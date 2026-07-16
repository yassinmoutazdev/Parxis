"""Integration tests for ApprovalService.

Tests the approve/reject transitions and the double-approval guard.
Corresponds to ARCHITECTURE Section 10.2 (ApprovalQueue state machine).
"""

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session

# Import all models to ensure tables are registered with correct foreign key order
from app.db.models.source import Source, Lesson  # Note depends on Lesson
from app.db.models.note import Note
from app.db.models.approval import ApprovalQueue, ApprovalSourceType, ApprovalStatus
from app.db.models.learning_item import LearningItem, ItemType, Tag, LearningItemTag
from app.db.models.learning_correction import LearningCorrection
from app.db.models.performance_error import PerformanceError, PerformanceErrorSource
from app.db.models.quiz import QuizSession, QuizQuestion
from app.db.models.writing import WritingPrompt, WritingSubmission, WritingEvaluation
from app.db.models.report import WeeklyReport
from app.db.models.system import AuditLog
from app.approvals.service import ApprovalService, AlreadyApprovedError, ApprovalError


@pytest.fixture
def test_engine():
    """Create a file-based SQLite engine for testing."""
    # Create a temporary database file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    yield engine

    # Cleanup
    engine.dispose()
    os.unlink(path)


@pytest.fixture
def test_session(test_engine, monkeypatch):
    """Create a session for testing and patch the service to use it."""
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Patch the Session class in the approvals service module to use our test engine
    import app.approvals.service as service_module

    original_session = service_module.Session

    class TestDBSession:
        """Test session wrapper."""

        def __enter__(self):
            self._session = TestSession()
            return self._session

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self._session:
                self._session.close()

    monkeypatch.setattr(service_module, "Session", TestDBSession)

    with TestSession() as session:
        yield session


@pytest.fixture
def pending_approval(test_session):
    """Create a pending approval queue item for testing."""
    approval = ApprovalQueue(
        source_type=ApprovalSourceType.NOTE_PARSE,
        source_id=1,
        item_type="COLLOCATION",
        extracted_text="test collocation",
        explanation="test explanation",
        example_sentence="test example",
        source_context="source context",
        status=ApprovalStatus.PENDING,
    )
    test_session.add(approval)
    test_session.commit()
    test_session.refresh(approval)
    return approval


@pytest.fixture
def pending_correction(test_session):
    """Create a pending approval for a correction."""
    approval = ApprovalQueue(
        source_type=ApprovalSourceType.WRITING_FEEDBACK,
        source_id=2,
        item_type="CORRECTION",
        extracted_text="wrong form",
        explanation="explanation",
        example_sentence="example",
        source_context="source context",
        status=ApprovalStatus.PENDING,
    )
    test_session.add(approval)
    test_session.commit()
    test_session.refresh(approval)
    return approval


