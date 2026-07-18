"""Integration tests for Backup Service.

Corresponds to PRD Epic 10.4.1 - Backup → Rotate → Restore round-trip tests.
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event
from sqlmodel import SQLModel


def _create_test_engine(db_path: Path):
    """Create a test database engine with WAL mode."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(scope="function")
def temp_backup_dir():
    """Create a temporary directory for backups."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="function")
def temp_db_path():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Create tables
    engine = _create_test_engine(db_path)
    SQLModel.metadata.create_all(engine)
    engine.dispose()

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()
    wal_path = db_path.with_suffix(".db-wal")
    if wal_path.exists():
        wal_path.unlink()
    shm_path = db_path.with_suffix(".db-shm")
    if shm_path.exists():
        shm_path.unlink()


class TestBackupService:
    """Tests for BackupService functionality."""

    def test_perform_backup_creates_file(self, temp_db_path, temp_backup_dir):
        """Test that perform_backup creates a backup file."""
        from app.backup.service import BackupService

        with patch("app.backup.service.settings") as mock_settings:
            mock_settings.db_path = temp_db_path
            mock_settings.backup_dir = temp_backup_dir

            backup_path = BackupService.perform_backup()

            assert backup_path.exists()
            assert backup_path.name.startswith("praxis_")
            assert backup_path.name.endswith(".db")

    def test_perform_backup_preserves_data(self, temp_db_path, temp_backup_dir):
        """Test that backup contains the same data as source."""
        from app.backup.service import BackupService

        # Add some test data to the database
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, value TEXT)"
        )
        cursor.execute("INSERT INTO test_table (value) VALUES ('test_value')")
        conn.commit()
        conn.close()

        with patch("app.backup.service.settings") as mock_settings:
            mock_settings.db_path = temp_db_path
            mock_settings.backup_dir = temp_backup_dir

            backup_path = BackupService.perform_backup()

            # Verify data in backup
            conn = sqlite3.connect(backup_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM test_table")
            result = cursor.fetchone()
            conn.close()

            assert result is not None
            assert result[0] == "test_value"

    def test_rotate_deletes_old_backups(self, temp_db_path, temp_backup_dir):
        """Test that rotate removes old backups beyond retention."""
        from app.backup.service import BackupService

        with patch("app.backup.service.settings") as mock_settings:
            mock_settings.db_path = temp_db_path
            mock_settings.backup_dir = temp_backup_dir
            mock_settings.backup_retention_daily = 3
            mock_settings.backup_retention_monthly = 1

            # Create 5 backups with different timestamps (all in same month)
            for i in range(5):
                backup_path = temp_backup_dir / f"praxis_2024010{i+1}_120000.db"
                backup_path.touch()

            # Run rotate
            result = BackupService.rotate()

            # With 5 backups and daily_retention=3, monthly_retention=1:
            # - Keep last 3 daily: 20240103, 20240104, 20240105
            # - Add first of month (20240101) since not in daily set: +1
            # - Total: 4
            assert result["retained"] == 4
            assert result["deleted"] == 1

    def test_rotate_keeps_monthly_backups(self, temp_db_path, temp_backup_dir):
        """Test that rotate keeps first backup of each month."""
        from app.backup.service import BackupService

        with patch("app.backup.service.settings") as mock_settings:
            mock_settings.db_path = temp_db_path
            mock_settings.backup_dir = temp_backup_dir
            mock_settings.backup_retention_daily = 2
            mock_settings.backup_retention_monthly = 2

            # Create backups for different months
            backups = [
                "praxis_20240101_120000.db",  # Jan 1 (first of Jan)
                "praxis_20240115_120000.db",  # Jan 15
                "praxis_20240201_120000.db",  # Feb 1 (first of Feb)
                "praxis_20240215_120000.db",  # Feb 15
            ]

            for backup_name in backups:
                (temp_backup_dir / backup_name).touch()

            result = BackupService.rotate()

            # With daily_retention=2:
            # - Keep last 2 daily: Feb 15, Feb 1 (Feb 1 is also first of Feb)
            # - First of each month NOT in daily: Jan 1
            # - Combined: Feb 15, Feb 1, Jan 1 = 3
            assert result["retained"] == 3
            assert result["deleted"] == 1

    def test_list_backups_returns_metadata(self, temp_db_path, temp_backup_dir):
        """Test that list_backups returns proper metadata."""
        from app.backup.service import BackupService

        with patch("app.backup.service.settings") as mock_settings:
            mock_settings.db_path = temp_db_path
            mock_settings.backup_dir = temp_backup_dir

            # Create a backup
            BackupService.perform_backup()

            backups = BackupService.list_backups()

            assert len(backups) == 1
            assert "name" in backups[0]
            assert "path" in backups[0]
            assert "created_at" in backups[0]
            assert "size_bytes" in backups[0]

    def test_restore_replaces_database(self, temp_db_path, temp_backup_dir):
        """Test that restore replaces the current database."""
        from app.backup.service import BackupService

        with patch("app.backup.service.settings") as mock_settings:
            mock_settings.db_path = temp_db_path
            mock_settings.backup_dir = temp_backup_dir

            # Add data to original database
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS restore_test (id INTEGER PRIMARY KEY, value TEXT)"
            )
            cursor.execute("INSERT INTO restore_test (value) VALUES ('original')")
            conn.commit()
            conn.close()

            # Create backup
            backup_path = BackupService.perform_backup()

            # Modify database
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE restore_test SET value = 'modified'")
            conn.commit()
            conn.close()

            # Restore from backup
            result = BackupService.restore(backup_path)

            # Verify data is restored
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM restore_test")
            result_value = cursor.fetchone()
            conn.close()

            assert result["status"] == "success"
            assert result_value[0] == "original"

    def test_check_and_backup_creates_backup_when_none_exists(
        self, temp_db_path, temp_backup_dir
    ):
        """Test that check_and_backup creates backup when none exist."""
        from app.backup.service import BackupService

        with patch("app.backup.service.settings") as mock_settings:
            mock_settings.db_path = temp_db_path
            mock_settings.backup_dir = temp_backup_dir
            mock_settings.backup_retention_daily = 14
            mock_settings.backup_retention_monthly = 6

            result = BackupService.check_and_backup_if_needed()

            assert result["action"] == "backup_created"
            assert result["reason"] == "no_backup_exists"

    def test_check_and_backup_skips_recent_backup(
        self, temp_db_path, temp_backup_dir
    ):
        """Test that check_and_backup skips backup when recent one exists."""
        from app.backup.service import BackupService

        with patch("app.backup.service.settings") as mock_settings:
            mock_settings.db_path = temp_db_path
            mock_settings.backup_dir = temp_backup_dir
            mock_settings.backup_retention_daily = 14
            mock_settings.backup_retention_monthly = 6

            # Create a backup
            BackupService.perform_backup()

            # Should skip - backup exists and is recent
            result = BackupService.check_and_backup_if_needed()

            assert result["action"] == "skipped"
            assert result["reason"] == "recent_backup_exists"

    def test_check_and_backup_creates_backup_when_old(
        self, temp_db_path, temp_backup_dir
    ):
        """Test that check_and_backup creates backup when last one is old."""
        from app.backup.service import BackupService

        with patch("app.backup.service.settings") as mock_settings:
            mock_settings.db_path = temp_db_path
            mock_settings.backup_dir = temp_backup_dir
            mock_settings.backup_retention_daily = 14
            mock_settings.backup_retention_monthly = 6

            # Create old backup by modifying mtime
            old_backup = temp_backup_dir / "praxis_20240101_120000.db"
            old_backup.touch()

            # Run check
            result = BackupService.check_and_backup_if_needed()

            # Should create new backup
            assert result["action"] == "backup_created"
            assert result["reason"] == "backup_older_than_24h"


class TestBackupRestoreWithData:
    """Test backup/restore with actual database content."""

    # Note: Full integration tests with SQLModel entities require proper database setup
    # and are covered indirectly by other tests. The core backup/restore functionality
    # is tested in TestBackupService.


class TestHealthCheckRecovery:
    """Tests for health endpoint recovery path."""

    def test_health_check_returns_error_on_corrupted_db(self):
        """Test that health check returns error status when database is corrupted."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        # Create a temporary corrupted database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)

            # Create a corrupted database file
            with open(db_path, "wb") as f:
                f.write(b"INVALID SQLITE DATABASE CONTENT" * 100)

            # Patch settings
            with patch("app.backup.service.settings") as mock_backup:
                mock_backup.db_path = db_path
                mock_backup.backup_dir = backup_dir

                with patch("app.main.settings") as mock_main:
                    mock_main.db_path = db_path
                    mock_main.backup_dir = backup_dir

                    from app.main import health_check
                    import asyncio

                    # Run in a new event loop
                    result = asyncio.run(health_check())

                    # Should return error status
                    assert result["status"] == "error"
                    assert result["database"] == "error"
                    assert "recovery_available" in result

        # Cleanup
        if db_path.exists():
            try:
                db_path.unlink()
            except PermissionError:
                pass

    def test_health_check_offers_restore_when_backup_exists(self):
        """Test that health check offers restore when backup exists and DB is corrupted."""
        import tempfile
        import sqlite3
        from pathlib import Path
        from unittest.mock import patch

        # Create a temporary valid database first
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        # Create a valid SQLite database
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        conn.close()

        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)

            # Create a backup from the valid database
            with patch("app.backup.service.settings") as mock_backup:
                mock_backup.db_path = db_path
                mock_backup.backup_dir = backup_dir

                from app.backup.service import BackupService

                BackupService.perform_backup()

            # Now corrupt the database
            with open(db_path, "wb") as f:
                f.write(b"CORRUPTED" * 50)

            # Check health endpoint
            with patch("app.backup.service.settings") as mock_backup:
                mock_backup.db_path = db_path
                mock_backup.backup_dir = backup_dir

                with patch("app.main.settings") as mock_main:
                    mock_main.db_path = db_path
                    mock_main.backup_dir = backup_dir

                    from app.main import health_check
                    import asyncio

                    result = asyncio.run(health_check())

                    # Should indicate recovery is available
                    assert result["recovery_available"] is True
                    assert "latest_backup" in result
                    assert "restore_endpoint" in result

        # Cleanup
        if db_path.exists():
            try:
                db_path.unlink()
            except PermissionError:
                pass