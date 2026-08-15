"""Integration tests for DashboardService.

Corresponds to ARCHITECTURE Section 17.2 (integration testing pattern, applied to dashboard).
"""

import pytest
from datetime import datetime, timedelta

from app.db.engine import Session
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
        assert result["week_snapshot"]["items_studied"] == 0
        assert "pending_approvals_count" not in result


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