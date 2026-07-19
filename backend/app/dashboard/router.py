"""Dashboard API router.

Corresponds to ARCHITECTURE Section 6.6 (Dashboard Refresh sequence).
"""

import logging
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.dashboard.service import DashboardService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class OverviewResponse(BaseModel):
    """Response for dashboard overview endpoint."""

    proficiency: float | None
    category_mastery_avg: float | None
    writing_performance_avg: float | None
    pending_approvals_count: int
    week_snapshot: dict[str, int]
    health: dict[str, Any]


class MasteryCategoryResponse(BaseModel):
    """Response for mastery breakdown endpoint."""

    categories: list[dict[str, Any]]


class TrendSeriesResponse(BaseModel):
    """Response for trends endpoint."""

    quiz_accuracy: list[dict[str, Any]]
    writing_scores: list[dict[str, Any]]
    items_learned: list[dict[str, Any]]
    range_days: int


class ItemBrowserResponse(BaseModel):
    """Response for item browser endpoint."""

    items: list[dict[str, Any]]
    total: int


@router.get("/overview")
async def get_overview(request: Request) -> OverviewResponse:
    """Get dashboard overview with proficiency, pending approvals, and health.

    This endpoint returns:
    - proficiency: blended score (40% item mastery / 60% writing performance)
    - category_mastery_avg: raw category mastery average
    - writing_performance_avg: recent writing performance average
    - pending_approvals_count: count of items awaiting approval
    - week_snapshot: this week's activity stats
    - health: VaultWatcher status
    """
    app_state = getattr(request.app, "state", None)
    overview = DashboardService.overview(app_state)

    return OverviewResponse(**overview)


@router.get("/mastery-breakdown")
async def get_mastery_breakdown() -> MasteryCategoryResponse:
    """Get mastery breakdown by category.

    Returns decayed mastery scores aggregated by item_type,
    weighted by review_count per PRD Section 17.4.
    """
    categories = DashboardService.mastery_by_category()

    return MasteryCategoryResponse(categories=categories)


@router.get("/trends")
async def get_trends(
    range_days: int = Query(default=90, ge=7, le=365)
) -> TrendSeriesResponse:
    """Get trend series data for charts.

    Args:
        range_days: Number of days to look back (default 90, min 7, max 365)

    Returns:
        quiz_accuracy: Quiz accuracy per week
        writing_scores: Writing 5-dimension scores per week
        items_learned: New items learned per week
    """
    trends = DashboardService.trend_series(range_days)

    return TrendSeriesResponse(**trends)


@router.get("/items")
async def get_items(
    search: str | None = Query(default=None, description="FTS5 text search"),
    item_type: str | None = Query(default=None, description="Filter by item type"),
    tag: str | None = Query(default=None, description="Filter by tag name"),
    min_mastery: float | None = Query(default=None, ge=0, le=1, description="Minimum mastery score"),
    max_mastery: float | None = Query(default=None, ge=0, le=1, description="Maximum mastery score"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ItemBrowserResponse:
    """Get learning items with optional filtering.

    Supports FTS5 text search combined with item_type/tag/mastery-range filters.

    Args:
        search: Text to search (FTS5 MATCH)
        item_type: Filter by item_type enum value
        tag: Filter by tag name
        min_mastery: Minimum decayed mastery score (0-1)
        max_mastery: Maximum decayed mastery score (0-1)
        limit: Max items to return
        offset: Pagination offset
    """
    from app.db.engine import Session
    from app.db.models.learning_item import LearningItem, LearningItemTag, Tag

    with Session() as session:
        query = session.query(LearningItem)

        # Apply FTS5 text search if provided
        if search:
            # Use FTS5 to search the virtual table
            # Note: This joins with learning_item_fts which is managed by triggers
            fts_query = """
                SELECT rowid FROM learning_item_fts WHERE learning_item_fts MATCH ?
            """
            cursor = session.execute(
                fts_query,
                (f"{search}*",)
            )
            fts_row_ids = [row[0] for row in cursor.fetchall()]

            if fts_row_ids:
                query = query.filter(LearningItem.id.in_(fts_row_ids))
            else:
                # No matches found
                return ItemBrowserResponse(items=[], total=0)

        # Apply item_type filter
        if item_type:
            from app.db.models.learning_item import ItemType
            try:
                item_type_enum = ItemType(item_type)
                query = query.filter(LearningItem.item_type == item_type_enum)
            except ValueError:
                pass  # Invalid item_type, ignore filter

        # Apply tag filter
        if tag:
            query = (
                query.join(LearningItemTag)
                .join(Tag)
                .filter(Tag.name == tag)
            )

        # Apply mastery range filter (using decayed score)
        # Note: We need to fetch all and filter in Python since decayed_score is computed
        all_items = query.all()

        from app.scheduler.mastery import decayed_score

        filtered_items = []
        for item in all_items:
            decayed = decayed_score(item)
            if min_mastery is not None and decayed < min_mastery:
                continue
            if max_mastery is not None and decayed > max_mastery:
                continue
            filtered_items.append(item)

        total = len(filtered_items)
        paginated_items = filtered_items[offset:offset + limit]

        # Get tags for each item
        item_ids = [item.id for item in paginated_items]
        tags_by_item: dict[int, list[str]] = {item_id: [] for item_id in item_ids}

        if item_ids:
            item_tags = (
                session.query(LearningItemTag, Tag)
                .join(Tag, LearningItemTag.tag_id == Tag.id)
                .filter(LearningItemTag.learning_item_id.in_(item_ids))
                .all()
            )

            for item_tag, tag in item_tags:
                if item_tag.learning_item_id in tags_by_item:
                    tags_by_item[item_tag.learning_item_id].append(tag.name)

        items_data = []
        for item in paginated_items:
            decayed = decayed_score(item)
            items_data.append({
                "id": item.id,
                "item_type": item.item_type.value,
                "text": item.text,
                "definition": item.definition,
                "example_sentence": item.example_sentence,
                "mastery_score": item.mastery_score,
                "decayed_mastery_score": round(decayed, 3),
                "review_count": item.review_count,
                "correct_count": item.correct_count,
                "incorrect_count": item.incorrect_count,
                "last_reviewed_at": item.last_reviewed_at.isoformat() if item.last_reviewed_at else None,
                "next_review_due": item.next_review_due.isoformat() if item.next_review_due else None,
                "suspended": item.suspended,
                "tags": tags_by_item.get(item.id, []),
                "created_at": item.created_at.isoformat() if item.created_at else None,
            })

        return ItemBrowserResponse(items=items_data, total=total)
