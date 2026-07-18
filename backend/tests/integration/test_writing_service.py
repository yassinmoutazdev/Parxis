"""Integration tests for WritingService.

Corresponds to ARCHITECTURE Section 17.2 and T7.5.1, T7.5.2.
Tests the WritingService methods and database model behaviors.
"""

import os
import tempfile
from datetime import datetime
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
from app.db.models.performance_error import PerformanceError, PerformanceErrorSource
from app.db.models.writing import (
    WritingPrompt,
    WritingPromptType,
    WritingSubmission,
    WritingSubmissionType,
    WritingEvaluation,
)
from app.db.models.report import WeeklyReport
from app.db.models.system import AuditLog, Config


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


class TestWritingPrompt:
    """Tests for WritingPrompt model."""

    def test_create_mini_prompt(self, test_session):
        """Test creating a mini writing prompt."""
        prompt = WritingPrompt(
            prompt_type=WritingPromptType.MINI,
            topic="Write about your day",
        )
        test_session.add(prompt)
        test_session.commit()
        test_session.refresh(prompt)

        assert prompt.id is not None
        assert prompt.prompt_type == WritingPromptType.MINI
        assert prompt.topic == "Write about your day"

    def test_create_weekly_prompt(self, test_session):
        """Test creating a weekly writing prompt."""
        prompt = WritingPrompt(
            prompt_type=WritingPromptType.WEEKLY,
            topic="Describe a memorable experience",
        )
        test_session.add(prompt)
        test_session.commit()
        test_session.refresh(prompt)

        assert prompt.id is not None
        assert prompt.prompt_type == WritingPromptType.WEEKLY


class TestWritingSubmission:
    """Tests for WritingSubmission model."""

    def test_create_mini_submission(self, test_session):
        """Test creating a mini writing submission."""
        # Create prompt first
        prompt = WritingPrompt(
            prompt_type=WritingPromptType.MINI,
            topic="Test topic",
        )
        test_session.add(prompt)
        test_session.commit()
        test_session.refresh(prompt)

        # Create submission
        submission = WritingSubmission(
            prompt_id=prompt.id,
            submission_type=WritingSubmissionType.MINI,
            submitted_text="This is my test submission.",
            word_count=5,
        )
        test_session.add(submission)
        test_session.commit()
        test_session.refresh(submission)

        assert submission.id is not None
        assert submission.submission_type == WritingSubmissionType.MINI
        assert submission.word_count == 5

    def test_create_weekly_submission(self, test_session):
        """Test creating a weekly writing submission."""
        # Create prompt first
        prompt = WritingPrompt(
            prompt_type=WritingPromptType.WEEKLY,
            topic="Test topic",
        )
        test_session.add(prompt)
        test_session.commit()
        test_session.refresh(prompt)

        # Create submission
        submission = WritingSubmission(
            prompt_id=prompt.id,
            submission_type=WritingSubmissionType.WEEKLY,
            submitted_text="This is my longer weekly writing submission with more content.",
            word_count=13,
        )
        test_session.add(submission)
        test_session.commit()
        test_session.refresh(submission)

        assert submission.id is not None
        assert submission.submission_type == WritingSubmissionType.WEEKLY


class TestWritingEvaluation:
    """Tests for WritingEvaluation model."""

    def test_create_mini_evaluation(self, test_session):
        """Test creating a mini writing evaluation."""
        # Create prompt and submission
        prompt = WritingPrompt(
            prompt_type=WritingPromptType.MINI,
            topic="Test topic",
        )
        test_session.add(prompt)
        test_session.commit()
        test_session.refresh(prompt)

        submission = WritingSubmission(
            prompt_id=prompt.id,
            submission_type=WritingSubmissionType.MINI,
            submitted_text="Test text",
            word_count=2,
        )
        test_session.add(submission)
        test_session.commit()
        test_session.refresh(submission)

        # Create evaluation
        evaluation = WritingEvaluation(
            submission_id=submission.id,
            overall_score=0.8,
            feedback_json={
                "corrections": [
                    {"wrong": "test", "correct": "test", "explanation": "good"}
                ],
                "naturalness_notes": ["Good flow"],
            },
        )
        test_session.add(evaluation)
        test_session.commit()
        test_session.refresh(evaluation)

        assert evaluation.id is not None
        assert evaluation.overall_score == 0.8

    def test_create_weekly_evaluation_with_scores(self, test_session):
        """Test creating a weekly writing evaluation with 5 dimension scores."""
        # Create prompt and submission
        prompt = WritingPrompt(
            prompt_type=WritingPromptType.WEEKLY,
            topic="Test topic",
        )
        test_session.add(prompt)
        test_session.commit()
        test_session.refresh(prompt)

        submission = WritingSubmission(
            prompt_id=prompt.id,
            submission_type=WritingSubmissionType.WEEKLY,
            submitted_text="Test text",
            word_count=2,
        )
        test_session.add(submission)
        test_session.commit()
        test_session.refresh(submission)

        # Create evaluation with 5 dimension scores
        evaluation = WritingEvaluation(
            submission_id=submission.id,
            grammar_score=85,
            naturalness_score=80,
            vocabulary_score=75,
            coherence_score=90,
            overall_score=82,
            feedback_json={
                "grammar": "Good grammar overall",
                "naturalness": "Sounds natural",
                "vocabulary": "Good vocabulary",
                "coherence": "Well organized",
                "overall": "Good effort",
            },
            # Provenance metadata
            evaluator_provider="ollama",
            evaluator_model="gemma4:31b",
            prompt_version="1.0.0",
            rubric_version="1.0.0",
        )
        test_session.add(evaluation)
        test_session.commit()
        test_session.refresh(evaluation)

        assert evaluation.id is not None
        assert evaluation.grammar_score == 85
        assert evaluation.naturalness_score == 80
        assert evaluation.vocabulary_score == 75
        assert evaluation.coherence_score == 90
        assert evaluation.overall_score == 82
        # Verify provenance
        assert evaluation.evaluator_provider == "ollama"
        assert evaluation.prompt_version == "1.0.0"


