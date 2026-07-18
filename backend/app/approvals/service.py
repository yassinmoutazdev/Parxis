"""Approval Service for managing approval queue items.

Corresponds to ARCHITECTURE Section 6.2 (Approval Action) and Section 10.2 (ApprovalQueue state machine).
"""

import logging
from datetime import datetime
from typing import Any

from app.backup.service import BackupService
from app.db.engine import Session
from app.db.models.approval import ApprovalQueue, ApprovalStatus
from app.db.models.learning_correction import LearningCorrection
from app.db.models.learning_item import ItemType, LearningItem

logger = logging.getLogger(__name__)


class ApprovalError(Exception):
    """Base exception for approval service errors."""

    pass


class AlreadyApprovedError(ApprovalError):
    """Raised when attempting to approve an already-approved item."""

    pass


def _convert_item_type(item_type_str: str) -> ItemType | None:
    """Convert string item_type to ItemType enum.

    Args:
        item_type_str: The item type string from ApprovalQueue

    Returns:
        ItemType enum if valid, None for corrections
    """
    try:
        return ItemType(item_type_str)
    except ValueError:
        # item_type_str is "CORRECTION" or similar - will result in LearningCorrection
        return None


class ApprovalService:
    """Service for managing approval queue items.

    Corresponds to ARCHITECTURE Section 6.2 (Approval Action sequence):
    - approve() / approve_edited(): creates LearningItem or LearningCorrection
    - reject(): terminal status transition, no new row created

    Double-approval guard implemented per ADR-11 (Section 11.1).
    """

    @classmethod
    def approve(
        cls, approval_id: int, edited_payload: dict[str, Any] | None = None
    ) -> int:
        """Approve an approval queue item.

        Creates a LearningItem or LearningCorrection depending on item_type,
        updates ApprovalQueue status to APPROVED or EDITED_APPROVED,
        and commits the transaction.

        Args:
            approval_id: The ID of the ApprovalQueue item to approve
            edited_payload: Optional edited values (for approve_edited flow)

        Returns:
            The ID of the created LearningItem or LearningCorrection

        Raises:
            ApprovalError: If the item is not found or already processed
            AlreadyApprovedError: If the item is not in PENDING status
        """
        with Session() as session:
            # Fetch the approval queue row
            approval = session.query(ApprovalQueue).filter(
                ApprovalQueue.id == approval_id
            ).first()

            if not approval:
                raise ApprovalError(f"ApprovalQueue item {approval_id} not found")

            # Double-approval guard - check status inside transaction
            if approval.status != ApprovalStatus.PENDING:
                raise AlreadyApprovedError(
                    f"ApprovalQueue item {approval_id} is already "
                    f"in status {approval.status.value}"
                )

            # Determine the payload to use (edited or original)
            if edited_payload:
                payload = edited_payload
                new_status = ApprovalStatus.EDITED_APPROVED
            else:
                payload = {
                    "extracted_text": approval.extracted_text,
                    "explanation": approval.explanation,
                    "example_sentence": approval.example_sentence,
                }
                new_status = ApprovalStatus.APPROVED

            # Determine whether to create LearningItem or LearningCorrection
            item_type = _convert_item_type(approval.item_type)

            created_id: int

            if item_type is None:
                # item_type is "CORRECTION" - create LearningCorrection
                correction = LearningCorrection(
                    wrong_form=payload.get("wrong_form", approval.extracted_text),
                    correct_form=payload.get("correct_form", ""),
                    explanation=payload.get("explanation", approval.explanation),
                    example_sentence=payload.get(
                        "example_sentence", approval.example_sentence
                    ),
                    source_note_id=approval.source_id
                    if approval.source_type.value == "NOTE_PARSE"
                    else None,
                    source_writing_evaluation_id=approval.source_id
                    if approval.source_type.value == "WRITING_FEEDBACK"
                    else None,
                    source_approval_id=approval.id,
                )
                session.add(correction)
                session.flush()  # Get the ID
                created_id = correction.id
            else:
                # Create LearningItem with mastery_score=0.3 per PRD Section 17.3
                item = LearningItem(
                    item_type=item_type,
                    text=payload.get("extracted_text", approval.extracted_text),
                    definition=payload.get("explanation", approval.explanation),
                    example_sentence=payload.get(
                        "example_sentence", approval.example_sentence
                    ),
                    source_note_id=approval.source_id
                    if approval.source_type.value == "NOTE_PARSE"
                    else None,
                    source_approval_id=approval.id,
                    mastery_score=0.3,  # PRD Section 17.3
                    review_count=0,
                )
                session.add(item)
                session.flush()  # Get the ID
                created_id = item.id

            # Update ApprovalQueue status
            approval.status = new_status
            approval.reviewed_at = datetime.utcnow()

            # Commit the transaction
            session.commit()

            # Post-commit: check and backup if needed (idempotent)
            try:
                BackupService.check_and_backup_if_needed()
            except Exception as e:
                logger.warning(f"Post-commit backup check failed: {e}")

            logger.info(
                f"Approved approval {approval_id}, created {item_type or 'LearningCorrection'} with id {created_id}"
            )

            return created_id

    @classmethod
    def reject(cls, approval_id: int) -> None:
        """Reject an approval queue item.

        Terminal status transition - no LearningItem or LearningCorrection row created.
        The row is retained for audit purposes.

        Args:
            approval_id: The ID of the ApprovalQueue item to reject

        Raises:
            ApprovalError: If the item is not found
            AlreadyApprovedError: If the item is not in PENDING status
        """
        with Session() as session:
            # Fetch the approval queue row
            approval = session.query(ApprovalQueue).filter(
                ApprovalQueue.id == approval_id
            ).first()

            if not approval:
                raise ApprovalError(f"ApprovalQueue item {approval_id} not found")

            # Double-approval guard - check status inside transaction
            if approval.status != ApprovalStatus.PENDING:
                raise AlreadyApprovedError(
                    f"ApprovalQueue item {approval_id} is already "
                    f"in status {approval.status.value}"
                )

            # Update status to REJECTED (terminal)
            approval.status = ApprovalStatus.REJECTED
            approval.reviewed_at = datetime.utcnow()

            # Commit the transaction
            session.commit()

            # Post-commit: check and backup if needed (idempotent)
            try:
                BackupService.check_and_backup_if_needed()
            except Exception as e:
                logger.warning(f"Post-commit backup check failed: {e}")

            logger.info(f"Rejected approval {approval_id}")
