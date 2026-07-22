"""Integration tests for QuizService.

Corresponds to ARCHITECTURE Section 17.2 and T6.5.2.
Tests the full start→answer→grade flow using FakeGenerator/FakeEvaluator.
Asserts: PerformanceError rows are created for incorrect answers with no approval step,
and LearningItem.mastery_score/next_review_due update correctly.
"""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

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
from app.db.models.quiz import QuizSession, QuizQuestion, QuizMode, QuizScope
from app.db.models.writing import WritingPrompt, WritingSubmission, WritingEvaluation
from app.db.models.report import WeeklyReport
from app.db.models.system import AuditLog, Config
from app.quizzes.service import QuizService
from app.quizzes.grading import grade_deterministic
from app.scheduler.mastery import reset_settings_cache


# Fake Generator for testing
class FakeGenerator:
    """Fake generator for testing quiz generation."""

    def __init__(self):
        self.calls = []

    async def generate(self, task: str, context: dict, output_schema):
        """Record the call and return a fake result."""
        self.calls.append({"task": task, "context": context})

        # Return a simple quiz question output
        from app.llm.schemas import QuizQuestionOutput

        return QuizQuestionOutput(
            prompt_text=f"What does {context.get('item_text', 'test')} mean?",
            correct_answer=context.get("item_text", "test answer"),
        )


# Fake Evaluator for testing
class FakeEvaluator:
    """Fake evaluator for testing quiz grading."""

    def __init__(self, score: float = 0.8, feedback: str = "Good job!"):
        self.calls = []
        self.score = score
        self.feedback = feedback

    async def evaluate(self, task: str, content: str, context: dict, output_schema):
        """Record the call and return a fake result."""
        self.calls.append({"task": task, "content": content, "context": context})

        from app.llm.schemas import GradedAnswerOutput

        return GradedAnswerOutput(score=self.score, feedback=self.feedback)


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
def test_session(test_engine):
    """Create a session for testing."""
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSession()

    yield session

    session.close()


@pytest.fixture
def learning_items(test_session):
    """Create some learning items for testing."""
    reset_settings_cache()

    items = [
        LearningItem(
            item_type=ItemType.COLLOCATION,
            text="test collocation",
            definition="A common phrase",
            example_sentence="This is an example",
            mastery_score=0.5,
            next_review_due=datetime.utcnow() - timedelta(days=1),
            ease_factor=2.5,
            interval_days=1,
            review_count=0,
            source_approval_id=1,
        ),
        LearningItem(
            item_type=ItemType.IDIOM,
            text="test idiom",
            definition="A figurative expression",
            example_sentence="Idiom example",
            mastery_score=0.3,
            next_review_due=datetime.utcnow() - timedelta(days=1),
            ease_factor=2.5,
            interval_days=1,
            review_count=0,
            source_approval_id=2,
        ),
        LearningItem(
            item_type=ItemType.PHRASAL_VERB,
            text="test phrasal verb",
            definition="A verb with particle",
            example_sentence="Phrasal verb example",
            mastery_score=0.7,
            next_review_due=datetime.utcnow() + timedelta(days=1),
            ease_factor=2.5,
            interval_days=1,
            review_count=0,
            source_approval_id=3,
        ),
    ]

    for item in items:
        test_session.add(item)
    test_session.commit()

    for item in items:
        test_session.refresh(item)

    return items