class TestPerformanceError:
    """Tests for PerformanceError model - ADR-05 exception."""

    def test_create_performance_error_from_mini_writing(self, test_session):
        """Test creating PerformanceError from mini writing (ADR-05 exception)."""
        # Create prompt and submission
        prompt = WritingPrompt(
            prompt_type=WritingPromptType.MINI,
            topic="Test topic",
        )
        test_session.add(prompt)
        test_session.commit()
        test_session.refresh(prompt)

        submission = WritingSubmission(
            prompt_id=prompt.id,
            submission_type=WritingSubmissionType.MINI,
            submitted_text="She dont like it",
            word_count=4,
        )
        test_session.add(submission)
        test_session.commit()
        test_session.refresh(submission)

        # Create PerformanceError (ADR-05 exception - direct write, no approval)
        error = PerformanceError(
            learning_item_id=None,
            wrong_form="She dont like it",
            correct_form="She doesn't like it",
            explanation="Use doesn't with third person singular",
            source_type=PerformanceErrorSource.WRITING_MINI,
            source_id=submission.id,
        )
        test_session.add(error)
        test_session.commit()
        test_session.refresh(error)

        assert error.id is not None
        assert error.source_type == PerformanceErrorSource.WRITING_MINI
        assert error.source_id == submission.id


class TestApprovalQueue:
    """Tests for ApprovalQueue - suggested items path."""

    def test_create_approval_queue_item_from_writing_feedback(self, test_session):
        """Test creating ApprovalQueue item from writing suggested items."""
        # Create prompt and submission
        prompt = WritingPrompt(
            prompt_type=WritingPromptType.MINI,
            topic="Test topic",
        )
        test_session.add(prompt)
        test_session.commit()
        test_session.refresh(prompt)

        submission = WritingSubmission(
            prompt_id=prompt.id,
            submission_type=WritingSubmissionType.MINI,
            submitted_text="Test text",
            word_count=2,
        )
        test_session.add(submission)
        test_session.commit()
        test_session.refresh(submission)

        # Create ApprovalQueue item (approval-gated path)
        queue_item = ApprovalQueue(
            source_type=ApprovalSourceType.WRITING_FEEDBACK,
            source_id=submission.id,
            item_type="COLLOCATION",
            extracted_text="go to the store",
            explanation="visit a store to buy things",
            example_sentence="I went to the store yesterday",
            source_context="went to the store",
            status=ApprovalStatus.PENDING,
        )
        test_session.add(queue_item)
        test_session.commit()
        test_session.refresh(queue_item)

        assert queue_item.id is not None
        assert queue_item.source_type == ApprovalSourceType.WRITING_FEEDBACK
        assert queue_item.status == ApprovalStatus.PENDING


class TestWritingService:
    """Tests for WritingService helper methods."""

    def test_generate_mini_prompt(self, test_session):
        """Test generating a mini prompt."""
        from app.writing.service import WritingService

        prompt = WritingService.generate_mini_prompt()

        assert prompt.id is not None
        assert prompt.prompt_type == WritingPromptType.MINI
        assert prompt.topic

    def test_get_recent_prompts(self, test_session):
        """Test getting recent prompts."""
        from app.writing.service import WritingService

        # Create some prompts
        for i in range(3):
            prompt = WritingPrompt(
                prompt_type=WritingPromptType.MINI,
                topic=f"Test prompt {i}",
            )
            test_session.add(prompt)
        test_session.commit()

        # Get recent prompts
        prompts = WritingService.get_recent_prompts(
            WritingPromptType.MINI,
            limit=2,
        )

        assert len(prompts) == 2

    def test_get_prompt(self, test_session):
        """Test getting a prompt by ID."""
        from app.writing.service import WritingService

        # Create a prompt
        prompt = WritingPrompt(
            prompt_type=WritingPromptType.MINI,
            topic="Test prompt",
        )
        test_session.add(prompt)
        test_session.commit()
        test_session.refresh(prompt)

        retrieved = WritingService.get_prompt(prompt.id)
        assert retrieved is not None
        assert retrieved.id == prompt.id

    def test_get_submission(self, test_session):
        """Test getting a submission by ID."""
        # Create a prompt and submission
        prompt = WritingPrompt(
            prompt_type=WritingPromptType.MINI,
            topic="Test prompt",
        )
        test_session.add(prompt)
        test_session.commit()
        test_session.refresh(prompt)

        submission = WritingSubmission(
            prompt_id=prompt.id,
            submission_type=WritingSubmissionType.MINI,
            submitted_text="Test text",
            word_count=2,
        )
        test_session.add(submission)
        test_session.commit()
        test_session.refresh(submission)

        # Verify it's in the database
        retrieved = test_session.get(WritingSubmission, submission.id)
        assert retrieved is not None
        assert retrieved.id == submission.id