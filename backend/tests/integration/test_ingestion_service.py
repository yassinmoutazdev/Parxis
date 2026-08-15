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

    # Cleanup
    with Session() as session:
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
            mock_adapter.generate = fake_gen.generate

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
            mock_adapter.generate = fake_gen.generate

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

        IngestionService._mark_failed(
            Session().__enter__(),
            session.query(Note).filter(Note.id == test_note).first(),
        )

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
