"""Mastery and decay calculations for learning items.

Corresponds to ARCHITECTURE Section 8.4 (Mastery Update Formula) and PRD Section 16.6.
"""

import math
from datetime import datetime, timedelta

from app.db.models.learning_item import LearningItem

# Default constants - can be overridden via Config table
DEFAULT_DECAY_RATE = 0.0077  # ~50% after 90 days
DEFAULT_CORRECT_THRESHOLD = 0.7
EASE_FACTOR_INCREMENT = 0.1
EASE_FACTOR_MAX = 3.0
EASE_FACTOR_DECREMENT = 0.2
EASE_FACTOR_MIN = 1.3
MASTERY_BONUS = 0.15
MASTERY_PENALTY = 0.25


def decayed_score(item: LearningItem, now: datetime | None = None) -> float:
    """Read-time decay (ADR-04) — never mutates the stored value.

    Calculates the mastery score with exponential decay based on time since last review.

    Args:
        item: The LearningItem to calculate decayed score for
        now: Optional datetime (defaults to now)

    Returns:
        The decayed mastery score (0.0 to 1.0)
    """
    now = now or datetime.utcnow()
    if item.last_reviewed_at is None:
        return item.mastery_score

    days = (now - item.last_reviewed_at).days
    decay_rate = SchedulerSettings.get().decay_rate
    return item.mastery_score * math.exp(-decay_rate * days)


def update_mastery(item: LearningItem, score: float, now: datetime | None = None) -> None:
    """Mutates item in place; caller is responsible for committing the session.

    Updates mastery based on the result score using the SM-2 inspired formula.

    Args:
        item: The LearningItem to update
        score: The score from the quiz/writing evaluation (0.0 to 1.0)
        now: Optional datetime (defaults to now)
    """
    now = now or datetime.utcnow()
    settings = SchedulerSettings.get()
    correct = score >= settings.correct_threshold

    if correct:
        # Correct answer path
        item.ease_factor = min(item.ease_factor + EASE_FACTOR_INCREMENT, EASE_FACTOR_MAX)
        item.interval_days = max(1, round(item.interval_days * item.ease_factor)) if item.interval_days else 1
        item.mastery_score = min(item.mastery_score + MASTERY_BONUS * (1 - item.mastery_score), 1.0)
        item.correct_count += 1
    else:
        # Incorrect answer path
        item.ease_factor = max(item.ease_factor - EASE_FACTOR_DECREMENT, EASE_FACTOR_MIN)
        item.interval_days = 1
        item.mastery_score = max(item.mastery_score - MASTERY_PENALTY * item.mastery_score, 0.0)
        item.incorrect_count += 1

    item.review_count += 1
    item.last_reviewed_at = now
    item.next_review_due = now + timedelta(days=item.interval_days)


def is_due(item: LearningItem, now: datetime | None = None) -> bool:
    """Check if a learning item is due for review.

    Args:
        item: The LearningItem to check
        now: Optional datetime (defaults to now)

    Returns:
        True if the item is due for review
    """
    now = now or datetime.utcnow()
    if item.suspended:
        return False
    if item.next_review_due is None:
        return True
    return now >= item.next_review_due


def weakness_score(item: LearningItem, now: datetime | None = None) -> float:
    """Calculate weakness score for weighted sampling (1 - mastery_score).

    Args:
        item: The LearningItem to calculate weakness for
        now: Optional datetime (defaults to now)

    Returns:
        Weakness score (0.0 = perfect, 1.0 = weakest)
    """
    return 1.0 - decayed_score(item, now)


class SchedulerSettings:
    """Runtime settings for the scheduler loaded from Config table.

    Corresponds to ARCHITECTURE Section 12.2 (Runtime-Adjustable Config).
    """

    _cached: dict[str, str] | None = None
    _decay_rate: float | None = None
    _correct_threshold: float | None = None

    @classmethod
    def get(cls) -> "SchedulerSettings":
        """Get settings, loading from Config table if not cached."""
        if cls._decay_rate is None:
            cls._load_settings()
        return cls()

    @classmethod
    def _load_settings(cls) -> None:
        """Load settings from Config table, falling back to defaults."""
        from app.db.engine import Session
        from app.db.models.system import Config

        cls._cached = {}
        cls._decay_rate = DEFAULT_DECAY_RATE
        cls._correct_threshold = DEFAULT_CORRECT_THRESHOLD

        try:
            with Session() as session:
                configs = session.query(Config).all()
                for config in configs:
                    cls._cached[config.key] = config.value

                    if config.key == "decay_rate":
                        cls._decay_rate = float(config.value)
                    elif config.key == "correct_threshold":
                        cls._correct_threshold = float(config.value)
        except Exception:
            # If Config table doesn't exist or query fails, use defaults
            pass

    @property
    def decay_rate(self) -> float:
        """Get the decay rate constant."""
        return self._decay_rate or DEFAULT_DECAY_RATE

    @property
    def correct_threshold(self) -> float:
        """Get the correct threshold constant."""
        return self._correct_threshold or DEFAULT_CORRECT_THRESHOLD


def reset_settings_cache() -> None:
    """Reset the settings cache (useful for testing)."""
    SchedulerSettings._cached = None
    SchedulerSettings._decay_rate = None
    SchedulerSettings._correct_threshold = None
