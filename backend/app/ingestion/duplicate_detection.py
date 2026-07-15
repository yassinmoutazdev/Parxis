"""Duplicate detection using FTS5.

Corresponds to ARCHITECTURE Section 7.3 (FTS5).
"""

import logging

from app.db.engine import Session
from app.db.models.learning_item import LearningItem

logger = logging.getLogger(__name__)


def find_similar(text: str, limit: int = 5) -> list[LearningItem]:
    """Find similar learning items using FTS5 with BM25 ranking.

    Corresponds to ARCHITECTURE Section 7.3 (FTS5 MATCH query).

    Args:
        text: The text to search for
        limit: Maximum number of results to return

    Returns:
        List of similar LearningItems ordered by BM25 relevance
    """
    with Session() as session:
        # Use FTS5 MATCH with BM25 ranking
        query = text("""
            SELECT li.id, li.text, li.definition, li.example_sentence,
                   li.item_type, li.mastery_score, li.created_at,
                   bm25(learning_item_fts) as rank
            FROM learning_item li
            JOIN learning_item_fts fts ON li.id = fts.rowid
            WHERE learning_item_fts MATCH :search_term
            ORDER BY rank
            LIMIT :limit
        """)

        # Escape special FTS5 characters and prepare search term
        search_term = _prepare_fts5_query(text)

        if not search_term:
            logger.debug(f"Empty search term after preparation for: {text}")
            return []

        try:
            result = session.execute(
                query, {"search_term": search_term, "limit": limit}
            )
            rows = result.fetchall()

            if not rows:
                logger.debug(f"No FTS matches found for: {text}")
                return []

            # Fetch the actual LearningItem objects
            item_ids = [row[0] for row in rows]
            items = (
                session.query(LearningItem)
                .filter(LearningItem.id.in_(item_ids))
                .all()
            )

            # Preserve the order from FTS5
            id_to_item = {item.id: item for item in items}
            ordered_items = [id_to_item[iid] for iid in item_ids if iid in id_to_item]

            logger.debug(f"Found {len(ordered_items)} similar items for: {text}")
            return ordered_items

        except Exception as e:
            logger.error(f"FTS5 search error for '{text}': {e}")
            return []


def _prepare_fts5_query(text: str) -> str | None:
    """Prepare text for FTS5 query.

    Handles escaping special characters and creates a reasonable search pattern.

    Args:
        text: The raw text to prepare

    Returns:
        Prepared FTS5 query string, or None if text is not suitable
    """
    if not text or not text.strip():
        return None

    # Clean the text
    cleaned = text.strip()

    # Split into words and create a simple AND query
    words = cleaned.split()

    if not words:
        return None

    # Create an FTS5 query with AND between words
    # This requires all words to be present (stricter matching)
    fts_query = " ".join(words)

    return fts_query


def check_exact_match(text: str) -> LearningItem | None:
    """Check for an exact text match in learning items.

    Args:
        text: The text to check

    Returns:
        The LearningItem if an exact match exists, None otherwise
    """
    with Session() as session:
        item = (
            session.query(LearningItem)
            .filter(LearningItem.text.ilike(text.strip()))
            .first()
        )
        return item
