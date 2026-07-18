"""Dashboard aggregation service for read-only dashboard queries.

Corresponds to ARCHITECTURE Section 6.6 (Dashboard Refresh) and PRD Section 17.4,
Section 20 (Dashboard Design).
"""

from datetime import datetime, timedelta
from typing import Any

from app.db.engine import Session
from app.db.models.approval import ApprovalQueue, ApprovalStatus
from app.db.models.learning_item import ItemType, LearningItem
from app.db.models.quiz import QuizQuestion, QuizSession
from app.db.models.writing import WritingEvaluation, WritingSubmission
from app.scheduler.mastery import decayed_score

# Default proficiency blend weights (per PRD Section 17.4)
DEFAULT_ITEM_MASTERY_WEIGHT = 0.4
DEFAULT_WRITING_PERFORMANCE_WEIGHT = 0.6

# Number of recent writing evaluations to average for proficiency calculation
RECENT_WRITING_EVALS_COUNT = 4


class DashboardService:
    """Read-only aggregation service for dashboard queries.

    No mutation methods — all queries are read-only.
    """

    @classmethod
    def overview(cls, app_state: Any | None = None) -> dict[str, Any]:
        """Get dashboard overview with proficiency, activity snapshot, and health.

        Implements the proficiency blend formula from PRD Section 17.4:
        - Default 40% item mastery / 60% recent writing performance

        Args:
            app_state: Optional FastAPI app state to check VaultWatcher health

        Returns:
            Dictionary with proficiency, pending approvals, and health status
        """
        # Get pending approvals count
        with Session() as session:
            pending_count = (
                session.query(ApprovalQueue)
                .filter(ApprovalQueue.status == ApprovalStatus.PENDING)
                .count()
            )

        # Get category mastery average
        category_mastery_avg = cls._calculate_category_mastery_avg()

        # Get recent writing performance average
        writing_perf_avg = cls._calculate_writing_performance_avg()

        # Apply proficiency blend formula
        proficiency = cls._blend_proficiency(
            category_mastery_avg, writing_perf_avg,
            DEFAULT_ITEM_MASTERY_WEIGHT, DEFAULT_WRITING_PERFORMANCE_WEIGHT
        )

        # Get this week's activity snapshot
        week_start = cls._get_week_start(datetime.utcnow())
        week_end = week_start + timedelta(days=7)
        week_snapshot = cls._get_week_snapshot(week_start, week_end)

        # Determine VaultWatcher health status
        health = cls._get_health_status(app_state)

        return {
            "proficiency": proficiency,
            "category_mastery_avg": category_mastery_avg,
            "writing_performance_avg": writing_perf_avg,
            "pending_approvals_count": pending_count,
            "week_snapshot": week_snapshot,
            "health": health,
        }

    @classmethod
    def mastery_by_category(cls) -> list[dict[str, Any]]:
        """Get decayed mastery scores aggregated by category.

        Per PRD Section 17.4, each category's mastery is weighted by review_count,
        and decay is applied at read-time (ADR-04) via decayed_score().

        Returns:
            List of category mastery dictionaries
        """
        with Session() as session:
            items = (
                session.query(LearningItem)
                .filter(LearningItem.suspended == False)  # noqa: E712
                .all()
            )

        # Aggregate by category
        category_scores: dict[ItemType, tuple[list[float], list[int]]] = {}

        for item in items:
            if item.item_type not in category_scores:
                category_scores[item.item_type] = ([], [])

            decayed = decayed_score(item)
            category_scores[item.item_type][0].append(decayed)
            category_scores[item.item_type][1].append(item.review_count)

        # Calculate weighted averages
        result = []
        for item_type, (scores, review_counts) in category_scores.items():
            if not scores:
                continue

            # Weighted by review_count per PRD Section 17.4
            weighted_sum = sum(s * rc for s, rc in zip(scores, review_counts))
            total_weight = sum(review_counts)

            if total_weight > 0:
                weighted_avg = weighted_sum / total_weight
            else:
                weighted_avg = sum(scores) / len(scores)

            result.append({
                "category": item_type.value,
                "mastery_score": round(weighted_avg, 3),
                "item_count": len(scores),
                "total_reviews": total_weight,
            })

        # Sort by category name for consistent ordering
        result.sort(key=lambda x: x["category"])

        return result

    @classmethod
    def trend_series(cls, range_days: int = 90) -> dict[str, Any]:
        """Get trend series data for charts.

        Returns:
            Dictionary with quiz_accuracy, writing_scores, and items_learned series
        """
        now = datetime.utcnow()
        start_date = now - timedelta(days=range_days)

        # Get weekly boundaries
        weeks = cls._get_week_boundaries(start_date, now)

        quiz_accuracy_series = []
        writing_scores_series = []
        items_learned_series = []

        for week_start, week_end in weeks:
            # Quiz accuracy for this week
            quiz_stats = cls._get_quiz_accuracy_for_week(week_start, week_end)
            quiz_accuracy_series.append({
                "week_start": week_start.isoformat(),
                "accuracy": quiz_stats["accuracy"],
                "total_questions": quiz_stats["total_questions"],
            })

            # Writing scores for this week
            writing_stats = cls._get_writing_scores_for_week(week_start, week_end)
            writing_scores_series.append({
                "week_start": week_start.isoformat(),
                "grammar": writing_stats.get("grammar_score"),
                "naturalness": writing_stats.get("naturalness_score"),
                "vocabulary": writing_stats.get("vocabulary_score"),
                "coherence": writing_stats.get("coherence_score"),
                "overall": writing_stats.get("overall_score"),
            })

            # Items learned this week
            items_count = cls._get_items_learned_for_week(week_start, week_end)
            items_learned_series.append({
                "week_start": week_start.isoformat(),
                "count": items_count,
            })

        return {
            "quiz_accuracy": quiz_accuracy_series,
            "writing_scores": writing_scores_series,
            "items_learned": items_learned_series,
            "range_days": range_days,
        }

    @classmethod
    def _calculate_category_mastery_avg(cls) -> float | None:
        """Calculate the average decayed mastery across all categories."""
        with Session() as session:
            items = (
                session.query(LearningItem)
                .filter(LearningItem.suspended == False)  # noqa: E712
                .all()
            )

        if not items:
            return None

        decayed_scores = [decayed_score(item) for item in items]
        return sum(decayed_scores) / len(decayed_scores)

    @classmethod
    def _calculate_writing_performance_avg(cls) -> float | None:
        """Calculate average of recent weekly writing overall scores."""
        with Session() as session:
            # Get recent weekly writing evaluations
            evaluations = (
                session.query(WritingEvaluation)
                .join(WritingSubmission)
                .filter(
                    WritingSubmission.submission_type == "WEEKLY",
                    WritingEvaluation.overall_score.isnot(None),
                )
                .order_by(WritingEvaluation.created_at.desc())
                .limit(RECENT_WRITING_EVALS_COUNT)
                .all()
            )

        if not evaluations:
            return None

        scores = [e.overall_score for e in evaluations if e.overall_score is not None]
        if not scores:
            return None

        # Convert 0-100 to 0-1 scale
        return (sum(scores) / len(scores)) / 100.0

    @classmethod
    def _blend_proficiency(
        cls,
        category_mastery: float | None,
        writing_perf: float | None,
        item_mastery_weight: float,
        writing_perf_weight: float,
    ) -> float | None:
        """Blend category mastery and writing performance into overall proficiency.

        Args:
            category_mastery: Category mastery average (0-1)
            writing_perf: Writing performance average (0-1)
            item_mastery_weight: Weight for item mastery (default 0.4)
            writing_perf_weight: Weight for writing performance (default 0.6)

        Returns:
            Blended proficiency score (0-1) or None if no data
        """
        # Handle missing data cases
        if category_mastery is None and writing_perf is None:
            return None

        if category_mastery is None:
            return writing_perf

        if writing_perf is None:
            return category_mastery

        # Apply blend formula
        return (
            category_mastery * item_mastery_weight +
            writing_perf * writing_perf_weight
        )

    @classmethod
    def _get_week_start(cls, dt: datetime) -> datetime:
        """Get the start of the week (Monday) for a given date."""
        # Monday is 0 in weekday()
        days_since_monday = dt.weekday()
        week_start = dt - timedelta(days=days_since_monday)
        return week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    @classmethod
    def _get_week_snapshot(cls, week_start: datetime, week_end: datetime) -> dict[str, Any]:
        """Get activity snapshot for a week."""
        with Session() as session:
            # Items studied this week
            items_studied = (
                session.query(LearningItem)
                .filter(
                    LearningItem.last_reviewed_at >= week_start,
                    LearningItem.last_reviewed_at < week_end,
                )
                .count()
            )

            # Quiz sessions this week
            quiz_sessions = (
                session.query(QuizSession)
                .filter(
                    QuizSession.started_at >= week_start,
                    QuizSession.started_at < week_end,
                    QuizSession.completed_at.isnot(None),
                )
                .count()
            )

            # Writing submissions this week
            writing_subs = (
                session.query(WritingSubmission)
                .filter(
                    WritingSubmission.created_at >= week_start,
                    WritingSubmission.created_at < week_end,
                )
                .count()
            )

        return {
            "items_studied": items_studied,
            "quiz_sessions": quiz_sessions,
            "writing_submissions": writing_subs,
        }

    @classmethod
    def _get_health_status(cls, app_state: Any | None = None) -> dict[str, Any]:
        """Get VaultWatcher health status.

        Args:
            app_state: Optional FastAPI app state

        Returns:
            Dictionary with health status
        """
        if app_state is None:
            return {
                "status": "unknown",
                "vault_watcher": "not_available",
            }

        vault_started = getattr(app_state, "vault_watcher_started", False)
        vault_path = getattr(app_state, "vault_watcher", None)

        return {
            "status": "ok" if vault_started else "warning",
            "vault_watcher": "running" if vault_started else "not_running",
            "vault_path": str(vault_path.vault_path) if vault_started and vault_path else None,
        }

    @classmethod
    def _get_week_boundaries(cls, start_date: datetime, end_date: datetime) -> list[tuple[datetime, datetime]]:
        """Get list of week boundaries between start and end dates."""
        weeks = []
        current = cls._get_week_start(start_date)

        while current < end_date:
            next_week = current + timedelta(days=7)
            weeks.append((current, next_week))
            current = next_week

        return weeks

    @classmethod
    def _get_quiz_accuracy_for_week(cls, week_start: datetime, week_end: datetime) -> dict[str, Any]:
        """Get quiz accuracy for a specific week."""
        with Session() as session:
            sessions = (
                session.query(QuizSession)
                .filter(
                    QuizSession.started_at >= week_start,
                    QuizSession.started_at < week_end,
                    QuizSession.completed_at.isnot(None),
                )
                .all()
            )

            if not sessions:
                return {"accuracy": None, "total_questions": 0}

            session_ids = [s.id for s in sessions]
            questions = (
                session.query(QuizQuestion)
                .filter(QuizQuestion.quiz_session_id.in_(session_ids))
                .all()
            )

            total = len(questions)
            correct = sum(1 for q in questions if q.is_correct is True)

            accuracy = (correct / total * 100) if total > 0 else None

            return {"accuracy": accuracy, "total_questions": total}

    @classmethod
    def _get_writing_scores_for_week(cls, week_start: datetime, week_end: datetime) -> dict[str, float | None]:
        """Get writing scores for a specific week (weekly submissions only)."""
        with Session() as session:
            eval = (
                session.query(WritingEvaluation)
                .join(WritingSubmission)
                .filter(
                    WritingSubmission.submission_type == "WEEKLY",
                    WritingEvaluation.created_at >= week_start,
                    WritingEvaluation.created_at < week_end,
                )
                .order_by(WritingEvaluation.created_at.desc())
                .first()
            )

            if eval is None:
                return {
                    "grammar_score": None,
                    "naturalness_score": None,
                    "vocabulary_score": None,
                    "coherence_score": None,
                    "overall_score": None,
                }

            return {
                "grammar_score": eval.grammar_score,
                "naturalness_score": eval.naturalness_score,
                "vocabulary_score": eval.vocabulary_score,
                "coherence_score": eval.coherence_score,
                "overall_score": eval.overall_score,
            }

    @classmethod
    def _get_items_learned_for_week(cls, week_start: datetime, week_end: datetime) -> int:
        """Get count of new items learned in a specific week."""
        with Session() as session:
            return (
                session.query(LearningItem)
                .filter(
                    LearningItem.created_at >= week_start,
                    LearningItem.created_at < week_end,
                )
                .count()
            )
