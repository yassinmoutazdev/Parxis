"""Ingestion Service for processing notes from the vault.

Corresponds to ARCHITECTURE Section 6.1 (Ingestion Pipeline).
"""

import logging
from pathlib import Path
from typing import Any

from app.db.engine import Session
from app.db.models.note import Note, NoteSource, NoteStatus
from app.llm import ollama_adapter
from app.llm.schemas import ParsedItem, ParsedNoteOutput
from app.llm.validation import validate_output

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for processing notes through the ingestion pipeline.

    Corresponds to ARCHITECTURE Section 6.1 (process_note sequence).
    """

    # Maximum retries for parsing failures
    MAX_PARSE_RETRIES = 2

    @classmethod
    def process_note(cls, note_id: int) -> tuple[bool, list[ParsedItem]]:
        """Process a note through the ingestion pipeline.

        No approval queue (Part H). Extracted items are either auto-inserted,
        silently dropped (duplicates, or vault-sourced items still
        unresolved after one retry), or - for chat-sourced notes only -
        returned as still-unresolved so the caller (the chat coach) can ask
        the user for clarification in its next reply.

        Args:
            note_id: The ID of the Note to process

        Returns:
            (success, unresolved_items) - unresolved_items is always empty
            for vault-sourced notes (those are dropped, not surfaced) and
            only non-empty for chat-sourced notes that still need a human
            answer after the automatic retry.
        """
        with Session() as session:
            # Fetch the note
            note = session.query(Note).filter(Note.id == note_id).first()
            if not note:
                logger.error(f"Note {note_id} not found")
                return False, []

            # Chat-sourced notes carry their text directly (no file on disk);
            # vault-sourced notes are read from the watched file.
            if note.source == NoteSource.CHAT:
                content = note.content or ""
                if not content.strip():
                    logger.error(f"Chat note {note_id} has no content")
                    cls._mark_failed(session, note)
                    return False, []
            else:
                file_path = Path(note.vault_path)
                if not file_path.exists():
                    logger.error(f"Note file not found: {note.vault_path}")
                    cls._mark_failed(session, note)
                    return False, []

                try:
                    content = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.error(f"Error reading note file: {e}")
                    cls._mark_failed(session, note)
                    return False, []

            note_source = note.source

            # Set status to PARSING
            note.status = NoteStatus.PARSING
            session.commit()

        # Attempt parsing with retries
        parse_result = cls._parse_note_with_retry(note_id, content)

        if parse_result is None:
            # Parsing failed after retries
            with Session() as session:
                note = session.query(Note).filter(Note.id == note_id).first()
                cls._mark_failed(session, note)
            return False, []

        # Validation passed - route extracted items (auto-insert, silent
        # skip, or - for chat-sourced notes only - hand back items still
        # needing clarification after one retry).
        unresolved = cls._route_extracted_items(
            note_id, parse_result, content, source=note_source
        )

        # Mark note as processed either way. Unresolved chat items are
        # handled by the caller as part of the same conversation turn, not
        # tracked as a note-level pending state.
        with Session() as session:
            note = session.query(Note).filter(Note.id == note_id).first()
            note.status = NoteStatus.PROCESSED
            session.commit()

        logger.info(f"Note {note_id} processed successfully")
        return True, unresolved

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
                # Call the generator (sync wrapper)
                result = ollama_adapter.ollama_adapter.generate_sync(
                    task=TaskType.PARSE_NOTE,
                    context=context,
                    output_schema=ParsedNoteOutput,
                )

                logger.info(f"LLM result type: {type(result)}, value: {result}")

                # Validate the output
                validated_result, warnings = validate_output(
                    task=TaskType.PARSE_NOTE,
                    output=result,
                    context={"note_content": content},
                )

                logger.info(f"Validation result type: {type(validated_result)}")

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
    def _route_extracted_items(
        cls,
        note_id: int,
        parsed_output: ParsedNoteOutput,
        note_content: str,
        source: NoteSource = NoteSource.VAULT,
    ) -> list[ParsedItem]:
        """Route extracted items: auto-insert, silently drop, or (chat only)
        hand back for clarification. No approval queue (Part H).

        Gating rule (unchanged from Part E): an item auto-inserts directly
        when ALL hold: not a likely duplicate, confidence is not "low",
        and it's complete (definition + example_sentence present for
        non-CORRECTION types).

        Items that fail that check get ONE retry via _retry_flagged_items
        (duplicates are never retried - they're just dropped, since the
        content is already covered by an existing item). After retry:
        - still flagged AND source == VAULT -> dropped silently (no one is
          watching a file-sync event to answer a question).
        - still flagged AND source == CHAT -> returned to the caller so the
          coach can ask the user for clarification in its next reply.

        Args:
            note_id: The note ID
            parsed_output: The parsed note output
            note_content: The raw source text (used if a retry is needed)
            source: Where this note came from - determines what happens to
                items still flagged after retry

        Returns:
            Items still needing clarification. Always empty for
            source=VAULT (those are dropped, not surfaced).
        """
        from app.db.models.learning_item import ItemType, LearningItem

        existing_items = cls._find_similar_items(parsed_output)

        to_insert: list[ParsedItem] = []
        to_retry: list[ParsedItem] = []
        duplicate_skipped_count = 0

        for item in parsed_output.items:
            if cls._matches_existing(item, existing_items):
                duplicate_skipped_count += 1
                continue
            if cls._needs_review(item):
                to_retry.append(item)
            else:
                to_insert.append(item)

        unresolved: list[ParsedItem] = []
        if to_retry:
            retried_items = cls._retry_flagged_items(to_retry, note_content)
            retried_texts = {i.text for i in retried_items}

            for item in retried_items:
                if cls._needs_review(item):
                    unresolved.append(item)
                else:
                    to_insert.append(item)

            # The model may drop an item entirely on retry instead of
            # re-emitting a (still-flawed) version of it - treat that the
            # same as "still needs review".
            for original in to_retry:
                if original.text not in retried_texts:
                    unresolved.append(original)

        inserted_count = 0
        with Session() as session:
            for item in to_insert:
                cls._insert_learning_item(session, item, note_id=note_id)
                inserted_count += 1
            session.commit()

        if source == NoteSource.VAULT:
            dropped_count = len(unresolved)
            logger.info(
                f"Routed items: {inserted_count} inserted, "
                f"{duplicate_skipped_count} duplicate-skipped, "
                f"{dropped_count} dropped after retry (vault source, no one to ask)"
            )
            return []

        logger.info(
            f"Routed items: {inserted_count} inserted, "
            f"{duplicate_skipped_count} duplicate-skipped, "
            f"{len(unresolved)} need clarification (chat source)"
        )
        return unresolved

    @staticmethod
    def _insert_learning_item(session: Session, item: ParsedItem, note_id: int | None) -> None:
        """Insert a resolved item as a LearningItem or LearningCorrection.

        Args:
            session: Open DB session (caller commits)
            item: The item to insert
            note_id: Source note ID, if any (None for writing-feedback-sourced items)
        """
        from app.db.models.learning_correction import LearningCorrection
        from app.db.models.learning_item import ItemType, LearningItem

        if item.item_type == "CORRECTION":
            session.add(
                LearningCorrection(
                    wrong_form=item.wrong_form or item.text,
                    correct_form=item.correct_form or "",
                    explanation=item.definition,
                    example_sentence=item.example_sentence,
                    source_note_id=note_id,
                )
            )
        else:
            session.add(
                LearningItem(
                    item_type=ItemType(item.item_type),
                    text=item.text,
                    definition=item.definition,
                    example_sentence=item.example_sentence,
                    source_note_id=note_id,
                    mastery_score=0.3,
                    review_count=0,
                    correct_count=0,
                    incorrect_count=0,
                    ease_factor=2.5,
                    interval_days=0,
                    suspended=False,
                )
            )

    @classmethod
    def _needs_review(cls, item: ParsedItem) -> bool:
        """True if an item is low-confidence or incomplete (not a duplicate check)."""
        is_low_confidence = item.confidence == "low"
        is_incomplete = item.item_type != "CORRECTION" and (
            not item.definition
            or not item.definition.strip()
            or not item.example_sentence
            or not item.example_sentence.strip()
        )
        return is_low_confidence or is_incomplete

    @classmethod
    def _matches_existing(cls, item: ParsedItem, existing_items: list[Any]) -> bool:
        """True if item looks like a duplicate of something already in the DB."""
        return any(cls._is_potential_duplicate(item.text, existing.text) for existing in existing_items)

    @classmethod
    def _describe_issue(cls, item: ParsedItem) -> str:
        """Human-readable description of why an item needs review, for the retry prompt."""
        if item.confidence == "low":
            return item.low_confidence_reason or "low confidence, no reason given"
        missing = []
        if not item.definition or not item.definition.strip():
            missing.append("definition")
        if not item.example_sentence or not item.example_sentence.strip():
            missing.append("example_sentence")
        return f"missing {' and '.join(missing)}" if missing else "flagged for review"

    @classmethod
    def _retry_flagged_items(
        cls, flagged_items: list[ParsedItem], source_content: str
    ) -> list[ParsedItem]:
        """One targeted retry for items flagged as low-confidence or incomplete.

        Reuses the PARSE_NOTE task, appending a targeted instruction asking
        the model to re-extract only the flagged items, resolving the
        specific issue noted for each (low_confidence_reason, or the
        missing field). Shared by both note ingestion and writing-feedback
        extraction - source_content is note text or submission text.

        Args:
            flagged_items: Items that failed the auto-insert gate
            source_content: The original text the items were drawn from

        Returns:
            The model's corrected items (may be fewer than flagged_items if
            the model drops one instead of fixing it - callers should treat
            a missing text as still-unresolved).
        """
        from app.llm.interface import TaskType

        if not flagged_items:
            return []

        issue_lines = "\n".join(
            f'- "{item.text}": {cls._describe_issue(item)}' for item in flagged_items
        )
        retry_content = (
            f"{source_content}\n\n---\n"
            "RETRY: re-extract ONLY the following items, resolving the specific "
            "issue noted for each. Return just these corrected items:\n"
            f"{issue_lines}"
        )

        try:
            result = ollama_adapter.ollama_adapter.generate_sync(
                task=TaskType.PARSE_NOTE,
                context={"note_content": retry_content, "recent_item_texts": []},
                output_schema=ParsedNoteOutput,
            )
            validated_result, _ = validate_output(
                task=TaskType.PARSE_NOTE,
                output=result,
                context={"note_content": retry_content},
            )
            return validated_result.items
        except Exception as e:
            logger.warning(f"Retry for flagged items failed: {e}")
            return []

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
