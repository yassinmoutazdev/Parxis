"""Retrieval Service for querying learning data.

Corresponds to ARCHITECTURE Section 6.3 (RetrievalService) and PRD Section 16.1.
"""

import random
from datetime import datetime, date
from typing import Any

from app.db.engine import Session
from app.db.models.learning_item import ItemType, LearningItem
from app.db.models.performance_error import PerformanceError
from app.db.models.quiz import QuizQuestion, QuizSession
from app.db.models.writing import WritingEvaluation, WritingSubmission
from app.scheduler.mastery import decayed_score, is_due

CATEGORY_BALANCE = 0.6  # ~60% category balance constraint


class RetrievalService:
    """Service for retrieving learning data.

    All read-side structured queries live here - the single place SQL for
    cross-cutting reads lives, so pipelines don't hand-roll queries.
    """

    @classmethod
    def select_eligible_items(
        cls,
        size: int,
        category_balance: float = CATEGORY_BALANCE,
        since: date | None = None,
    ) -> list[LearningItem]:
        """Select eligible items for quiz generation.

        PRD Section 16.1 (Eligibility & Selection algorithm):
        1. Partition items into due/not-due
        2. Use weakness-weighted sampling (weakness = 1 - mastery)
        3. Apply ~60% category-balance constraint
        4. Backfill from not-due pool if needed

        Args:
            size: Number of items to select
            category_balance: Target proportion of items from categories with due items (0.0-1.0)
            since: Optional date to bias selection toward items created/reviewed since this date.
                   Used for weekly quiz to prefer items from the current week.

        Returns:
            List of eligible LearningItems
        """
        now = datetime.utcnow()
        since_dt = datetime.combine(since, datetime.min.time()) if since else None

        with Session() as session:
            # Fetch all non-suspended items
            query = session.query(LearningItem).filter(
                LearningItem.suspended == False  # noqa: E712
            )

            # If since is provided, also fetch items created/reviewed since that date
            # for potential biasing
            all_items = query.all()

            if not all_items:
                return []

            # If since is provided, identify items created or reviewed since that date
            recent_items: set[int] = set()
            if since_dt:
                for item in all_items:
                    if (item.created_at and item.created_at >= since_dt) or \
                       (item.last_reviewed_at and item.last_reviewed_at >= since_dt):
                        recent_items.add(item.id)

            # Partition into due and not-due
            due_items = [item for item in all_items if is_due(item, now)]
            not_due_items = [item for item in all_items if not is_due(item, now)]

            # If since is provided, bias toward recent items by reordering
            if since_dt and recent_items:
                # Move recent items to front of due_items and not_due_items lists
                due_items.sort(key=lambda x: 0 if x.id in recent_items else 1)
                not_due_items.sort(key=lambda x: 0 if x.id in recent_items else 1)

            # Calculate weakness scores for weighted sampling
            def weakness(item: LearningItem) -> float:
                return 1.0 - decayed_score(item, now)

            # Get unique categories from due items
            due_by_category: dict[ItemType, list[LearningItem]] = {}
            for item in due_items:
                if item.item_type not in due_by_category:
                    due_by_category[item.item_type] = []
                due_by_category[item.item_type].append(item)

            # If we have enough due items, sample with category balance
            if len(due_items) >= size:
                # Calculate target number from categories with due items
                categories_with_due = list(due_by_category.keys())
                target_from_categories = int(size * category_balance)

                selected: list[LearningItem] = []

                # Sample from each category (weighted by weakness)
                if categories_with_due and target_from_categories > 0:
                    per_category = max(1, target_from_categories // len(categories_with_due))

                    for cat in categories_with_due:
                        cat_items = due_by_category[cat]
                        if len(cat_items) <= per_category:
                            selected.extend(cat_items)
                        else:
                            # Weighted sampling
                            weights = [weakness(item) + 0.01 for item in cat_items]  # +0.01 to avoid zero
                            total = sum(weights)
                            probs = [w / total for w in weights]

                            selected.extend(
                                random.choices(
                                    cat_items,
                                    weights=probs,
                                    k=min(per_category, len(cat_items)),
                                )
                            )

                # Fill remaining from random due items
                remaining = size - len(selected)
                if remaining > 0 and due_items:
                    remaining_due = [i for i in due_items if i not in selected]
                    if remaining_due:
                        weights = [weakness(item) + 0.01 for item in remaining_due]
                        total = sum(weights)
                        probs = [w / total for w in weights]
                        additional = random.choices(
                            remaining_due,
                            weights=probs,
                            k=min(remaining, len(remaining_due)),
                        )
                        selected.extend(additional)

                return selected[:size]

            # Not enough due items - need to backfill from not-due
            selected = due_items.copy()

            # Calculate how many more we need
            needed = size - len(selected)

            if needed > 0 and not_due_items:
                # Weight by weakness for backfill (prefer weaker items)
                weights = [weakness(item) + 0.01 for item in not_due_items]
                total = sum(weights)
                probs = [w / total for w in weights]

                backfill = random.choices(
                    not_due_items,
                    weights=probs,
                    k=min(needed, len(not_due_items)),
                )
                selected.extend(backfill)

            return selected[:size]

    @classmethod
    def items_created_between(
        cls, week_start: datetime, week_end: datetime
    ) -> list[LearningItem]:
        """Get learning items created within a week range.

        Args:
            week_start: Start of the week
            week_end: End of the week

        Returns:
            List of LearningItems created in the week
        """
        with Session() as session:
            return (
                session.query(LearningItem)
                .filter(
                    LearningItem.created_at >= week_start,
                    LearningItem.created_at < week_end,
                )
                .all()
            )

    @classmethod
    def quiz_summary_for_week(
        cls, week_start: datetime, week_end: datetime
    ) -> dict[str, Any]:
        """Get quiz activity summary for a week.

        Args:
            week_start: Start of the week
            week_end: End of the week

        Returns:
            Dictionary with quiz summary stats
        """
        with Session() as session:
            # Get completed sessions in the week
            sessions = (
                session.query(QuizSession)
                .filter(
                    QuizSession.started_at >= week_start,
                    QuizSession.started_at < week_end,
                    QuizSession.completed_at.isnot(None),
                )
                .all()
            )

            total_sessions = len(sessions)
            if total_sessions == 0:
                return {
                    "total_sessions": 0,
                    "total_questions": 0,
                    "correct_count": 0,
                    "incorrect_count": 0,
                    "score": None,
                }

            # Get all questions for these sessions
            session_ids = [s.id for s in sessions]
            questions = (
                session.query(QuizQuestion)
                .filter(QuizQuestion.quiz_session_id.in_(session_ids))
                .all()
            )

            correct_count = sum(1 for q in questions if q.is_correct is True)
            incorrect_count = sum(1 for q in questions if q.is_correct is False)
            total_questions = len(questions)

            score = (
                (correct_count / total_questions * 100) if total_questions > 0 else None
            )

            return {
                "total_sessions": total_sessions,
                "total_questions": total_questions,
                "correct_count": correct_count,
                "incorrect_count": incorrect_count,
                "score": score,
            }

    @classmethod
    def mini_writing_summary_for_week(
        cls, week_start: datetime, week_end: datetime
    ) -> dict[str, Any]:
        """Get mini writing activity summary for a week.

        Args:
            week_start: Start of the week
            week_end: End of the week

        Returns:
            Dictionary with mini writing summary stats
        """
        with Session() as session:
            submissions = (
                session.query(WritingSubmission)
                .filter(
                    WritingSubmission.created_at >= week_start,
                    WritingSubmission.created_at < week_end,
                )
                .all()
            )

            total_submissions = len(submissions)

            if total_submissions == 0:
                return {"total_submissions": 0, "average_score": None}

            # Get evaluations for these submissions
            submission_ids = [s.id for s in submissions]
            evaluations = (
                session.query(WritingEvaluation)
                .filter(
                    WritingEvaluation.submission_id.in_(submission_ids),
                )
                .all()
            )

            scores = [e.overall_score for e in evaluations if e.overall_score]
            avg_score = sum(scores) / len(scores) if scores else None

            return {
                "total_submissions": total_submissions,
                "average_score": avg_score,
            }

    @classmethod
    def weekly_writing_eval_for_week(
        cls, week_start: datetime, week_end: datetime
    ) -> WritingEvaluation | None:
        """Get the weekly writing evaluation for a week.

        Args:
            week_start: Start of the week
            week_end: End of the week

        Returns:
            The WritingEvaluation for the week, or None if not found
        """
        with Session() as session:
            return (
                session.query(WritingEvaluation)
                .filter(
                    WritingEvaluation.created_at >= week_start,
                    WritingEvaluation.created_at < week_end,
                )
                .order_by(WritingEvaluation.created_at.desc())
                .first()
            )

    @classmethod
    def item_context(cls, item: LearningItem) -> dict[str, Any]:
        """Get context for a learning item (for quiz prompt construction).

        Args:
            item: The LearningItem to get context for

        Returns:
            Dictionary with item context for prompt construction
        """
        return {
            "text": item.text,
            "definition": item.definition,
            "example_sentence": item.example_sentence,
            "item_type": item.item_type.value,
            "mastery_score": item.mastery_score,
        }

    @classmethod
    def writing_context(cls, text: str, limit: int = 10) -> dict[str, Any]:
        """Get context for writing evaluation (FTS5-based lookup).

        Note: Per PRD Section 15.1, this uses lexical-only matching (no embeddings).

        Args:
            text: The writing text to find context for
            limit: Maximum number of items to return

        Returns:
            Dictionary with known relevant items and weak categories
        """
        with Session() as session:
            # Find items that might be related based on word overlap
            # This is a simple lexical match - more sophisticated matching would use embeddings
            words = set(text.lower().split())

            # Get all learning items
            all_items = session.query(LearningItem).all()

            # Find items with word overlap
            relevant_items = []
            for item in all_items:
                item_words = set(item.text.lower().split())
                if words & item_words:  # intersection
                    relevant_items.append(item)

            # Get weak categories (items with low mastery)
            now = datetime.utcnow()
            weak_categories: list[str] = []
            items = session.query(LearningItem).all()

            category_mastery: dict[ItemType, list[float]] = {}
            for item in items:
                if item.item_type not in category_mastery:
                    category_mastery[item.item_type] = []
                category_mastery[item.item_type].append(decayed_score(item, now))

            # Find categories with avg mastery < 0.5
            for cat, scores in category_mastery.items():
                if scores and sum(scores) / len(scores) < 0.5:
                    weak_categories.append(cat.value)

            return {
                "known_relevant_items": relevant_items[:limit],
                "weak_categories": weak_categories,
            }

    @classmethod
    def performance_error_patterns(
        cls, week_start: datetime, week_end: datetime
    ) -> list[dict[str, Any]]:
        """Get performance error patterns for weekly report weakness surfacing.

        Args:
            week_start: Start of the week
            week_end: End of the week

        Returns:
            List of error pattern dictionaries
        """
        with Session() as session:
            errors = (
                session.query(PerformanceError)
                .filter(
                    PerformanceError.created_at >= week_start,
                    PerformanceError.created_at < week_end,
                )
                .all()
            )

            # Group by wrong_form for pattern analysis
            pattern_counts: dict[str, dict[str, Any]] = {}

            for error in errors:
                key = error.wrong_form
                if key not in pattern_counts:
                    pattern_counts[key] = {
                        "wrong_form": error.wrong_form,
                        "correct_form": error.correct_form,
                        "count": 0,
                        "sources": set(),
                    }
                pattern_counts[key]["count"] += 1
                pattern_counts[key]["sources"].add(error.source_type.value)

            # Convert to list and sort by count
            patterns = [
                {**p, "sources": list(p["sources"])}
                for p in pattern_counts.values()
            ]
            patterns.sort(key=lambda x: x["count"], reverse=True)

            return patterns
