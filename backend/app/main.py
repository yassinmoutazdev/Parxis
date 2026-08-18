"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.llm.ollama_adapter import (
    OllamaAuthError,
    OllamaModelNotFoundError,
    OllamaRateLimitError,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
    logger.info("Starting Praxis application...")

    # Ensure data directory exists
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    settings.chat_attachments_dir.mkdir(parents=True, exist_ok=True)

    # Check and perform backup if needed (idempotent)
    from app.backup.service import BackupService

    backup_status = BackupService.check_and_backup_if_needed()
    logger.info(f"Startup backup check: {backup_status}")

    # Store backup status in app state
    app.state.backup_status = backup_status

    # Start VaultWatcher as background thread, using whatever vault path was
    # actually saved via Settings (ConfigService/DB) -- NOT the .env/default
    # fallback, which previously meant a saved path silently stopped being
    # used again the moment the app restarted, until Settings was reopened.
    from pathlib import Path

    from app.config_service import ConfigService
    from app.ingestion.watcher import get_vault_watcher, restart_vault_watcher

    saved_vault_path = ConfigService.get("vault_path")

    if saved_vault_path:
        vault_started = restart_vault_watcher(Path(saved_vault_path))
        vault_watcher = get_vault_watcher()
    else:
        logger.info(
            "No notes folder configured yet - watcher not started. "
            "Set one from Settings to begin watching for notes."
        )
        vault_watcher = get_vault_watcher()
        vault_started = False

    # Store watcher state in app state for access
    app.state.vault_watcher = vault_watcher
    app.state.vault_watcher_started = vault_started

    yield

    # Shutdown - stop VaultWatcher
    vault_watcher.stop()

    logger.info("Shutting down Praxis application...")


app = FastAPI(
    title="Praxis",
    description="Personal AI English Learning Coach",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - permissive for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OllamaAuthError)
async def handle_ollama_auth_error(request: Request, exc: OllamaAuthError) -> JSONResponse:
    """Turn any auth failure into the shape the frontend's global handler
    listens for (App.tsx), so it can drop back to the Connect screen from
    anywhere -- previously this exception was raised but never caught
    anywhere, so it surfaced as a raw unhandled 500 instead.
    """
    return JSONResponse(
        status_code=401,
        content={
            "error": "ollama_auth_failed",
            "detail": "Your Ollama Cloud API key is missing or was rejected. Reconnect to continue.",
        },
    )


@app.exception_handler(OllamaRateLimitError)
async def handle_ollama_rate_limit_error(
    request: Request, exc: OllamaRateLimitError
) -> JSONResponse:
    detail = "You've hit Ollama Cloud's rate limit. Wait a moment and try again."
    if exc.retry_after:
        detail = (
            "You've hit Ollama Cloud's rate limit. "
            f"Try again in about {exc.retry_after} seconds."
        )
    return JSONResponse(
        status_code=429,
        content={
            "error": "ollama_rate_limited",
            "detail": detail,
            "retry_after": exc.retry_after,
        },
    )


@app.exception_handler(OllamaModelNotFoundError)
async def handle_ollama_model_not_found_error(
    request: Request, exc: OllamaModelNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={
            "error": "ollama_model_not_found",
            "detail": (
                f"The model '{exc.model}' isn't available on Ollama Cloud. "
                "Check OLLAMA_MODEL."
            ),
        },
    )


@app.exception_handler(httpx.ConnectError)
async def handle_ollama_connect_error(request: Request, exc: httpx.ConnectError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": "ollama_unreachable",
            "detail": "Couldn't reach Ollama Cloud. Check your internet connection and try again.",
        },
    )


@app.exception_handler(httpx.TimeoutException)
async def handle_ollama_timeout_error(
    request: Request, exc: httpx.TimeoutException
) -> JSONResponse:
    return JSONResponse(
        status_code=504,
        content={
            "error": "ollama_timeout",
            "detail": "Ollama Cloud took too long to respond. Try again.",
        },
    )


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint that verifies database integrity.

    Includes automatic recovery path for corrupted databases:
    - On integrity_check failure, attempts to restore from most recent backup
    - Surfaces recovery notice in response
    - Offers manual restore endpoint for learner confirmation
    """
    import sqlite3

    from app.backup.service import BackupService

    # Get the database path
    db_path = settings.db_path

    if not db_path.exists():
        return {
            "status": "ok",
            "database": "not_initialized",
            "message": "Database file does not exist yet",
        }

    try:
        # Connect and run integrity check
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        conn.close()

        if result[0] == "ok":
            return {
                "status": "ok",
                "database": "ok",
                "integrity_check": result[0],
            }

        # Integrity check failed - database is corrupted
        # Try to restore from most recent backup
        backups = BackupService.list_backups()

        recovery_info = {
            "status": "error",
            "database": "corrupted",
            "integrity_check": result[0],
            "recovery_available": len(backups) > 0,
            "message": "Database integrity check failed",
            "backup_count": len(backups),
        }

        if backups:
            # Offer to restore from most recent backup
            most_recent = backups[-1]
            recovery_info["latest_backup"] = most_recent["name"]
            recovery_info["restore_endpoint"] = f"/settings/backups/{most_recent['name']}/restore"

            # Note: Automatic restore is NOT performed - learner must confirm
            recovery_info["auto_restore"] = False
            recovery_info["recovery_notice"] = (
                "Database is corrupted. A backup from "
                f"{most_recent['created_at']} is available. "
                "Use POST /settings/backups/{name}/restore to restore."
            )
        else:
            recovery_info["recovery_notice"] = (
                "Database is corrupted and no backups available. "
                "Data may be lost. Consider re-initializing the database."
            )

        return recovery_info

    except sqlite3.DatabaseError as e:
        # Database file is corrupted or inaccessible
        backups = BackupService.list_backups()

        response = {
            "status": "error",
            "database": "error",
            "error": str(e),
            "recovery_available": len(backups) > 0,
            "backup_count": len(backups),
        }

        if backups:
            most_recent = backups[-1]
            response["latest_backup"] = most_recent["name"]
            response["restore_endpoint"] = f"/settings/backups/{most_recent['name']}/restore"
            response["recovery_notice"] = (
                "Database file cannot be opened. A backup from "
                f"{most_recent['created_at']} is available. "
                "Use POST /settings/backups/{name}/restore to restore."
            )
        else:
            response["recovery_notice"] = (
                "Database file cannot be opened and no backups available. "
                "Data may be lost. Consider re-initializing the database."
            )

        return response
    except Exception as e:
        return {
            "status": "error",
            "database": "error",
            "error": str(e),
        }


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": "Praxis",
        "version": "0.1.0",
        "description": "Personal AI English Learning Coach",
    }


# Import routers
from app.chat.router import router as chat_router
from app.dashboard.router import router as dashboard_router
from app.quizzes.router import router as quizzes_router
from app.reports.router import router as reports_router
from app.settings.router import router as settings_router
from app.writing.router import router as writing_router

# Register routers
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(quizzes_router)
app.include_router(reports_router)
app.include_router(settings_router)
app.include_router(writing_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
