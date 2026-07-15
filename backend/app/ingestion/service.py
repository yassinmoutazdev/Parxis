"""Ingestion Service for processing notes from the vault.

Corresponds to ARCHITECTURE Section 6.1 (Ingestion Pipeline).
"""

import logging
from pathlib import Path
from typing import Any

from app.db.engine import Session
from app.db.models.note import Note, NoteStatus
from app.llm import ollama_adapter
from app.llm.schemas import ParsedNoteOutput
from app.llm.validation import validate_output

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for processing notes through the ingestion pipeline.

    Corresponds to ARCHITECTURE Section 6.1 (process_note sequence).
    """

    # Maximum retries for parsing failures
    MAX_PARSE_RETRIES = 2

    @classmethod
    def process_note(cls, note_id: int) -> bool:
        """Process a note through the ingestion pipeline.

        Corresponds to ARCHITECTURE Section 6.1 (process_note sequence):
        1. Set Note.status = PARSING
        2. Call Generator.generate(task="parse_note", ...)
        3. Handle schema/semantic validation failures
        4. On success: create ApprovalQueue rows

        Args:
            note_id: The ID of the Note to process

        Returns:
            True if processing succeeded, False otherwise
        """
        with Session() as session:
            # Fetch the note
            note = session.query(Note).filter(Note.id == note_id).first()
            if not note:
                logger.error(f"Note {note_id} not found")
                return False

            # Read file content
            file_path = Path(note.vault_path)
            if not file_path.exists():
                logger.error(f"Note file not found: {note.vault_path}")
                cls._mark_failed(session, note)
                return False

            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Error reading note file: {e}")
                cls._mark_failed(session, note)
                return False

            # Set status to PARSING
            note.status = NoteStatus.PARSING
            session.commit()

        # Attempt parsing with retries
        parse_result = cls._parse_note_with_retry(note_id, content)

        if parse_result is None:
            # Parsing failed after retries
            cls._mark_failed(session, note)
            return False

        # Validation passed - create approval queue entries
        cls._create_approval_queue_entries(note_id, parse_result)

        # Mark note as pending approval
        with Session() as session:
            note = session.query(Note).filter(Note.id == note_id).first()
            note.status = NoteStatus.PENDING_APPROVAL
            session.commit()

        logger.info(f"Note {note_id} processed successfully")
        return True

    @classmethod
    def _parse_note_with_retry(
        cls, note_id: int, content: str
    ) -> ParsedNoteOutput | None:
        """Parse a note with retry on validation failure.

        Args:
            note_id: The note ID
            content: The note content

        Returns:
            ParsedNoteOutput if successful, None if failed
        """
        from app.llm.interface import TaskType

        # Get recent item texts for deduplication awareness
        recent_items = cls._get_recent_item_texts()

        # Build context
        context = {
            "note_content": content,
            "recent_item_texts": recent_items,
        }

        for attempt in range(cls.MAX_PARSE_RETRIES + 1):
            try:
                # Call the generator
                result = ollama_adapter.ollama_adapter.generate(
                    task=TaskType.PARSE_NOTE,
                    context=context,
                    output_schema=ParsedNoteOutput,
                )

                # Validate the output
                validated_result, warnings = validate_output(
                    task=TaskType.PARSE_NOTE,
                    output=result,
                    context={"note_content": content},
                )

                if warnings:
                    logger.warning(
                        f"Validation warnings for note {note_id}: {warnings}"
                    )

                return validated_result

            except Exception as e:
                logger.warning(f"Parse attempt {attempt + 1} failed: {e}")

                if attempt < cls.MAX_PARSE_RETRIES:
                    # Retry with correction instruction
                    correction = cls._get_correction_instruction(warnings)
                    if correction:
                        context["note_content"] += f"\n\n{correction}"
                    continue

        return None

    @classmethod
    def _get_recent_item_texts(cls, limit: int = 50) -> list[str]:
        """Get recent learning item texts for deduplication awareness.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of recent item texts
        """
        from app.db.models.learning_item import LearningItem

        with Session() as session:
            items = (
                session.query(LearningItem.text)
                .order_by(LearningItem.created_at.desc())
                .limit(limit)
                .all()
            )
            return [item[0] for item in items]

    @classmethod
    def _get_correction_instruction(cls, warnings: list[str]) -> str | None:
        """Get correction instruction based on validation warnings.

        Args:
            warnings: List of validation warnings

        Returns:
            Correction instruction string, or None if no specific correction
        """
        if not warnings:
            return None

        # Build a correction instruction from the warnings
        instruction = "Please correct the following issues:\n"
        for warning in warnings:
            instruction += f"- {warning}\n"

        return instruction

    @classmethod
    def _mark_failed(cls, session, note: Note) -> None:
        """Mark a note as PARSE_FAILED.

        Args:
            session: The database session
            note: The note to mark as failed
        """
        note.status = NoteStatus.PARSE_FAILED
        session.commit()
        logger.error(f"Note {note.id} marked as PARSE_FAILED")

    @classmethod
    def _create_approval_queue_entries(
        cls, note_id: int, parsed_output: ParsedNoteOutput
    ) -> None:
        """Create ApprovalQueue entries from parsed note output.

        Corresponds to ARCHITECTURE Section 6.2 (create ApprovalQueue step).

        Args:
            note_id: The note ID
            parsed_output: The parsed note output
        """
        from app.db.engine import Session
        from app.db.models.approval import ApprovalQueue, ApprovalSourceType

        # Get similar items for duplicate detection
        existing_items = cls._find_similar_items(parsed_output)

        with Session() as session:
            for item in parsed_output.items:
                # Check for potential duplicate
                possible_duplicate_of = None
                if existing_items:
                    # Find best match
                    for existing in existing_items:
                        if cls._is_potential_duplicate(item.text, existing.text):
                            possible_duplicate_of = existing.id
                            break

                # Create approval queue entry using actual model fields
                queue_entry = ApprovalQueue(
                    source_type=ApprovalSourceType.NOTE_PARSE,
                    source_id=note_id,
                    item_type=item.item_type,
                    extracted_text=item.text,
                    explanation=item.definition,
                    example_sentence=item.example_sentence,
                    source_context=item.source_excerpt,
                    possible_duplicate_of=possible_duplicate_of,
                )
                session.add(queue_entry)

            session.commit()

        logger.info(f"Created {len(parsed_output.items)} approval queue entries")

    @classmethod
    def _find_similar_items(
        cls, parsed_output: ParsedNoteOutput
    ) -> list[Any]:
        """Find similar items for duplicate detection.

        Args:
            parsed_output: The parsed note output

        Returns:
            List of similar LearningItems
        """
        # Import duplicate detection
        from app.ingestion import duplicate_detection

        all_similar = []

        for item in parsed_output.items:
            similar = duplicate_detection.find_similar(item.text)
            all_similar.extend(similar)

        return all_similar

    @classmethod
    def _is_potential_duplicate(cls, text1: str, text2: str) -> bool:
        """Check if two texts might be duplicates (case-insensitive).

        Args:
            text1: First text
            text2: Second text

        Returns:
            True if potential duplicate
        """
        return text1.lower().strip() == text2.lower().strip()
