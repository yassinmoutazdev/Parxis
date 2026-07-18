"""Backup Service for database backup and restore operations.

Corresponds to PRD Epic 10 - Backup & Settings.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Base exception for backup service errors."""

    pass


class BackupService:
    """Service for performing database backups using SQLite's online backup API.

    Supports:
    - Timestamped snapshots using SQLite's online backup API
    - Automatic rotation with configurable retention (daily + monthly)
    - Manual restore from backups
    """

    @classmethod
    def perform_backup(cls) -> Path:
        """Create a timestamped backup of the database.

        Uses SQLite's online backup API to create a consistent snapshot.

        Returns:
            Path to the created backup file

        Raises:
            BackupError: If the database doesn't exist or backup fails
        """
        db_path = settings.db_path

        if not db_path.exists():
            raise BackupError(f"Database file does not exist: {db_path}")

        # Ensure backup directory exists
        settings.backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"praxis_{timestamp}.db"
        backup_path = settings.backup_dir / backup_filename

        try:
            # Use SQLite's online backup API
            source_conn = sqlite3.connect(str(db_path), timeout=30)
            dest_conn = sqlite3.connect(str(backup_path), timeout=30)

            # Perform the backup
            source_conn.backup(dest_conn)

            dest_conn.close()
            source_conn.close()

            logger.info(f"Database backup created: {backup_path}")

            return backup_path
        except Exception as e:
            # Clean up partial backup on failure
            if backup_path.exists():
                backup_path.unlink()
            raise BackupError(f"Backup failed: {e}") from e

    @classmethod
    def rotate(cls) -> dict[str, int]:
        """Rotate backups to retain configured counts.

        Retains:
        - Last N daily backups (configurable via Config.backup_retention_daily)
        - Last N monthly backups (configurable via Config.backup_retention_monthly)

        Daily backups are identified by date (YYYYMMDD_*.db).
        Monthly backups are identified as the first backup of each month.

        Returns:
            Dict with counts of deleted and retained backups
        """
        backup_dir = settings.backup_dir

        if not backup_dir.exists():
            logger.info("No backups to rotate - backup directory does not exist")
            return {"deleted": 0, "retained": 0}

        # Get all backup files sorted by name (which includes timestamp)
        backup_files = sorted(backup_dir.glob("praxis_*.db"))

        if not backup_files:
            return {"deleted": 0, "retained": 0}

        # Separate daily and monthly backups
        daily_backups: list[Path] = []
        monthly_backups: list[Path] = []

        for backup_file in backup_files:
            # Extract date from filename: praxis_YYYYMMDD_HHMMSS.db
            try:
                date_part = backup_file.stem.replace("praxis_", "").split("_")[0]
                date = datetime.strptime(date_part, "%Y%m%d")

                daily_backups.append((backup_file, date))
            except ValueError:
                logger.warning(f"Skipping invalid backup filename: {backup_file.name}")
                continue

        # Sort daily backups by date
        daily_backups.sort(key=lambda x: x[1])

        # Identify monthly backups (first backup of each month)
        # Go in forward order to find the first backup of each month
        seen_months: set[tuple[int, int]] = set()  # (year, month)
        monthly_backups: list[Path] = []

        for backup_file, date in daily_backups:
            month_key = (date.year, date.month)
            if month_key not in seen_months:
                seen_months.add(month_key)
                monthly_backups.append(backup_file)

        # Determine which backups to delete
        daily_retention = settings.backup_retention_daily
        monthly_retention = settings.backup_retention_monthly

        # Approach: keep the most recent N backups (daily) PLUS
        # M more first-of-month backups that aren't already in the daily set
        # This ensures we get at least N+M backups but handles overlaps

        # Get the most recent N backups (these are our daily retention)
        daily_to_keep = set(bf for bf, _ in daily_backups[-daily_retention:])

        # Get M more monthly backups that aren't already in daily_to_keep
        # We go through monthly backups newest to oldest
        monthly_to_keep: set[Path] = set()
        for backup_file in reversed(monthly_backups):
            if len(monthly_to_keep) >= monthly_retention:
                break
            if backup_file not in daily_to_keep:
                monthly_to_keep.add(backup_file)

        # Combine both sets
        combined_to_keep = daily_to_keep | monthly_to_keep

        # Delete backups not in keep set
        deleted_count = 0
        for backup_file, _ in daily_backups:
            if backup_file not in combined_to_keep:
                try:
                    backup_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {backup_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete backup {backup_file.name}: {e}")

        retained_count = len(daily_backups) - deleted_count

        logger.info(
            f"Backup rotation complete: deleted {deleted_count}, retained {retained_count}"
        )

        return {"deleted": deleted_count, "retained": retained_count}

    @classmethod
    def check_and_backup_if_needed(cls) -> dict[str, object]:
        """Check if a backup is needed and perform one if necessary.

        Idempotent: checks the last backup timestamp and only creates a new
        backup if the last backup is older than 24 hours or no backup exists.

        Returns:
            Dict with backup status information
        """
        backup_dir = settings.backup_dir

        # If backup directory doesn't exist, perform initial backup
        if not backup_dir.exists():
            backup_path = cls.perform_backup()
            cls.rotate()  # Run rotation after new backup
            return {
                "action": "backup_created",
                "path": str(backup_path),
                "reason": "no_backup_exists",
            }

        # Find the most recent backup
        backup_files = sorted(backup_dir.glob("praxis_*.db"))

        if not backup_files:
            backup_path = cls.perform_backup()
            cls.rotate()
            return {
                "action": "backup_created",
                "path": str(backup_path),
                "reason": "no_backup_exists",
            }

        # Check if most recent backup is older than 24 hours
        latest_backup = backup_files[-1]
        try:
            date_part = latest_backup.stem.replace("praxis_", "").split("_")[0]
            time_part = latest_backup.stem.replace("praxis_", "").split("_")[1]
            backup_datetime = datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")
        except ValueError:
            # Invalid filename format, create new backup
            backup_path = cls.perform_backup()
            cls.rotate()
            return {
                "action": "backup_created",
                "path": str(backup_path),
                "reason": "invalid_backup_filename",
            }

        # Check if 24 hours have passed
        if datetime.now() - backup_datetime > timedelta(hours=24):
            backup_path = cls.perform_backup()
            cls.rotate()
            return {
                "action": "backup_created",
                "path": str(backup_path),
                "reason": "backup_older_than_24h",
            }

        return {
            "action": "skipped",
            "reason": "recent_backup_exists",
            "last_backup": str(latest_backup.name),
        }

    @classmethod
    def list_backups(cls) -> list[dict[str, object]]:
        """List all available backups with metadata.

        Returns:
            List of dicts with backup information (path, created_at, size_bytes)
        """
        backup_dir = settings.backup_dir

        if not backup_dir.exists():
            return []

        backups = []
        for backup_file in sorted(backup_dir.glob("praxis_*.db")):
            try:
                date_part = backup_file.stem.replace("praxis_", "").split("_")[0]
                time_part = backup_file.stem.replace("praxis_", "").split("_")[1]
                created_at = datetime.strptime(
                    f"{date_part}_{time_part}", "%Y%m%d_%H%M%S"
                )

                backups.append(
                    {
                        "name": backup_file.name,
                        "path": str(backup_file),
                        "created_at": created_at.isoformat(),
                        "size_bytes": backup_file.stat().st_size,
                    }
                )
            except ValueError:
                logger.warning(f"Skipping invalid backup filename: {backup_file.name}")
                continue

        return backups

    @classmethod
    def restore(cls, backup_path: str | Path) -> dict[str, str]:
        """Restore database from a backup file.

        WARNING: This operation replaces the current database file.
        Should only be used when requested by the learner.

        Args:
            backup_path: Path to the backup file to restore

        Returns:
            Dict with restore status message

        Raises:
            BackupError: If the backup file doesn't exist or restore fails
        """
        backup_path = Path(backup_path)

        if not backup_path.exists():
            raise BackupError(f"Backup file does not exist: {backup_path}")

        db_path = settings.db_path

        # Ensure backup directory exists
        settings.backup_dir.mkdir(parents=True, exist_ok=True)

        # Create a backup of current database before restoring (safety net)
        safety_backup_path = db_path.with_suffix(".db.pre_restore")
        if db_path.exists():
            try:
                source_conn = sqlite3.connect(str(db_path), timeout=30)
                dest_conn = sqlite3.connect(str(safety_backup_path), timeout=30)
                source_conn.backup(dest_conn)
                dest_conn.close()
                source_conn.close()
                logger.info(f"Safety backup created: {safety_backup_path}")
            except Exception as e:
                logger.warning(f"Failed to create safety backup: {e}")

        try:
            # Restore from backup
            source_conn = sqlite3.connect(str(backup_path), timeout=30)
            dest_conn = sqlite3.connect(str(db_path), timeout=30)

            # Copy from source (backup) to destination (main db)
            source_conn.backup(dest_conn)

            dest_conn.close()
            source_conn.close()

            logger.info(f"Database restored from backup: {backup_path}")

            return {
                "status": "success",
                "message": f"Database restored from {backup_path.name}",
                "safety_backup": str(safety_backup_path),
            }
        except Exception as e:
            raise BackupError(f"Restore failed: {e}") from e