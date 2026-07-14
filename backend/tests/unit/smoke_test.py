"""Smoke test for pytest fixtures."""


from app.db.models.approval import ApprovalQueue, ApprovalSourceType, ApprovalStatus
from app.db.models.learning_item import ItemType, LearningItem


def test_temp_db_creates_file(temp_db_path):
    """Test that temp_db_path fixture creates a file."""
    assert temp_db_path.exists()


def test_engine_creates_tables(test_engine):
    """Test that the test engine creates tables."""
    from sqlalchemy import inspect

    inspector = inspect(test_engine)
    tables = inspector.get_table_names()
    assert "learning_item" in tables


def test_session_can_query(test_session):
    """Test that test session can query the database."""
    # First create an approval queue record (required for FK)
    approval = ApprovalQueue(
        source_type=ApprovalSourceType.NOTE_PARSE,
        source_id=1,
        item_type="COLLOCATION",
        extracted_text="test",
        source_context="test context",
        status=ApprovalStatus.PENDING,
    )
    test_session.add(approval)
    test_session.commit()

    # Then create a learning item
    item = LearningItem(
        item_type=ItemType.COLLOCATION,
        text="test collocation",
        definition="A test definition",
        source_approval_id=approval.id,
    )
    test_session.add(item)
    test_session.commit()

    # Query it back using SQLModel style
    result = test_session.get(LearningItem, item.id)

    assert result is not None
    assert result.text == "test collocation"
    assert result.item_type == ItemType.COLLOCATION
