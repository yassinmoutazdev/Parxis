"""Integration tests for RetrievalService and scheduler.

Tests select_eligible_items() and week-scoped queries.
"""

import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Import all models to ensure tables are registered
from app.db.models.source import Source, Lesson
from app.db.models.note import Note
from app.db.models.approval import ApprovalQueue, ApprovalSourceType, ApprovalStatus
from app.db.models.learning_item import LearningItem, ItemType, Tag, LearningItemTag
from app.db.models.learning_correction import LearningCorrection
from app.db.models.performance_error import PerformanceError, PerformanceErrorSource
from app.db.models.quiz import QuizSession, QuizQuestion
from app.db.models.writing import WritingPrompt, WritingSubmission, WritingEvaluation
from app.db.models.report import WeeklyReport
from app.db.models.system import AuditLog, Config
from app.retrieval.service import RetrievalService


@pytest.fixture
def test_engine():
    """Create a file-based SQLite engine for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    yield engine

    engine.dispose()
    os.unlink(path)


@pytest.fixture
def test_session(test_engine, monkeypatch):
    """Create a session for testing and patch the service to use it."""
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Patch Session in the retrieval module
    import app.retrieval.service as retrieval_module

    class TestDBSession:
        def __enter__(self):
            self._session = TestSession()
            return self._session

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self._session:
                self._session.close()

    monkeypatch.setattr(retrieval_module, "Session", TestDBSession)

    with TestSession() as session:
        yield session


class TestSelectEligibleItems:
    """Tests for select_eligible_items() function."""

    def test_empty_db_returns_empty(self, test_session):
        """Empty database returns empty list."""
        items = RetrievalService.select_eligible_items(size=5)
        assert items == []

    def test_all_due_returns_due(self, test_session):
        """All items due returns due items."""
        now = datetime.utcnow()

        # Create due items
        item1 = LearningItem(
            item_type=ItemType.COLLOCATION,
            text="test1",
            mastery_score=0.3,
            next_review_due=now - timedelta(days=1),
            source_approval_id=1,
        )
        item2 = LearningItem(
            item_type=ItemType.IDIOM,
            text="test2",
            mastery_score=0.4,
            next_review_due=now - timedelta(days=1),
            source_approval_id=2,
        )

        test_session.add(item1)
        test_session.add(item2)
        test_session.commit()

        items = RetrievalService.select_eligible_items(size=2)

        assert len(items) == 2
        texts = [i.text for i in items]
        assert "test1" in texts
        assert "test2" in texts

    def test_backfill_from_not_due(self, test_session):
        """Not enough due items backfills from not-due pool."""
        now = datetime.utcnow()

        # Create some due items
        due_item = LearningItem(
            item_type=ItemType.COLLOCATION,
            text="due item",
            mastery_score=0.3,
            next_review_due=now - timedelta(days=1),
            source_approval_id=1,
        )

        # Create not-due items
        not_due_item = LearningItem(
            item_type=ItemType.IDIOM,
            text="not due item",
            mastery_score=0.8,
            next_review_due=now + timedelta(days=10),
            source_approval_id=2,
        )

        test_session.add(due_item)
        test_session.add(not_due_item)
        test_session.commit()

        # Request 5 items but only 1 is due
        items = RetrievalService.select_eligible_items(size=5)

        assert len(items) == 2  # Should include both due and backfilled
        texts = [i.text for i in items]
        assert "due item" in texts
        assert "not due item" in texts

    def test_category_balance(self, test_session):
        """Category balance constraint is applied."""
        now = datetime.utcnow()

        # Create items of different categories
        items = []
        for i in range(5):
            item = LearningItem(
                item_type=ItemType.COLLOCATION,
                text=f"col{i}",
                mastery_score=0.3,
                next_review_due=now - timedelta(days=1),
                source_approval_id=i + 1,
            )
            items.append(item)

        for i in range(3):
            item = LearningItem(
                item_type=ItemType.IDIOM,
                text=f"idiom{i}",
                mastery_score=0.3,
                next_review_due=now - timedelta(days=1),
                source_approval_id=i + 100,
            )
            items.append(item)

        for item in items:
            test_session.add(item)
        test_session.commit()

        # Request items - should have balance between categories
        selected = RetrievalService.select_eligible_items(size=6)

        # Count items per category
        collocations = sum(1 for i in selected if i.item_type == ItemType.COLLOCATION)
        idioms = sum(1 for i in selected if i.item_type == ItemType.IDIOM)

        # Both categories should be represented (with 60% balance)
        assert collocations > 0
        assert idioms > 0


class TestWeekScopedQueries:
    """Tests for week-scoped query methods."""

    def test_items_created_between_empty(self, test_session):
        """No items in week returns empty list."""
        week_start = datetime(2024, 1, 1)
        week_end = datetime(2024, 1, 8)

        items = RetrievalService.items_created_between(week_start, week_end)

        assert items == []

    def test_items_created_between_returns_items(self, test_session):
        """Items created in week are returned."""
        week_start = datetime(2024, 1, 1)
        week_end = datetime(2024, 1, 8)

        # Create item within week
        item = LearningItem(
            item_type=ItemType.COLLOCATION,
            text="test",
            created_at=datetime(2024, 1, 5),
            source_approval_id=1,
        )
        test_session.add(item)
        test_session.commit()

        items = RetrievalService.items_created_between(week_start, week_end)

        assert len(items) == 1
        assert items[0].text == "test"

    def test_items_outside_week_not_included(self, test_session):
        """Items created outside week are not returned."""
        week_start = datetime(2024, 1, 1)
        week_end = datetime(2024, 1, 8)

        # Create item outside week
        item = LearningItem(
            item_type=ItemType.COLLOCATION,
            text="test",
            created_at=datetime(2024, 2, 1),
            source_approval_id=1,
        )
        test_session.add(item)
        test_session.commit()

        items = RetrievalService.items_created_between(week_start, week_end)

        assert items == []

    def test_quiz_summary_no_sessions(self, test_session):
        """Zero quiz sessions returns empty (not error) result."""
        week_start = datetime(2024, 1, 1)
        week_end = datetime(2024, 1, 8)

        summary = RetrievalService.quiz_summary_for_week(week_start, week_end)

        assert summary["total_sessions"] == 0
        assert summary["total_questions"] == 0
        assert summary["score"] is None

    def test_quiz_summary_with_sessions(self, test_session):
        """Quiz sessions are counted correctly."""
        week_start = datetime(2024, 1, 1)
        week_end = datetime(2024, 1, 8)

        # Create a completed session
        session = QuizSession(
            quiz_scope="AD_HOC",
            quiz_mode="RECALL",
            started_at=datetime(2024, 1, 5),
            completed_at=datetime(2024, 1, 5),
        )
        test_session.add(session)
        test_session.commit()
        test_session.refresh(session)

        # Add questions
        q1 = QuizQuestion(
            quiz_session_id=session.id,
            learning_item_id=1,
            question_type="RECALL",
            prompt="test prompt",
            correct_answer="answer",
            is_correct=True,
            graded_by="DETERMINISTIC",
        )
        q2 = QuizQuestion(
            quiz_session_id=session.id,
            learning_item_id=2,
            question_type="RECALL",
            prompt="test prompt 2",
            correct_answer="answer2",
            is_correct=False,
            graded_by="DETERMINISTIC",
        )
        test_session.add(q1)
        test_session.add(q2)
        test_session.commit()

        summary = RetrievalService.quiz_summary_for_week(week_start, week_end)

        assert summary["total_sessions"] == 1
        assert summary["total_questions"] == 2
        assert summary["correct_count"] == 1
        assert summary["incorrect_count"] == 1

    def test_mini_writing_summary_no_submissions(self, test_session):
        """Zero submissions returns empty (not error) result."""
        week_start = datetime(2024, 1, 1)
        week_end = datetime(2024, 1, 8)

        summary = RetrievalService.mini_writing_summary_for_week(week_start, week_end)

        assert summary["total_submissions"] == 0
        assert summary["average_score"] is None

    def test_mini_writing_summary_with_evaluations(self, test_session):
        """Writing submissions with evaluations are summarized."""
        week_start = datetime(2024, 1, 1)
        week_end = datetime(2024, 1, 8)

        # Create a submission
        submission = WritingSubmission(
            prompt_id=1,
            submission_type="MINI",
            submitted_text="test text",
            word_count=100,
            created_at=datetime(2024, 1, 5),
        )
        test_session.add(submission)
        test_session.commit()
        test_session.refresh(submission)

        # Create evaluation
        evaluation = WritingEvaluation(
            submission_id=submission.id,
            overall_score=0.75,
            created_at=datetime(2024, 1, 5),
        )
        test_session.add(evaluation)
        test_session.commit()

        summary = RetrievalService.mini_writing_summary_for_week(week_start, week_end)

        assert summary["total_submissions"] == 1
        assert summary["average_score"] == 0.75

    def test_performance_error_patterns_empty(self, test_session):
        """No errors returns empty list."""
        week_start = datetime(2024, 1, 1)
        week_end = datetime(2024, 1, 8)

        patterns = RetrievalService.performance_error_patterns(week_start, week_end)

        assert patterns == []

    def test_performance_error_patterns_grouped(self, test_session):
        """Errors are grouped by wrong_form."""
        week_start = datetime(2024, 1, 1)
        week_end = datetime(2024, 1, 8)

        # Create errors
        error1 = PerformanceError(
            learning_item_id=1,
            wrong_form="their",
            correct_form="there",
            explanation="confusion",
            source_type=PerformanceErrorSource.QUIZ,
            source_id=1,
            created_at=datetime(2024, 1, 5),
        )
        error2 = PerformanceError(
            learning_item_id=1,
            wrong_form="their",
            correct_form="there",
            explanation="confusion",
            source_type=PerformanceErrorSource.QUIZ,
            source_id=2,
            created_at=datetime(2024, 1, 5),
        )
        error3 = PerformanceError(
            learning_item_id=2,
            wrong_form="its",
            correct_form="it's",
            explanation="contraction",
            source_type=PerformanceErrorSource.WRITING_MINI,
            source_id=3,
            created_at=datetime(2024, 1, 5),
        )

        test_session.add(error1)
        test_session.add(error2)
        test_session.add(error3)
        test_session.commit()

        patterns = RetrievalService.performance_error_patterns(week_start, week_end)

        assert len(patterns) == 2

        # Find the "their" pattern
        their_pattern = next(p for p in patterns if p["wrong_form"] == "their")
        assert their_pattern["count"] == 2

        its_pattern = next(p for p in patterns if p["wrong_form"] == "its")
        assert its_pattern["count"] == 1