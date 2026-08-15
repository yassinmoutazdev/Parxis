"""Tests for Chat Service."""

import pytest
import tempfile
from pathlib import Path
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Import models FIRST - before defining fixtures
from app.db.models import (
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

# Import service after models
from app.chat.service import ChatService
from app.db.models.chat import ChatActionType, ChatMessage, ChatRole, ChatThread
from app.db import engine as db_engine


def _create_test_engine(db_path):
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


@pytest.fixture
def test_engine(monkeypatch):
    """Create a file-based SQLite engine for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)

    test_eng = _create_test_engine(path)

    # Create all tables
    SQLModel.metadata.create_all(test_eng)

    # Create test session factory
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_eng)

    # Create a test Session class that uses our test engine
    class TestSession:
        def __enter__(self):
            self._session = TestSessionLocal()
            return self._session

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self._session:
                self._session.close()

    # Monkeypatch the Session in the chat.service module
    monkeypatch.setattr("app.chat.service.Session", TestSession)

    yield test_eng

    test_eng.dispose()
    Path(path).unlink(missing_ok=True)


class TestChatService:
    """Tests for ChatService CRUD operations."""

    def test_create_thread(self, test_engine):
        """Test creating a new thread."""
        thread = ChatService.create_thread()

        assert thread.id is not None
        assert thread.title is None
        assert thread.last_message_preview is None

    def test_list_threads_empty(self, test_engine):
        """Test listing threads when none exist."""
        threads = ChatService.list_threads()
        assert threads == []

    def test_list_threads_with_data(self, test_engine):
        """Test listing threads with existing data."""
        # Create some threads
        thread1 = ChatService.create_thread()
        # Add a message to thread1
        ChatService.append_message(thread1.id, ChatRole.USER, "Hello")

        thread2 = ChatService.create_thread()

        threads = ChatService.list_threads()
        assert len(threads) == 2
        # Should be ordered by updated_at desc
        assert threads[0].id == thread2.id

    def test_list_threads_pagination(self, test_engine):
        """Test thread listing with limit and offset."""
        # Create 5 threads
        for _ in range(5):
            ChatService.create_thread()

        threads = ChatService.list_threads(limit=2, offset=0)
        assert len(threads) == 2

        threads_page2 = ChatService.list_threads(limit=2, offset=2)
        assert len(threads_page2) == 2

    def test_get_thread(self, test_engine):
        """Test getting a thread by ID."""
        thread = ChatService.create_thread()
        retrieved = ChatService.get_thread(thread.id)

        assert retrieved.id == thread.id
        assert retrieved.title is None

    def test_get_thread_not_found(self, test_engine):
        """Test getting a non-existent thread raises ValueError."""
        with pytest.raises(ValueError, match="Chat thread 999 not found"):
            ChatService.get_thread(999)

    def test_append_message_user(self, test_engine):
        """Test appending a user message."""
        thread = ChatService.create_thread()

        message = ChatService.append_message(
            thread.id, ChatRole.USER, "Hello, coach!"
        )

        assert message.id is not None
        assert message.thread_id == thread.id
        assert message.role == ChatRole.USER
        assert message.content == "Hello, coach!"
        assert message.action_type == ChatActionType.NONE

    def test_append_message_updates_thread(self, test_engine):
        """Test that appending a message updates thread metadata."""
        thread = ChatService.create_thread()

        ChatService.append_message(thread.id, ChatRole.USER, "Test message")

        # Refresh thread from db
        updated_thread = ChatService.get_thread(thread.id)
        assert updated_thread.last_message_preview == "Test message"

    def test_append_message_preview_truncation(self, test_engine):
        """Test that message preview is truncated to ~120 chars."""
        thread = ChatService.create_thread()

        long_message = "A" * 200
        ChatService.append_message(thread.id, ChatRole.USER, long_message)

        updated_thread = ChatService.get_thread(thread.id)
        assert len(updated_thread.last_message_preview) == 120

    def test_append_message_action_type_quiz(self, test_engine):
        """Test appending a message with quiz action."""
        thread = ChatService.create_thread()

        message = ChatService.append_message(
            thread.id,
            ChatRole.ASSISTANT,
            "Let's do a quiz!",
            action_type=ChatActionType.QUIZ,
            action_ref_id=123,
        )

        assert message.action_type == ChatActionType.QUIZ
        assert message.action_ref_id == 123

    def test_list_messages_empty(self, test_engine):
        """Test listing messages in an empty thread."""
        thread = ChatService.create_thread()

        messages = ChatService.list_messages(thread.id)
        assert messages == []

    def test_list_messages_with_data(self, test_engine):
        """Test listing messages in a thread with data."""
        thread = ChatService.create_thread()

        ChatService.append_message(thread.id, ChatRole.USER, "Hello")
        ChatService.append_message(thread.id, ChatRole.ASSISTANT, "Hi there!")

        messages = ChatService.list_messages(thread.id)
        assert len(messages) == 2
        # Should be ordered by created_at asc
        assert messages[0].role == ChatRole.USER
        assert messages[1].role == ChatRole.ASSISTANT

    def test_delete_thread(self, test_engine):
        """Test deleting a thread."""
        thread = ChatService.create_thread()
        ChatService.append_message(thread.id, ChatRole.USER, "Test")

        ChatService.delete_thread(thread.id)

        with pytest.raises(ValueError, match="Chat thread .* not found"):
            ChatService.get_thread(thread.id)

    def test_delete_thread_cascades_messages(self, test_engine):
        """Test that deleting a thread deletes its messages."""
        thread = ChatService.create_thread()
        ChatService.append_message(thread.id, ChatRole.USER, "Test")

        ChatService.delete_thread(thread.id)

        messages = ChatService.list_messages(thread.id)
        assert messages == []

    def test_delete_thread_not_found(self, test_engine):
        """Test deleting a non-existent thread raises ValueError."""
        with pytest.raises(ValueError, match="Chat thread 999 not found"):
            ChatService.delete_thread(999)