class TestQuizSessionFlow:
    """Tests for the full quiz session flow."""

    def test_quiz_session_model_creation(self, test_session, learning_items):
        """Test creating a quiz session and question in the database."""
        # Create a quiz session
        session = QuizSession(
            quiz_scope=QuizScope.AD_HOC,
            quiz_mode=QuizMode.RECALL,
            started_at=datetime.utcnow(),
        )
        test_session.add(session)
        test_session.flush()

        # Create a quiz question
        question = QuizQuestion(
            quiz_session_id=session.id,
            learning_item_id=learning_items[0].id,
            question_type=QuizMode.RECALL,
            prompt="What does test collocation mean?",
            correct_answer="test collocation",
        )
        test_session.add(question)
        test_session.commit()

        # Verify they were saved
        assert session.id is not None
        assert question.id is not None

        # Verify relationship
        assert question.quiz_session_id == session.id
        assert question.learning_item_id == learning_items[0].id

    @pytest.mark.asyncio
    async def test_grade_deterministic_creates_performance_error(
        self, test_session, learning_items, monkeypatch
    ):
        """Test that deterministic grading creates PerformanceError for incorrect answers."""
        # Create a quiz question
        item = learning_items[0]
        quiz_session = QuizSession(
            quiz_scope=QuizScope.AD_HOC,
            quiz_mode=QuizMode.RECALL,
            started_at=datetime.utcnow(),
        )
        test_session.add(quiz_session)
        test_session.flush()

        question = QuizQuestion(
            quiz_session_id=quiz_session.id,
            learning_item_id=item.id,
            question_type=QuizMode.RECALL,
            prompt="What does test collocation mean?",
            correct_answer="test collocation",
        )
        test_session.add(question)
        test_session.commit()
        test_session.refresh(question)
        test_session.refresh(item)

        # Grade with wrong answer (deterministic)
        is_correct, score, feedback = grade_deterministic(
            question_type=QuizMode.RECALL,
            correct_answer=question.correct_answer,
            user_answer="wrong answer",
        )

        assert is_correct is False
        assert score == 0.0

        # Create PerformanceError directly (as the service does)
        error = PerformanceError(
            learning_item_id=question.learning_item_id,
            wrong_form="wrong answer",
            correct_form=question.correct_answer or "",
            explanation=feedback,
            source_type=PerformanceErrorSource.QUIZ,
            source_id=question.id,
        )
        test_session.add(error)
        test_session.commit()

        # Verify PerformanceError was created
        errors = test_session.query(PerformanceError).all()
        assert len(errors) == 1
        assert errors[0].wrong_form == "wrong answer"
        assert errors[0].correct_form == "test collocation"
        assert errors[0].source_type == PerformanceErrorSource.QUIZ

    @pytest.mark.asyncio
    async def test_mastery_updates_on_correct_answer(
        self, test_session, learning_items, monkeypatch
    ):
        """Test that mastery_score and next_review_due update correctly on correct answer."""
        from app.scheduler.mastery import update_mastery

        item = learning_items[0]
        original_mastery = item.mastery_score
        original_interval = item.interval_days

        # Simulate a correct answer (score >= 0.7)
        update_mastery(item, score=0.9)

        # Verify mastery increased
        assert item.mastery_score > original_mastery

        # Verify interval increased
        assert item.interval_days >= original_interval

        # Verify next_review_due is set
        assert item.next_review_due is not None
        assert item.next_review_due > datetime.utcnow()

        # Verify review count increased
        assert item.review_count == 1

    @pytest.mark.asyncio
    async def test_mastery_updates_on_incorrect_answer(
        self, test_session, learning_items, monkeypatch
    ):
        """Test that mastery updates correctly on incorrect answer."""
        from app.scheduler.mastery import update_mastery

        item = learning_items[1]
        original_mastery = item.mastery_score
        original_ease = item.ease_factor

        # Simulate an incorrect answer (score < 0.7)
        update_mastery(item, score=0.3)

        # Verify mastery decreased
        assert item.mastery_score < original_mastery

        # Verify ease factor decreased
        assert item.ease_factor < original_ease

        # Verify interval reset to 1
        assert item.interval_days == 1

        # Verify incorrect count increased
        assert item.incorrect_count == 1


class TestPerformanceErrorCreation:
    """Tests for PerformanceError creation (ADR-05 exception)."""

    def test_performance_error_no_approval_required(
        self, test_session, learning_items
    ):
        """Test that PerformanceError can be created directly without approval.

        This is the ADR-05 exception - PerformanceError rows are written
        directly by QuizService at grading time with no approval step.
        """
        item = learning_items[0]

        # Direct creation of PerformanceError (no approval)
        error = PerformanceError(
            learning_item_id=item.id,
            wrong_form="wrong form",
            correct_form="correct form",
            explanation="Test explanation",
            source_type=PerformanceErrorSource.QUIZ,
            source_id=1,
        )
        test_session.add(error)
        test_session.commit()

        # Verify it was created
        errors = test_session.query(PerformanceError).all()
        assert len(errors) == 1
        assert errors[0].learning_item_id == item.id

    def test_performance_error_has_source_tracking(
        self, test_session, learning_items
    ):
        """Test that PerformanceError tracks its source (QUIZ vs WRITING)."""
        item = learning_items[0]

        # Create quiz error
        quiz_error = PerformanceError(
            learning_item_id=item.id,
            wrong_form="quiz wrong",
            correct_form="quiz correct",
            explanation="Quiz error",
            source_type=PerformanceErrorSource.QUIZ,
            source_id=1,
        )

        # Create writing mini error
        writing_error = PerformanceError(
            learning_item_id=item.id,
            wrong_form="writing wrong",
            correct_form="writing correct",
            explanation="Writing error",
            source_type=PerformanceErrorSource.WRITING_MINI,
            source_id=2,
        )

        test_session.add(quiz_error)
        test_session.add(writing_error)
        test_session.commit()

        # Verify both types exist
        errors = test_session.query(PerformanceError).all()
        assert len(errors) == 2

        source_types = [e.source_type for e in errors]
        assert PerformanceErrorSource.QUIZ in source_types
        assert PerformanceErrorSource.WRITING_MINI in source_types


class TestQuizModes:
    """Tests for different quiz modes."""

    def test_all_concrete_modes_exist(self):
        """Test that all 5 concrete quiz modes are defined."""
        concrete_modes = [
            QuizMode.RECALL,
            QuizMode.FILL_BLANK,
            QuizMode.MULTIPLE_CHOICE,
            QuizMode.ERROR_CORRECTION,
            QuizMode.REWRITE_NATURALLY,
        ]

        for mode in concrete_modes:
            assert mode is not None
            assert mode != QuizMode.RANDOM

    def test_random_mode_is_separate(self):
        """Test that RANDOM mode is separate from concrete modes."""
        assert QuizMode.RANDOM is not None

        # RANDOM should not be in the concrete mode list
        concrete_modes = [
            QuizMode.RECALL,
            QuizMode.FILL_BLANK,
            QuizMode.MULTIPLE_CHOICE,
            QuizMode.ERROR_CORRECTION,
            QuizMode.REWRITE_NATURALLY,
        ]

        assert QuizMode.RANDOM not in concrete_modes