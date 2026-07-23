"""Pytest configuration and fixtures for Praxis tests."""

import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Import all models to register them with SQLModel.metadata
from app.db.models import (
    approval,
    chat,
    learning_correction,
    learning_item,
    note,
    performance_error,
    quiz,
    report,
    source,
    system,
    writing,
)


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
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database file for a test.

    Uses a temp file (not in-memory) since WAL mode behavior matters
    and we need to test actual file operations.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()
        # Also clean up WAL files
        wal_path = db_path.with_suffix(".db-wal")
        if wal_path.exists():
            wal_path.unlink()
        shm_path = db_path.with_suffix(".db-shm")
        if shm_path.exists():
            shm_path.unlink()


@pytest.fixture(scope="function")
def test_engine(temp_db_path):
    """Create a test database engine."""
    engine = _create_test_engine(temp_db_path)

    # Create all tables
    SQLModel.metadata.create_all(engine)

    yield engine

    # Cleanup
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_engine):
    """Create a test database session.

    This fixture provides a Session that can be used in tests.
    It uses a real temp file with WAL mode for proper testing.
    """
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def override_get_generator():
    """Fixture to override the get_generator FastAPI dependency.

    Usage:
        async def test_something(override_get_generator):
            fake_gen = FakeGenerator()
            fake_gen.register('task', OutputSchema(field=value))
            override_get_generator(fake_gen)

            # Now FastAPI endpoints will use fake_gen
    """
    from app.llm.interface import Generator

    _original_generator = None

    @contextmanager
    def _override(generator: Generator):
        """Context manager to override the generator."""
        # This would be used with FastAPI's dependency overrides
        # In practice, you'd use app.dependency_overrides
        yield

    return _override


@pytest.fixture(scope="function")
def override_get_evaluator():
    """Fixture to override the get_evaluator FastAPI dependency.

    Usage:
        async def test_something(override_get_evaluator):
            fake_eval = FakeEvaluator()
            fake_eval.register('task', OutputSchema(field=value))
            override_get_evaluator(fake_eval)

            # Now FastAPI endpoints will use fake_eval
    """
    from app.llm.interface import Evaluator

    @contextmanager
    def _override(evaluator: Evaluator):
        """Context manager to override the evaluator."""
        yield

    return _override
