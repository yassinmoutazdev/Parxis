"""Integration tests for IngestionService.

Corresponds to ARCHITECTURE Section 17.2 (Testing Boundaries).
"""

from unittest.mock import patch

import pytest

from app.db.engine import Session
from app.db.models.note import Note, NoteStatus
from app.ingestion.service import IngestionService
from app.llm.schemas import ParsedItem, ParsedNoteOutput


class FakeGenerator:
    """Fake generator for testing."""

    def __init__(self, should_fail: bool = False, fail_after_retries: int = 0):
        self.should_fail = should_fail
        self.fail_after_retries = fail_after_retries
        self.call_count = 0

    async def generate(self, task, context, output_schema):
        self.call_count += 1

        if self.should_fail and self.call_count > self.fail_after_retries:
            raise Exception("Fake generation failure")

        # Return a valid parsed output
        return ParsedNoteOutput(
            items=[
                ParsedItem(
                    item_type="IDIOM",
                    text="break the ice",
                    definition="To initiate conversation",
                    example_sentence="Let me break the ice.",
                    source_excerpt="Let me break the ice.",
                )
            ]
        )

    def generate_sync(self, task, context, output_schema):
        """Sync counterpart of generate().

        IngestionService calls ollama_adapter.ollama_adapter.generate_sync()
        directly (not the async generate()), so this is the method that
        actually needs to be patched onto the mocked adapter for these
        tests to exercise the real failure/success path.
        """
        self.call_count += 1

        if self.should_fail and self.call_count > self.fail_after_retries:
            raise Exception("Fake generation failure")

        return ParsedNoteOutput(
            items=[
                ParsedItem(
                    item_type="IDIOM",
                    text="break the ice",
                    definition="To initiate conversation",
                    example_sentence="Let me break the ice.",
                    source_excerpt="Let me break the ice.",
                )
            ]
        )


@pytest.fixture
def temp_note(tmp_path):
    """Create a temporary note file."""
    note_file = tmp_path / "test_note.md"
    note_file.write_text("Break the ice means to initiate conversation.")
    yield note_file
    if note_file.exists():
        note_file.unlink()


@pytest.fixture
def test_note(temp_note):
    """Create a test Note in the database."""
    import hashlib

    content = temp_note.read_text()
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    with Session() as session:
        note = Note(
            vault_path=str(temp_note),
            content_hash=content_hash,
            status=NoteStatus.NEW,
        )
        session.add(note)
        session.commit()
        note_id = note.id

    yield note_id

    # Cleanup. With generate_sync now actually mocked (see FakeGenerator),
    # the happy-path test really inserts a LearningItem pointing at this
    # note via source_note_id. Foreign keys are enforced (PRAGMA
    # foreign_keys=ON), so it has to be deleted before the Note itself or
    # this raises an IntegrityError.
    with Session() as session:
        from app.db.models.learning_item import LearningItem

        session.query(LearningItem).filter(
            LearningItem.source_note_id == note_id
        ).delete()
        note = session.query(Note).filter(Note.id == note_id).first()
        if note:
            session.delete(note)
        session.commit()


class TestIngestionServiceProcessNote:
    """Tests for IngestionService.process_note."""

    @pytest.mark.asyncio
    async def test_process_note_happy_path(self, test_note):
        """Test successful note processing."""
        fake_gen = FakeGenerator()

        with patch("app.ingestion.service.ollama_adapter.ollama_adapter") as mock_adapter:
            # IngestionService calls generate_sync(), not generate() - patch
            # the method that's actually on the call path.
            mock_adapter.generate_sync = fake_gen.generate_sync

            success, unresolved = IngestionService.process_note(test_note)

            assert success is True
            # High-confidence, complete item -> auto-inserted, nothing unresolved.
            assert unresolved == []

            # Verify note status changed
            with Session() as session:
                note = session.query(Note).filter(Note.id == test_note).first()
                assert note.status == NoteStatus.PROCESSED

    @pytest.mark.asyncio
    async def test_process_note_parse_failure(self, test_note):
        """Test note processing with parse failure."""
        fake_gen = FakeGenerator(should_fail=True, fail_after_retries=0)

        with patch("app.ingestion.service.ollama_adapter.ollama_adapter") as mock_adapter:
            # Same reasoning as the happy-path test - patch generate_sync().
            mock_adapter.generate_sync = fake_gen.generate_sync

            success, unresolved = IngestionService.process_note(test_note)

            assert success is False
            assert unresolved == []

            # Verify note status changed to PARSE_FAILED
            with Session() as session:
                note = session.query(Note).filter(Note.id == test_note).first()
                assert note.status == NoteStatus.PARSE_FAILED


class TestIngestionServiceValidation:
    """Tests for validation functions in IngestionService."""

    def test_mark_failed(self, test_note):
        """Test _mark_failed sets correct status."""
        with Session() as session:
            note = session.query(Note).filter(Note.id == test_note).first()
            note.status = NoteStatus.PARSING
            session.commit()

        # _mark_failed() just mutates the passed-in Note and commits on the
        # passed-in session - so both need to come from the *same* session.
        # The previous version fetched `note` from an already-closed
        # session above and paired it with a brand-new session here; since
        # `note` was never attached to that new session, the mutation never
        # got picked up by its commit.
        with Session() as session:
            note = session.query(Note).filter(Note.id == test_note).first()
            IngestionService._mark_failed(session, note)

        with Session() as session:
            note = session.query(Note).filter(Note.id == test_note).first()
            assert note.status == NoteStatus.PARSE_FAILED

    def test_is_potential_duplicate(self):
        """Test _is_potential_duplicate detection."""
        # Exact match
        assert IngestionService._is_potential_duplicate("hello", "hello") is True

        # Case insensitive
        assert IngestionService._is_potential_duplicate("Hello", "HELLO") is True

        # Different
        assert IngestionService._is_potential_duplicate("hello", "goodbye") is False

        # With whitespace
        assert IngestionService._is_potential_duplicate(" hello ", "hello") is True
