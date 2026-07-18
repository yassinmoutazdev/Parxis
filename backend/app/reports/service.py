"""Report Service for weekly progress reports.

Corresponds to ARCHITECTURE Section 6.5 (Weekly Report Assembly).
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from app.db.engine import Session
from app.db.models.learning_item import LearningItem
from app.db.models.report import WeeklyReport
from app.db.models.writing import WritingEvaluation
from app.llm import ollama_adapter
from app.llm.interface import TaskType
from app.llm.provenance import stamp_provenance
from app.llm.schemas import WeeklyNarrativeOutput
from app.retrieval.service import RetrievalService

logger = logging.getLogger(__name__)


class ReportService:
    """Service for generating weekly progress reports.

    Handles the weekly review assembly: gathering quiz/writing data,
    computing mastery snapshots, and generating narrative reports.
    """

    @classmethod
    def get_week_boundary(cls, reference_date: datetime | None = None) -> tuple[date, date]:
        """Compute the Monday–Sunday week boundary.

        PRD Section 19.1 (Week Boundary Definition):
        - Week runs Monday through Sunday
        - If reference_date is Sunday, that week is complete
        - If reference_date is any other day, the current week is in progress

        Args:
            reference_date: Date to compute week for (defaults to now)

        Returns:
            Tuple of (week_start, week_end) as date objects
        """
        if reference_date is None:
            reference_date = datetime.utcnow()

        # Get the weekday (Monday=0, Sunday=6)
        weekday = reference_date.weekday()

        # Calculate Monday of this week
        days_since_monday = weekday
        week_start = (reference_date - timedelta(days=days_since_monday)).date()

        # Calculate Sunday of this week
        days_until_sunday = 6 - weekday
        week_end = (reference_date + timedelta(days=days_until_sunday)).date()

        return week_start, week_end

    @classmethod
    async def assemble(
        cls,
        week_start: date | None = None,
        week_end: date | None = None,
    ) -> WeeklyReport:
        """Assemble a weekly progress report.

        ARCHITECTURE Section 6.5 (sequence diagram):
        1. Compute week boundary (Monday–Sunday) if not provided
        2. Get items created this week via RetrievalService
        3. Get quiz summary via RetrievalService
        4. Get mini writing summary via RetrievalService
        5. Get weekly writing evaluation via RetrievalService
        6. Get mastery snapshot via category_mastery_snapshot()
        7. Generate narrative via Generator
        8. INSERT WeeklyReport
        9. Return the report

        PRD Section 19.2 (Adaptive Content Volume):
        - If zero items studied, skip quiz step and note it explicitly

        Args:
            week_start: Start date of the week (optional, computed if not provided)
            week_end: End date of the week (optional, computed if not provided)

        Returns:
            The created WeeklyReport
        """
        # Compute week boundary if not provided
        if week_start is None or week_end is None:
            computed_start, computed_end = cls.get_week_boundary()
            week_start = week_start or computed_start
            week_end = week_end or computed_end

        # Convert dates to datetime for RetrievalService queries
        week_start_dt = datetime.combine(week_start, datetime.min.time())
        week_end_dt = datetime.combine(week_end, datetime.max.time())

        with Session() as session:
            # Get items created this week
            items_this_week = RetrievalService.items_created_between(
                week_start_dt, week_end_dt
            )
            items_studied_count = len(items_this_week)

            # Get quiz summary
            quiz_summary = RetrievalService.quiz_summary_for_week(
                week_start_dt, week_end_dt
            )

            # Get mini writing summary
            mini_writing_summary = RetrievalService.mini_writing_summary_for_week(
                week_start_dt, week_end_dt
            )

            # Get weekly writing evaluation
            weekly_writing_eval = RetrievalService.weekly_writing_eval_for_week(
                week_start_dt, week_end_dt
            )

            # Get mastery snapshot (category mastery at point-in-time)
            mastery_snapshot = cls._category_mastery_snapshot()

            # Generate narrative
            narrative_context = {
                "quiz_summary": quiz_summary,
                "mini_writing_summary": mini_writing_summary,
                "weekly_writing_eval": cls._format_writing_eval(weekly_writing_eval),
                "items_studied_count": items_studied_count,
            }

            try:
                narrative_result = await ollama_adapter.ollama_adapter.generate(
                    task=TaskType.WEEKLY_NARRATIVE,
                    context=narrative_context,
                    output_schema=WeeklyNarrativeOutput,
                )

                narrative_report = narrative_result.narrative_report
                top_strengths = narrative_result.top_strengths_this_week
                top_focus_areas = narrative_result.top_focus_areas_next_week

                # Get provenance (ADR-13)
                provenance = stamp_provenance(prompt_version="1.0.0")

            except Exception as e:
                logger.error(f"Failed to generate weekly narrative: {e}")
                # Fallback narrative
                narrative_report = f"This week you studied {items_studied_count} items."

            # Create the weekly report
            report = WeeklyReport(
                week_start=week_start,
                week_end=week_end,
                items_studied_count=items_studied_count,
                quiz_summary_json=quiz_summary,
                mini_writing_summary_json=mini_writing_summary,
                weekly_writing_evaluation_id=weekly_writing_eval.id if weekly_writing_eval else None,
                mastery_snapshot_json=mastery_snapshot,
                narrative_report=narrative_report,
            )
            session.add(report)
            session.commit()
            session.refresh(report)

            return report

    @classmethod
    def _category_mastery_snapshot(cls) -> dict[str, Any]:
        """Get point-in-time category mastery snapshot.

        This creates a snapshot of current mastery by category for the report.
        Called at report-creation time; freezes the state at that moment.

        Returns:
            Dictionary with category mastery data
        """
        with Session() as session:
            now = datetime.utcnow()

            # Get all items
            items = session.query(LearningItem).all()

            # Calculate decayed scores by category
            from app.scheduler.mastery import decayed_score

            category_mastery: dict[str, dict[str, Any]] = {}

            for item in items:
                cat = item.item_type.value
                if cat not in category_mastery:
                    category_mastery[cat] = {
                        "items": 0,
                        "total_mastery": 0.0,
                        "average_mastery": 0.0,
                    }

                category_mastery[cat]["items"] += 1
                decayed = decayed_score(item, now)
                category_mastery[cat]["total_mastery"] += decayed

            # Calculate averages
            for cat, data in category_mastery.items():
                if data["items"] > 0:
                    data["average_mastery"] = data["total_mastery"] / data["items"]

            return category_mastery

    @classmethod
    def _format_writing_eval(cls, evaluation: WritingEvaluation | None) -> dict[str, Any]:
        """Format weekly writing evaluation for narrative context.

        Args:
            evaluation: The WritingEvaluation to format, or None

        Returns:
            Dictionary with formatted writing evaluation data
        """
        if not evaluation:
            return {
                "completed": False,
                "overall_score": None,
            }

        return {
            "completed": True,
            "overall_score": evaluation.overall_score,
            "grammar_score": evaluation.grammar_score,
            "naturalness_score": evaluation.naturalness_score,
            "vocabulary_score": evaluation.vocabulary_score,
            "coherence_score": evaluation.coherence_score,
        }

    @classmethod
    def get_reports(cls, limit: int = 10) -> list[WeeklyReport]:
        """Get recent weekly reports.

        Args:
            limit: Maximum number of reports to return

        Returns:
            List of WeeklyReports, ordered by week_start descending
        """
        with Session() as session:
            return (
                session.query(WeeklyReport)
                .order_by(WeeklyReport.week_start.desc())
                .limit(limit)
                .all()
            )

    @classmethod
    def get_report(cls, report_id: int) -> WeeklyReport | None:
        """Get a weekly report by ID.

        Args:
            report_id: The report ID

        Returns:
            The WeeklyReport if found
        """
        with Session() as session:
            return session.get(WeeklyReport, report_id)

    @classmethod
    def get_report_by_week(cls, week_start: date) -> WeeklyReport | None:
        """Get a weekly report by week start date.

        Args:
            week_start: The start date of the week

        Returns:
            The WeeklyReport if found
        """
        with Session() as session:
            return (
                session.query(WeeklyReport)
                .filter(WeeklyReport.week_start == week_start)
                .first()
            )

    @classmethod
    def get_current_week_report(cls) -> WeeklyReport | None:
        """Get the current week's report if it exists.

        Returns:
            The current week's WeeklyReport if it exists
        """
        week_start, _ = cls.get_week_boundary()
        return cls.get_report_by_week(week_start)
