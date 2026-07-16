"""Unit tests for scheduler mastery functions.

Tests the decayed_score() and update_mastery() functions per ARCHITECTURE Section 8.4.
"""

import pytest
from datetime import datetime, timedelta

from app.db.models.learning_item import LearningItem, ItemType
from app.scheduler.mastery import (
    decayed_score,
    update_mastery,
    is_due,
    weakness_score,
    SchedulerSettings,
    reset_settings_cache,
    DEFAULT_DECAY_RATE,
    DEFAULT_CORRECT_THRESHOLD,
)


class TestDecayedScore:
    """Tests for decayed_score() function."""

    def test_no_review_returns_mastery(self):
        """If last_reviewed_at is None, return stored mastery."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            last_reviewed_at=None,
        )
        assert decayed_score(item) == 0.5

    def test_zero_days_returns_mastery(self):
        """At 0 days elapsed, decayed score equals stored mastery."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            last_reviewed_at=datetime.utcnow(),
        )
        result = decayed_score(item)
        assert abs(result - 0.5) < 0.01

    def test_90_days_approx_half(self):
        """At ~90 days, decayed score should be ~50% of original (per DECAY_RATE)."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=1.0,
            last_reviewed_at=datetime.utcnow() - timedelta(days=90),
        )
        result = decayed_score(item)
        # exp(-0.0077 * 90) ≈ 0.5
        assert abs(result - 0.5) < 0.05

    def test_very_long_elapsed_approaches_zero(self):
        """With very long elapsed time, decayed score approaches zero."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=1.0,
            last_reviewed_at=datetime.utcnow() - timedelta(days=365),
        )
        result = decayed_score(item)
        # exp(-0.0077 * 365) ≈ 0.062
        assert result < 0.1

    def test_custom_datetime(self):
        """Test decayed_score with a custom datetime."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.8,
            last_reviewed_at=datetime(2024, 1, 1),
        )
        result = decayed_score(item, now=datetime(2024, 1, 31))  # 30 days
        expected = 0.8 * pow(2.71828, -DEFAULT_DECAY_RATE * 30)
        assert abs(result - expected) < 0.01


class TestUpdateMastery:
    """Tests for update_mastery() function."""

    def test_correct_answer_increases_mastery(self):
        """Correct answer increases mastery_score."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            ease_factor=2.5,
            interval_days=1,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
        )

        update_mastery(item, score=0.8)

        assert item.mastery_score > 0.5
        assert item.mastery_score <= 1.0
        assert item.correct_count == 1
        assert item.review_count == 1

    def test_correct_answer_increases_interval(self):
        """Correct answer increases interval_days via ease_factor."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            ease_factor=2.5,
            interval_days=1,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
        )

        update_mastery(item, score=0.8)

        assert item.interval_days > 1
        assert item.ease_factor > 2.5

    def test_incorrect_answer_decreases_mastery(self):
        """Incorrect answer decreases mastery_score."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            ease_factor=2.5,
            interval_days=5,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
        )

        update_mastery(item, score=0.3)

        assert item.mastery_score < 0.5
        assert item.mastery_score >= 0.0
        assert item.incorrect_count == 1

    def test_incorrect_answer_resets_interval(self):
        """Incorrect answer resets interval_days to 1."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            ease_factor=2.5,
            interval_days=10,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
        )

        update_mastery(item, score=0.3)

        assert item.interval_days == 1

    def test_incorrect_answer_decreases_ease_factor(self):
        """Incorrect answer decreases ease_factor."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            ease_factor=2.5,
            interval_days=5,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
        )

        update_mastery(item, score=0.3)

        assert item.ease_factor < 2.5

    def test_mastery_clamped_at_zero(self):
        """Mastery cannot go below 0.0."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.05,
            ease_factor=1.5,
            interval_days=1,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
        )

        update_mastery(item, score=0.1)

        assert item.mastery_score >= 0.0

    def test_mastery_clamped_at_one(self):
        """Mastery cannot exceed 1.0."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.95,
            ease_factor=2.5,
            interval_days=1,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
        )

        update_mastery(item, score=1.0)

        assert item.mastery_score <= 1.0

    def test_ease_factor_clamped_min(self):
        """Ease factor has minimum of 1.3."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            ease_factor=1.4,
            interval_days=1,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
        )

        update_mastery(item, score=0.1)

        assert item.ease_factor >= 1.3

    def test_ease_factor_clamped_max(self):
        """Ease factor has maximum of 3.0."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            ease_factor=3.0,
            interval_days=1,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
        )

        update_mastery(item, score=1.0)

        assert item.ease_factor <= 3.0

    def test_sets_next_review_due(self):
        """update_mastery sets next_review_due based on interval_days."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            ease_factor=2.5,
            interval_days=1,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
            last_reviewed_at=None,
            next_review_due=None,
        )

        now = datetime.utcnow()
        update_mastery(item, score=0.8, now=now)

        assert item.next_review_due is not None
        assert item.last_reviewed_at == now


class TestIsDue:
    """Tests for is_due() function."""

    def test_suspended_not_due(self):
        """Suspended items are never due."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            suspended=True,
            next_review_due=None,
        )
        assert not is_due(item)

    def test_no_next_review_is_due(self):
        """Items with no next_review_due are due."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            suspended=False,
            next_review_due=None,
        )
        assert is_due(item)

    def test_past_due_is_due(self):
        """Items with past next_review_due are due."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            suspended=False,
            next_review_due=datetime.utcnow() - timedelta(days=1),
        )
        assert is_due(item)

    def test_future_not_due(self):
        """Items with future next_review_due are not due."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            suspended=False,
            next_review_due=datetime.utcnow() + timedelta(days=1),
        )
        assert not is_due(item)


class TestWeaknessScore:
    """Tests for weakness_score() function."""

    def test_perfect_item_zero_weakness(self):
        """Item with mastery 1.0 has weakness 0."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=1.0,
            last_reviewed_at=datetime.utcnow(),
        )
        assert weakness_score(item) == 0.0

    def test_zero_mastery_max_weakness(self):
        """Item with mastery 0.0 has weakness 1."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.0,
            last_reviewed_at=datetime.utcnow(),
        )
        assert weakness_score(item) == 1.0

    def test_half_mastery_half_weakness(self):
        """Item with mastery 0.5 has weakness 0.5."""
        item = LearningItem(
            id=1,
            item_type=ItemType.COLLOCATION,
            text="test",
            mastery_score=0.5,
            last_reviewed_at=datetime.utcnow(),
        )
        assert weakness_score(item) == 0.5