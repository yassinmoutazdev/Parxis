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

router = APIRouter(prefix="/settings", tags=["settings"])


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