class TestApprovalTransitions:
    """Test approval status transitions."""

    def test_approve_creates_learning_item(self, pending_approval, test_session):
        """approve() should create a LearningItem and update status to APPROVED."""
        approval_id = pending_approval.id

        created_id = ApprovalService.approve(approval_id)

        # Refresh session to see changes from service's committed session
        test_session.expire_all()

        # Verify LearningItem was created
        item = test_session.get(LearningItem, created_id)
        assert item is not None
        assert item.item_type == ItemType.COLLOCATION
        assert item.text == "test collocation"
        assert item.definition == "test explanation"
        assert item.example_sentence == "test example"
        assert item.mastery_score == 0.3  # PRD Section 17.3
        assert item.review_count == 0

        # Verify ApprovalQueue status was updated
        approval = test_session.get(ApprovalQueue, approval_id)
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.reviewed_at is not None

    def test_approve_edited_creates_learning_item_with_edited_values(
        self, pending_approval, test_session
    ):
        """approve() with edited_payload should create LearningItem with edited values."""
        approval_id = pending_approval.id

        edited_payload = {
            "extracted_text": "edited text",
            "explanation": "edited explanation",
            "example_sentence": "edited example",
        }
        created_id = ApprovalService.approve(approval_id, edited_payload=edited_payload)

        # Refresh session to see changes from service's committed session
        test_session.expire_all()

        # Verify LearningItem was created with edited values
        item = test_session.get(LearningItem, created_id)
        assert item.text == "edited text"
        assert item.definition == "edited explanation"
        assert item.example_sentence == "edited example"

        # Verify status is EDITED_APPROVED
        approval = test_session.get(ApprovalQueue, approval_id)
        assert approval.status == ApprovalStatus.EDITED_APPROVED

    def test_approve_creates_learning_correction_for_correction_type(
        self, pending_correction, test_session
    ):
        """approve() should create LearningCorrection for CORRECTION item_type."""
        approval_id = pending_correction.id

        edited_payload = {
            "wrong_form": "wrong form",
            "correct_form": "correct form",
            "explanation": "correction explanation",
        }
        created_id = ApprovalService.approve(approval_id, edited_payload=edited_payload)

        # Verify LearningCorrection was created
        correction = test_session.get(LearningCorrection, created_id)
        assert correction is not None
        assert correction.wrong_form == "wrong form"
        assert correction.correct_form == "correct form"
        assert correction.explanation == "correction explanation"
        assert correction.source_approval_id == approval_id

    def test_reject_is_terminal_no_row_created(self, pending_approval, test_session):
        """reject() should not create LearningItem and should set status to REJECTED."""
        approval_id = pending_approval.id

        ApprovalService.reject(approval_id)

        # Refresh session to see changes from service's committed session
        test_session.expire_all()

        # Verify no LearningItem was created
        items = test_session.query(LearningItem).all()
        assert len(items) == 0

        # Verify status is REJECTED (terminal)
        approval = test_session.get(ApprovalQueue, approval_id)
        assert approval.status == ApprovalStatus.REJECTED
        assert approval.reviewed_at is not None

    def test_retain_approval_row_for_audit(self, pending_approval, test_session):
        """Rejected approval rows should be retained for audit."""
        approval_id = pending_approval.id

        ApprovalService.reject(approval_id)

        # Verify the row still exists
        approval = test_session.get(ApprovalQueue, approval_id)
        assert approval is not None
        assert approval.id == approval_id


class TestDoubleApprovalGuard:
    """Test the double-approval guard per ADR-11."""

    def test_double_approve_returns_409(self, pending_approval, test_session):
        """Second approve attempt should return 409 Conflict."""
        approval_id = pending_approval.id

        # First approve succeeds
        ApprovalService.approve(approval_id)

        # Second approve should raise AlreadyApprovedError
        with pytest.raises(AlreadyApprovedError) as exc_info:
            ApprovalService.approve(approval_id)

        assert "already" in str(exc_info.value).lower()

    def test_double_approve_no_duplicate_row(self, pending_approval, test_session):
        """Double approval should not create duplicate LearningItem."""
        approval_id = pending_approval.id

        # First approve
        first_id = ApprovalService.approve(approval_id)

        # Second attempt
        try:
            ApprovalService.approve(approval_id)
        except AlreadyApprovedError:
            pass

        # Verify only one LearningItem was created
        items = test_session.query(LearningItem).all()
        assert len(items) == 1
        assert items[0].id == first_id

    def test_approve_after_reject_is_rejected(self, pending_approval, test_session):
        """Approve after reject should return 409."""
        approval_id = pending_approval.id

        # First reject
        ApprovalService.reject(approval_id)

        # Then try to approve - should fail
        with pytest.raises(AlreadyApprovedError):
            ApprovalService.approve(approval_id)

    def test_reject_after_approve_is_rejected(self, pending_approval, test_session):
        """Reject after approve should return 409."""
        approval_id = pending_approval.id

        # First approve
        ApprovalService.approve(approval_id)

        # Then try to reject - should fail
        with pytest.raises(AlreadyApprovedError):
            ApprovalService.reject(approval_id)


class TestApprovalErrorHandling:
    """Test error handling."""

    def test_approve_nonexistent_raises_error(self, test_session):
        """Approving non-existent item should raise ApprovalError."""
        with pytest.raises(ApprovalError) as exc_info:
            ApprovalService.approve(99999)

        assert "not found" in str(exc_info.value).lower()

    def test_reject_nonexistent_raises_error(self, test_session):
        """Rejecting non-existent item should raise ApprovalError."""
        with pytest.raises(ApprovalError) as exc_info:
            ApprovalService.reject(99999)

        assert "not found" in str(exc_info.value).lower()