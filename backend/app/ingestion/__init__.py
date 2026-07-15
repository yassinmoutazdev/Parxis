"""Ingestion module for processing notes from the vault."""

from app.ingestion import duplicate_detection
from app.ingestion.service import IngestionService
from app.ingestion.watcher import VaultWatcher, get_vault_watcher

__all__ = [
    "IngestionService",
    "VaultWatcher",
    "get_vault_watcher",
    "duplicate_detection",
]
