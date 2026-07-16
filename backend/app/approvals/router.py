"""Approval API router.

Corresponds to ARCHITECTURE Section 6.2 (sequence diagram) and PRD Section 10 (Flow 5).
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.approvals.service import (
    AlreadyApprovedError,
    ApprovalError,
    ApprovalService,
)
from app.db.models.approval import ApprovalQueue, ApprovalStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalResponse(BaseModel):
    """Response for approval actions."""

    learning_item_id: int | None = None
    message: str


class ApprovalEditPayload(BaseModel):
    """Payload for approve-edited endpoint."""

    extracted_text: str
    explanation: str | None = None
    example_sentence: str | None = None
    # For corrections
    wrong_form: str | None = None
    correct_form: str | None = None


class PendingCountResponse(BaseModel):
    """Response for pending count endpoint."""

    count: int


@router.get("")
async def list_approvals(
    status: ApprovalStatus = Query(default=ApprovalStatus.PENDING),
) -> list[dict[str, Any]]:
    """List approval queue items, optionally filtered by status.

    Returns pending items grouped by source_type+source_id.
    """
    from app.db.engine import Session

    with Session() as session:
        approvals = session.query(ApprovalQueue).filter(
            ApprovalQueue.status == status
        ).all()

        return [
            {
                "id": a.id,
                "source_type": a.source_type.value,
                "source_id": a.source_id,
                "item_type": a.item_type,
                "extracted_text": a.extracted_text,
                "explanation": a.explanation,
                "example_sentence": a.example_sentence,
                "source_context": a.source_context,
                "possible_duplicate_of": a.possible_duplicate_of,
                "status": a.status.value,
                "reviewed_payload": a.reviewed_payload,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
            }
            for a in approvals
        ]


@router.post("/{approval_id}/approve")
async def approve_item(approval_id: int) -> ApprovalResponse:
    """Approve an approval queue item.

    Creates a LearningItem or LearningCorrection depending on item_type.
    """
    try:
        created_id = ApprovalService.approve(approval_id)
        return ApprovalResponse(
            learning_item_id=created_id, message="Item approved successfully"
        )
    except ApprovalError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AlreadyApprovedError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{approval_id}/approve-edited")
async def approve_edited_item(
    approval_id: int, payload: ApprovalEditPayload
) -> ApprovalResponse:
    """Approve an approval queue item with edited values.

    Creates a LearningItem or LearningCorrection with the edited payload.
    """
    try:
        created_id = ApprovalService.approve(
            approval_id, edited_payload=payload.model_dump(exclude_none=True)
        )
        return ApprovalResponse(
            learning_item_id=created_id, message="Item approved with edits"
        )
    except ApprovalError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AlreadyApprovedError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{approval_id}/reject")
async def reject_item(approval_id: int) -> ApprovalResponse:
    """Reject an approval queue item.

    Terminal status transition - no LearningItem or LearningCorrection created.
    """
    try:
        ApprovalService.reject(approval_id)
        return ApprovalResponse(learning_item_id=None, message="Item rejected")
    except ApprovalError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AlreadyApprovedError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/batch/approve")
async def batch_approve(approval_ids: list[int]) -> list[ApprovalResponse]:
    """Approve multiple approval queue items in batch."""
    results = []
    for approval_id in approval_ids:
        try:
            created_id = ApprovalService.approve(approval_id)
            results.append(
                ApprovalResponse(
                    learning_item_id=created_id,
                    message=f"Item {approval_id} approved",
                )
            )
        except ApprovalError as e:
            results.append(
                ApprovalResponse(learning_item_id=None, message=str(e))
            )
        except AlreadyApprovedError as e:
            raise HTTPException(status_code=409, detail=str(e))
    return results


@router.post("/batch/approve-edited")
async def batch_approve_edited(
    payload: list[dict[str, Any]]
) -> list[ApprovalResponse]:
    """Approve multiple approval queue items with edited values in batch."""
    results = []
    for item in payload:
        approval_id = item.get("approval_id")
        edited = item.get("edited")
        if not approval_id:
            results.append(
                ApprovalResponse(
                    learning_item_id=None, message="Missing approval_id"
                )
            )
            continue
        try:
            created_id = ApprovalService.approve(approval_id, edited_payload=edited)
            results.append(
                ApprovalResponse(
                    learning_item_id=created_id,
                    message=f"Item {approval_id} approved with edits",
                )
            )
        except ApprovalError as e:
            results.append(
                ApprovalResponse(learning_item_id=None, message=str(e))
            )
        except AlreadyApprovedError as e:
            raise HTTPException(status_code=409, detail=str(e))
    return results


@router.post("/batch/reject")
async def batch_reject(approval_ids: list[int]) -> list[ApprovalResponse]:
    """Reject multiple approval queue items in batch."""
    results = []
    for approval_id in approval_ids:
        try:
            ApprovalService.reject(approval_id)
            results.append(
                ApprovalResponse(
                    learning_item_id=None, message=f"Item {approval_id} rejected"
                )
            )
        except ApprovalError as e:
            results.append(
                ApprovalResponse(learning_item_id=None, message=str(e))
            )
        except AlreadyApprovedError as e:
            raise HTTPException(status_code=409, detail=str(e))
    return results


@router.get("/pending-count")
async def get_pending_count() -> PendingCountResponse:
    """Get the count of pending approval items.

    Lightweight polling target referenced by ADR-08 for the frontend's
    normal refresh cadence.
    """
    from app.db.engine import Session

    with Session() as session:
        count = session.query(ApprovalQueue).filter(
            ApprovalQueue.status == ApprovalStatus.PENDING
        ).count()

        return PendingCountResponse(count=count)
