"""Database engine and session management."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.config import settings


def create_db_engine():
    """Create the SQLModel engine with WAL mode and foreign keys enabled."""
    # Ensure parent directories exist
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create engine with SQLite
    engine = create_engine(
        f"sqlite:///{settings.db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Enable WAL mode
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


# Global engine instance
engine = create_db_engine()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Session:
    """Context manager for database sessions.

    Usage:
        with Session() as session:
            session.query(Model).all()
    """

    def __enter__(self):
        self._session = SessionLocal()
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            self._session.close()


def get_session() -> Generator:
    """FastAPI dependency for getting a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Initialize database - create all tables."""
    SQLModel.metadata.create_all(engine)


def get_db_url() -> str:
    """Get the database URL."""
    return str(settings.db_path)
