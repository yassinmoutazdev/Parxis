"""Tests for Chat Service."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
from app.chat.service import (
    CHAT_HISTORY_TOKEN_BUDGET,
    ChatService,
    _estimate_tokens,
)
from app.chat.attachments import MAX_ATTACHMENT_CONTEXT_CHARS
from app.chat.router import _attachments_response
from app.db.models.chat import AttachmentKind, ChatActionType, ChatMessage, ChatRole, ChatThread
from app.db import engine as db_engine
from app.llm.ollama_adapter import ToolCallResult
from app.llm.schemas import CoachHistorySummary


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

    def test_delete_thread_with_attachment(self, test_engine):
        """Deleting a thread whose message has an attachment must not
        raise a foreign-key IntegrityError.

        Regression test: ChatMessageAttachment FK-references
        chat_message.id with no ON DELETE CASCADE, and PRAGMA
        foreign_keys=ON is set, so bulk-deleting ChatMessage rows without
        first clearing their attachments raised sqlite3.IntegrityError -
        the actual cause of "DELETE /api/chat/threads/{id}" 500s in
        production once a message in the thread had an attachment.
        """
        thread = ChatService.create_thread()
        message = ChatService.append_message(thread.id, ChatRole.USER, "Test")
        ChatService.add_attachment(
            message_id=message.id,
            filename="notes.txt",
            mime_type="text/plain",
            kind=AttachmentKind.TEXT,
            extracted_text="some extracted text",
        )

        # Previously raised sqlalchemy.exc.IntegrityError here.
        ChatService.delete_thread(thread.id)

        with pytest.raises(ValueError, match="Chat thread .* not found"):
            ChatService.get_thread(thread.id)

    def test_truncate_after_with_attachment(self, test_engine):
        """Same FK issue as delete_thread, but for the edit-with-regenerate
        truncation path (ChatService.truncate_after)."""
        thread = ChatService.create_thread()
        anchor = ChatService.append_message(thread.id, ChatRole.USER, "First")
        later = ChatService.append_message(thread.id, ChatRole.ASSISTANT, "Second")
        ChatService.add_attachment(
            message_id=later.id,
            filename="image.png",
            mime_type="image/png",
            kind=AttachmentKind.IMAGE,
            stored_path="/tmp/fake/image.png",
        )

        # Previously raised sqlalchemy.exc.IntegrityError here.
        ChatService.truncate_after(thread.id, anchor.id)

        messages = ChatService.list_messages(thread.id)
        assert [m.id for m in messages] == [anchor.id]


class TestChatHistorySummarization:
    """Tests for the token-budget-based rolling summary (replaces the old
    fixed messages[-20:] cap in the main chat loop)."""

    LONG_TEXT = "x" * 60_000  # comfortably exceeds CHAT_HISTORY_TOKEN_BUDGET on its own

    @pytest.mark.asyncio
    async def test_summary_trigger_on_long_thread(self, test_engine):
        """A thread whose raw history exceeds the token budget gets folded
        into thread.history_summary, and summarized_up_to_message_id points
        at the last message that was folded (not the newest raw one)."""
        thread = ChatService.create_thread()
        # Seed a prior USER/ASSISTANT pair so is_first_reply is False for
        # the call under test -- keeps this test focused on summarization,
        # not the separate thread-title code path.
        seed_user = ChatService.append_message(thread.id, ChatRole.USER, "hi")
        seed_assistant = ChatService.append_message(
            thread.id, ChatRole.ASSISTANT, "hello"
        )
        long_msg = ChatService.append_message(
            thread.id, ChatRole.USER, self.LONG_TEXT
        )

        with patch("app.chat.service.ollama_adapter.ollama_adapter") as mock_adapter:
            mock_adapter.generate_chat_with_tools = AsyncMock(
                return_value=ToolCallResult(content="a normal reply")
            )
            mock_adapter.generate = AsyncMock(
                return_value=CoachHistorySummary(summary="Learner said hi.")
            )

            reply = await ChatService.generate_reply(thread.id)

        assert reply.content == "a normal reply"

        updated_thread = ChatService.get_thread(thread.id)
        assert updated_thread.history_summary == "Learner said hi."
        # The long message alone already exceeds the budget, so it must be
        # the one thing left raw -- folding stops at the message before it,
        # guaranteeing forward progress without losing the newest turn.
        assert updated_thread.summarized_up_to_message_id == seed_assistant.id
        assert updated_thread.summarized_up_to_message_id != long_msg.id

    @pytest.mark.asyncio
    async def test_no_premature_summary_for_short_thread(self, test_engine):
        """A short thread, well under the token budget, never gets a
        summary -- identical behavior to before this change."""
        thread = ChatService.create_thread()
        ChatService.append_message(thread.id, ChatRole.USER, "hi")
        ChatService.append_message(thread.id, ChatRole.ASSISTANT, "hello")
        ChatService.append_message(thread.id, ChatRole.USER, "how are you?")

        with patch("app.chat.service.ollama_adapter.ollama_adapter") as mock_adapter:
            mock_adapter.generate_chat_with_tools = AsyncMock(
                return_value=ToolCallResult(content="doing great")
            )
            mock_adapter.generate = AsyncMock(
                side_effect=AssertionError(
                    "summarization should not run for a short thread"
                )
            )

            await ChatService.generate_reply(thread.id)

        updated_thread = ChatService.get_thread(thread.id)
        assert updated_thread.history_summary is None
        assert updated_thread.summarized_up_to_message_id is None

    @pytest.mark.asyncio
    async def test_sliding_summary_moves_forward_only(self, test_engine):
        """Across multiple turns past the threshold,
        summarized_up_to_message_id only ever advances, and the raw portion
        sent to the LLM never re-includes already-summarized messages."""
        thread = ChatService.create_thread()
        seed_user = ChatService.append_message(thread.id, ChatRole.USER, "hi")
        seed_assistant = ChatService.append_message(
            thread.id, ChatRole.ASSISTANT, "hello"
        )
        ChatService.append_message(thread.id, ChatRole.USER, self.LONG_TEXT)

        with patch("app.chat.service.ollama_adapter.ollama_adapter") as mock_adapter:
            mock_adapter.generate_chat_with_tools = AsyncMock(
                return_value=ToolCallResult(content="reply one")
            )
            mock_adapter.generate = AsyncMock(
                return_value=CoachHistorySummary(summary="summary v1")
            )
            await ChatService.generate_reply(thread.id)

        thread_after_round_1 = ChatService.get_thread(thread.id)
        first_summarized_up_to = thread_after_round_1.summarized_up_to_message_id
        assert first_summarized_up_to == seed_assistant.id

        # Round 2: another oversized message pushes the raw remainder over
        # budget again.
        ChatService.append_message(thread.id, ChatRole.USER, self.LONG_TEXT)

        with patch("app.chat.service.ollama_adapter.ollama_adapter") as mock_adapter:
            mock_adapter.generate_chat_with_tools = AsyncMock(
                return_value=ToolCallResult(content="reply two")
            )
            mock_adapter.generate = AsyncMock(
                return_value=CoachHistorySummary(summary="summary v2")
            )
            await ChatService.generate_reply(thread.id)

        thread_after_round_2 = ChatService.get_thread(thread.id)
        second_summarized_up_to = thread_after_round_2.summarized_up_to_message_id

        assert second_summarized_up_to > first_summarized_up_to
        assert thread_after_round_2.history_summary == "summary v2"

        # The raw remainder sent to the model on round 2 must never include
        # anything at or before first_summarized_up_to.
        all_messages = ChatService.list_messages(thread.id)
        raw_after_round_2 = [
            m for m in all_messages if m.id > second_summarized_up_to
        ]
        assert all(m.id > first_summarized_up_to for m in raw_after_round_2)

    @pytest.mark.asyncio
    async def test_summarization_failure_is_non_fatal(self, test_engine):
        """If the summarization LLM call raises, generate_reply must still
        return a normal assistant reply (best-effort pattern, same as
        _maybe_set_thread_title)."""
        thread = ChatService.create_thread()
        ChatService.append_message(thread.id, ChatRole.USER, "hi")
        ChatService.append_message(thread.id, ChatRole.ASSISTANT, "hello")
        ChatService.append_message(thread.id, ChatRole.USER, self.LONG_TEXT)

        with patch("app.chat.service.ollama_adapter.ollama_adapter") as mock_adapter:
            mock_adapter.generate_chat_with_tools = AsyncMock(
                return_value=ToolCallResult(content="still works")
            )
            mock_adapter.generate = AsyncMock(side_effect=Exception("boom"))

            reply = await ChatService.generate_reply(thread.id)

        assert reply.content == "still works"
        updated_thread = ChatService.get_thread(thread.id)
        # Summarization failed, so no summary should have been persisted.
        assert updated_thread.history_summary is None


class TestAttachmentContextCap:
    """Tests for the separate, smaller cap on attachment text folded into
    the LLM prompt (independent of the 10MB raw-upload size limit)."""

    def test_format_history_truncates_oversized_attachment_text(self, test_engine):
        thread = ChatService.create_thread()
        message = ChatService.append_message(thread.id, ChatRole.USER, "see attached")
        long_text = "a" * (MAX_ATTACHMENT_CONTEXT_CHARS + 500)
        ChatService.add_attachment(
            message_id=message.id,
            filename="essay.txt",
            mime_type="text/plain",
            kind=AttachmentKind.TEXT,
            extracted_text=long_text,
        )

        history = ChatService._format_history_for_tools([message])

        assert len(history) == 1
        content = history[0]["content"]
        assert "[... truncated, file was longer than this ...]" in content
        # The folded-in text itself must be capped, even though the marker
        # text pushes the *total* content length a bit past the cap.
        folded_text_start = content.index("[Attached: essay.txt]\n") + len(
            "[Attached: essay.txt]\n"
        )
        marker_start = content.index("\n[... truncated")
        assert marker_start - folded_text_start == MAX_ATTACHMENT_CONTEXT_CHARS

        # The full extracted_text must remain untouched in storage.
        stored = ChatService.list_attachments(message.id)
        assert len(stored) == 1
        assert stored[0].extracted_text == long_text
        assert len(stored[0].extracted_text) == MAX_ATTACHMENT_CONTEXT_CHARS + 500

    def test_format_history_leaves_short_attachment_untouched(self, test_engine):
        thread = ChatService.create_thread()
        message = ChatService.append_message(thread.id, ChatRole.USER, "see attached")
        short_text = "short content"
        ChatService.add_attachment(
            message_id=message.id,
            filename="note.txt",
            mime_type="text/plain",
            kind=AttachmentKind.TEXT,
            extracted_text=short_text,
        )

        history = ChatService._format_history_for_tools([message])

        content = history[0]["content"]
        assert "[... truncated" not in content
        assert short_text in content


class TestAttachmentContextTruncatedFlag:
    """Tests for AttachmentResponse.context_truncated (router.py)."""

    def test_flag_true_for_over_cap_text_attachment(self, test_engine):
        thread = ChatService.create_thread()
        message = ChatService.append_message(thread.id, ChatRole.USER, "see attached")
        long_text = "a" * (MAX_ATTACHMENT_CONTEXT_CHARS + 1)
        ChatService.add_attachment(
            message_id=message.id,
            filename="essay.txt",
            mime_type="text/plain",
            kind=AttachmentKind.TEXT,
            extracted_text=long_text,
        )

        responses = _attachments_response(message.id)

        assert responses is not None
        assert len(responses) == 1
        assert responses[0].context_truncated is True

    def test_flag_false_for_short_text_attachment(self, test_engine):
        thread = ChatService.create_thread()
        message = ChatService.append_message(thread.id, ChatRole.USER, "see attached")
        ChatService.add_attachment(
            message_id=message.id,
            filename="note.txt",
            mime_type="text/plain",
            kind=AttachmentKind.TEXT,
            extracted_text="short",
        )

        responses = _attachments_response(message.id)

        assert responses is not None
        assert responses[0].context_truncated is False

    def test_flag_false_for_image_attachment(self, test_engine):
        thread = ChatService.create_thread()
        message = ChatService.append_message(thread.id, ChatRole.USER, "see attached")
        ChatService.add_attachment(
            message_id=message.id,
            filename="photo.png",
            mime_type="image/png",
            kind=AttachmentKind.IMAGE,
            stored_path="/tmp/fake/photo.png",
        )

        responses = _attachments_response(message.id)

        assert responses is not None
        assert responses[0].context_truncated is False


class TestEstimateTokens:
    """Sanity checks for the chars-per-token heuristic."""

    def test_estimate_tokens_scales_with_length(self):
        assert _estimate_tokens("") == 1  # floor of at least 1
        assert _estimate_tokens("a" * 4000) == 1000
        assert _estimate_tokens("a" * 4000) < _estimate_tokens("a" * 8000)

    def test_budget_constant_is_reasonable(self):
        # Not a behavioral test, just guards against an accidental
        # order-of-magnitude typo in the constant.
        assert 8_000 <= CHAT_HISTORY_TOKEN_BUDGET <= 20_000
