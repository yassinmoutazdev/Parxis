"""System database models (Config, AuditLog)."""

from datetime import datetime
from enum import Enum

from sqlmodel import JSON, Column, Field, SQLModel


class Config(SQLModel, table=True):
    """Key-value configuration store."""

    __tablename__ = "config"

    key: str = Field(primary_key=True)
    value: str


class AuditEventType(str, Enum):
    """Audit log event types."""

    PARSE_FAILED = "PARSE_FAILED"
    BACKUP_TAKEN = "BACKUP_TAKEN"
    BACKUP_FAILED = "BACKUP_FAILED"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    APPROVAL_ACTION = "APPROVAL_ACTION"


class AuditLog(SQLModel, table=True):
    """Audit log for tracking system events."""

    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    event_type: AuditEventType = Field(index=True)
    description: str
    event_metadata: dict | None = Field(default=None, sa_column=Column(JSON))
