"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

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

    # Start VaultWatcher as background thread
    from app.ingestion.watcher import get_vault_watcher

    vault_watcher = get_vault_watcher()
    vault_started = vault_watcher.start()

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


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint that verifies database integrity."""
    import sqlite3

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

        return {
            "status": "ok" if result[0] == "ok" else "error",
            "database": "ok" if result[0] == "ok" else "error",
            "integrity_check": result[0],
        }
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
from app.approvals.router import router as approvals_router
from app.quizzes.router import router as quizzes_router
from app.writing.router import router as writing_router

# Register routers
app.include_router(approvals_router)
app.include_router(quizzes_router)
app.include_router(writing_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
