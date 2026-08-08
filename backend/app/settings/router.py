"""Settings API router.

Corresponds to PRD Epic 10.2 - Configuration & Settings.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.backup.service import BackupError, BackupService
from app.config_service import (
    ConfigService,
    ConfigServiceError,
    ConfigValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ConfigGetResponse(BaseModel):
    """Response for GET /settings/config."""

    config: dict


class ConfigSetRequest(BaseModel):
    """Request for PUT /settings/config."""

    key: str
    value: str | int | float | bool | dict


class ConfigSetResponse(BaseModel):
    """Response for PUT /settings/config."""

    key: str
    value: str | int | float | bool | dict
    message: str


class BackupListResponse(BaseModel):
    """Response for GET /settings/backups."""

    backups: list[dict]


class BackupRestoreResponse(BaseModel):
    """Response for POST /settings/backups/{name}/restore."""

    status: str
    message: str
    safety_backup: str | None = None


class VaultPathSetRequest(BaseModel):
    """Request for PUT /settings/vault-path."""

    vault_path: str


class VaultPathSetResponse(BaseModel):
    """Response for PUT /settings/vault-path."""

    vault_path: str
    watcher_started: bool
    message: str


class EnvInfoResponse(BaseModel):
    """Response for GET /settings/env-info.

    Read-only view of infra-level configuration (pydantic-settings/.env), as
    opposed to the runtime-adjustable Config table above. Per ARCHITECTURE,
    this kind of config changes rarely, so it's surfaced for visibility only
    and is not editable from this endpoint.
    """

    ollama_host: str
    ollama_model: str
    ollama_api_key_set: bool
    vault_path: str
    db_path: str
    backup_dir: str


@router.get("/config")
async def get_config() -> ConfigGetResponse:
    """Get all runtime-configurable parameters.

    Returns current values along with metadata (type, min, max, default, description).
    """
    config = ConfigService.get_all()
    return ConfigGetResponse(config=config)


@router.put("/config")
async def set_config(payload: ConfigSetRequest) -> ConfigSetResponse:
    """Set a runtime-configurable parameter.

    Validates the value against min/max constraints defined in CONFIG_DEFINITIONS.
    """
    try:
        result = ConfigService.set(payload.key, payload.value)
        return ConfigSetResponse(
            key=result["key"],
            value=result["value"],
            message=f"Config '{payload.key}' updated successfully",
        )
    except ConfigValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConfigServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/env-info")
async def get_env_info() -> EnvInfoResponse:
    """Get read-only environment/infra info (from .env / pydantic-settings).

    These fields are not part of the runtime-adjustable Config table and are
    intentionally not editable here - they're a restart-and-edit-a-file
    concern, not a UI concern (ARCHITECTURE Section 12.2).
    """
    from app.config import settings as app_settings

    return EnvInfoResponse(
        ollama_host=app_settings.ollama_host,
        ollama_model=app_settings.ollama_model,
        ollama_api_key_set=bool(app_settings.ollama_api_key),
        vault_path=str(app_settings.vault_path),
        db_path=str(app_settings.db_path),
        backup_dir=str(app_settings.backup_dir),
    )


@router.put("/vault-path")
async def set_vault_path(payload: VaultPathSetRequest) -> VaultPathSetResponse:
    """Update the vault path and restart the watcher against the new location.

    The folder must exist. Takes effect immediately (no restart required).
    """
    from app.ingestion.watcher import restart_vault_watcher

    new_path = Path(payload.vault_path).expanduser()

    if not new_path.exists() or not new_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"'{payload.vault_path}' isn't a folder that exists on this machine.",
        )

    try:
        ConfigService.set("vault_path", str(new_path))
    except ConfigValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    watcher_started = restart_vault_watcher(new_path)

    return VaultPathSetResponse(
        vault_path=str(new_path),
        watcher_started=watcher_started,
        message="Vault path updated." if watcher_started else (
            "Vault path saved, but the watcher couldn't start — check the folder is readable."
        ),
    )


@router.get("/backups")
async def list_backups() -> BackupListResponse:
    """List all available backups with metadata."""
    backups = BackupService.list_backups()
    return BackupListResponse(backups=backups)


@router.post("/backups/{name}/restore")
async def restore_backup(name: str) -> BackupRestoreResponse:
    """Restore database from a backup file.

    WARNING: This operation replaces the current database file.
    Only use when explicitly requested by the learner.
    """
    from app.config import settings

    backup_path = settings.backup_dir / name

    if not backup_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Backup '{name}' not found"
        )

    try:
        result = BackupService.restore(backup_path)
        return BackupRestoreResponse(
            status=result["status"],
            message=result["message"],
            safety_backup=result.get("safety_backup"),
        )
    except BackupError as e:
        raise HTTPException(status_code=500, detail=str(e))