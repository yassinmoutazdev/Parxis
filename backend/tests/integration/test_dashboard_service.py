"""Integration tests for DashboardService.

Corresponds to ARCHITECTURE Section 17.2 (integration testing pattern, applied to dashboard).
"""

import pytest
from datetime import datetime, timedelta

from app.db.engine import Session
from app.db.models.approval import ApprovalQueue, ApprovalStatus, ApprovalSourceType
from app.dashboard.service import DashboardService


class TestDashboardOverview:
    """Tests for DashboardService.overview()"""

    def test_overview_with_no_data(self):
        """Overview returns proficiency object with null band when no data exists."""
        result = DashboardService.overview(app_state=None)

        # Proficiency is now an object (Part B: CEFR band as headline metric)
        assert result["proficiency"] is not None
        assert result["proficiency"]["band"] is None
        assert result["proficiency"]["trend"] == "steady"
        assert result["proficiency"]["last_eval_week_start"] is None
        assert result["pending_approvals_count"] == 0
        assert result["week_snapshot"]["items_studied"] == 0

    def test_overview_with_pending_approvals(self):
        """Overview returns correct pending approvals count."""
        with Session() as session:
            # Create a pending approval
            approval = ApprovalQueue(
                source_type=ApprovalSourceType.NOTE_PARSE,
                source_id=1,
                item_type="COLLOCATION",
                extracted_text="test",
                explanation="test explanation",
                source_context="test context",
                status=ApprovalStatus.PENDING,
            )
            session.add(approval)
            session.commit()

            approval_id = approval.id

        try:
            result = DashboardService.overview(app_state=None)
            assert result["pending_approvals_count"] >= 1
        finally:
            with Session() as session:
                session.query(ApprovalQueue).filter(ApprovalQueue.id == approval_id).delete()
                session.commit()


class TestDashboardMasteryByCategory:
    """Tests for DashboardService.mastery_by_category()"""

    def test_mastery_by_category_empty(self):
        """Returns empty list when no items exist."""
        result = DashboardService.mastery_by_category()
        assert result == []


class TestDashboardTrendSeries:
    """Tests for DashboardService.trend_series()"""

    def test_trend_series_empty(self):
        """Returns week entries with null values when no data exists."""
        result = DashboardService.trend_series(range_days=30)

        # Should have week entries even with no data (one week per 7 days)
        assert len(result["quiz_accuracy"]) >= 1
        assert len(result["writing_scores"]) >= 1
        assert len(result["items_learned"]) >= 1
        assert result["range_days"] == 30

        # All values should be null/empty
        for entry in result["quiz_accuracy"]:
            assert entry["accuracy"] is None
            assert entry["total_questions"] == 0