"""TDD tests for MCP tool implementations — permission checks + logic."""
import uuid
from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from app.utils.uuid import uuid7


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username="testuser", is_superuser=False):
    user = MagicMock()
    user.id = uuid7()
    user.username = username
    user.email = f"{username}@example.com"
    user.is_superuser = is_superuser
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    return user


def make_post(user_id=None, **overrides):
    post = MagicMock()
    post.id = uuid7()
    post.title = overrides.get("title", "Test Post")
    post.slug = overrides.get("slug", "test-post")
    post.content = overrides.get("content", "Some content here")
    post.excerpt = overrides.get("excerpt", "An excerpt")
    post.tags = overrides.get("tags", ["python", "fastapi"])
    post.published = overrides.get("published", True)
    post.reading_time = overrides.get("reading_time", 3)
    post.user_id = user_id or uuid7()
    post.embedding = None
    post.created_at = datetime.now(UTC)
    post.updated_at = datetime.now(UTC)
    return post


def make_account(user_id=None, **overrides):
    a = MagicMock()
    a.id = uuid7()
    a.name = overrides.get("name", "Test Account")
    a.type = MagicMock()
    a.type.value = overrides.get("type", "bank_account")
    a.description = overrides.get("description", "A test account")
    a.limit = overrides.get("limit", None)
    a.account_number = overrides.get("account_number", "123456")
    a.user_id = user_id or uuid7()
    return a


def make_category(user_id=None, **overrides):
    c = MagicMock()
    c.id = uuid7()
    c.name = overrides.get("name", "Food")
    c.type = MagicMock()
    c.type.value = overrides.get("type", "expense")
    c.user_id = user_id or uuid7()
    c.created_at = datetime.now(UTC)
    c.updated_at = datetime.now(UTC)
    return c


def make_transaction(user_id=None, **overrides):
    t = MagicMock()
    t.id = uuid7()
    t.transaction_date = overrides.get("transaction_date", datetime.now(UTC))
    t.description = overrides.get("description", "Lunch")
    t.amount = overrides.get("amount", Decimal("25.50"))
    t.transaction_type = MagicMock()
    t.transaction_type.value = overrides.get("transaction_type", "expense")
    t.account_id = overrides.get("account_id", uuid7())
    t.category_id = overrides.get("category_id", uuid7())
    t.destination_account_id = overrides.get("destination_account_id", None)
    t.transfer_fee = overrides.get("transfer_fee", None)
    t.receipt_file_id = overrides.get("receipt_file_id", None)
    t.receipt_url = overrides.get("receipt_url", None)
    t.user_id = user_id or uuid7()
    t.created_at = datetime.now(UTC)
    t.updated_at = datetime.now(UTC)
    return t


def setup_context(user, db):
    """Set MCP context vars and return tokens for cleanup."""
    from app.mcp.context import _current_user_var, _current_db_var
    t1 = _current_user_var.set(user)
    t2 = _current_db_var.set(db)
    return t1, t2


def reset_context(t1, t2):
    from app.mcp.context import _current_user_var, _current_db_var
    _current_user_var.reset(t1)
    _current_db_var.reset(t2)


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_superuser_passes():
    from app.mcp.context import _current_user_var
    from app.mcp.tools import _require_superuser

    user = make_user(is_superuser=True)
    tok = _current_user_var.set(user)
    try:
        _require_superuser()  # should not raise
    finally:
        _current_user_var.reset(tok)


@pytest.mark.asyncio
async def test_require_superuser_fails_non_superuser():
    from app.mcp.context import _current_user_var
    from app.mcp.tools import _require_superuser

    user = make_user(is_superuser=False)
    tok = _current_user_var.set(user)
    try:
        with pytest.raises(PermissionError, match="Superuser"):
            _require_superuser()
    finally:
        _current_user_var.reset(tok)


@pytest.mark.asyncio
async def test_require_superuser_fails_guest_superuser():
    """Guest + superuser should still be rejected."""
    from app.mcp.context import _current_user_var
    from app.mcp.tools import _require_superuser

    user = make_user(username="guest", is_superuser=True)
    tok = _current_user_var.set(user)
    try:
        with pytest.raises(PermissionError, match="Superuser"):
            _require_superuser()
    finally:
        _current_user_var.reset(tok)


@pytest.mark.asyncio
async def test_require_not_guest_passes():
    from app.mcp.context import _current_user_var
    from app.mcp.tools import _require_not_guest

    user = make_user(username="alice")
    tok = _current_user_var.set(user)
    try:
        _require_not_guest()  # should not raise
    finally:
        _current_user_var.reset(tok)


@pytest.mark.asyncio
async def test_require_not_guest_fails():
    from app.mcp.context import _current_user_var
    from app.mcp.tools import _require_not_guest

    user = make_user(username="guest")
    tok = _current_user_var.set(user)
    try:
        with pytest.raises(PermissionError, match="Guest"):
            _require_not_guest()
    finally:
        _current_user_var.reset(tok)


# ---------------------------------------------------------------------------
# Blog tools — permissions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_post_requires_superuser():
    from app.mcp.tools import create_post_impl

    user = make_user(is_superuser=False)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(PermissionError, match="Superuser"):
            await create_post_impl(title="T", content="C")
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_update_post_requires_superuser():
    from app.mcp.tools import update_post_impl

    user = make_user(is_superuser=False)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(PermissionError, match="Superuser"):
            await update_post_impl(post_id=str(uuid7()), title="T", content="C")
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_delete_post_requires_superuser():
    from app.mcp.tools import delete_post_impl

    user = make_user(is_superuser=False)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(PermissionError, match="Superuser"):
            await delete_post_impl(post_id=str(uuid7()))
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_delete_post_not_found():
    from app.mcp.tools import delete_post_impl

    user = make_user(is_superuser=True)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(LookupError):
            await delete_post_impl(post_id=str(uuid7()))
    finally:
        reset_context(t1, t2)


# ---------------------------------------------------------------------------
# Blog tools — logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_post_impl_found():
    from app.mcp.tools import get_post_impl

    post = make_post(slug="my-post")
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = post

    user = make_user()
    t1, t2 = setup_context(user, mock_db)
    try:
        result = await get_post_impl("my-post")
        assert result["slug"] == "my-post"
        assert result["title"] == "Test Post"
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_get_post_impl_not_found():
    from app.mcp.tools import get_post_impl

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    user = make_user()
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(LookupError):
            await get_post_impl("nonexistent")
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_list_posts_impl_cursor_pagination():
    from app.mcp.tools import list_posts_impl

    p1 = make_post()
    p2 = make_post()

    mock_query = MagicMock()
    mock_query.count.return_value = 2
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value.limit.return_value.all.return_value = [p1, p2]

    mock_db = MagicMock()
    mock_db.query.return_value = mock_query

    user = make_user()
    t1, t2 = setup_context(user, mock_db)
    try:
        result = await list_posts_impl(limit=10, cursor="2026-01-01T00:00:00")
        assert "items" in result
        assert "next_cursor" in result
        assert "has_more" in result
    finally:
        reset_context(t1, t2)


# ---------------------------------------------------------------------------
# Cuan — account CRUD permissions (guest allowed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_account_allows_regular_user():
    from app.mcp.tools import create_account_impl

    user = make_user(is_superuser=False)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with (
            patch("app.mcp.tools.prepare_account_for_db") as mock_prep,
            patch("app.mcp.tools.create_credit_card_initial_transaction"),
        ):
            mock_account = make_account()
            mock_prep.return_value = mock_account
            result = await create_account_impl(name="Bank", type="bank_account")
            assert result["name"] == "Test Account"
    finally:
        reset_context(t1, t2)


# ---------------------------------------------------------------------------
# Cuan — category CRUD permissions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_category_allows_regular_user():
    from app.mcp.tools import create_category_impl

    user = make_user()
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with patch("app.mcp.tools.prepare_category_for_db") as mock_prep:
            mock_cat = make_category()
            mock_prep.return_value = mock_cat
            result = await create_category_impl(name="Food", type="expense")
            assert result["name"] == "Food"
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_update_category_allows_regular_user():
    from app.mcp.tools import update_category_impl

    user = make_user()
    cat = make_category(user_id=user.id)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with patch("app.mcp.tools.validate_category", return_value=cat):
            result = await update_category_impl(str(cat.id), "New Name", "income")
            assert result["name"] == "New Name"
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_delete_category_allows_regular_user():
    from app.mcp.tools import delete_category_impl

    user = make_user()
    cat = make_category(user_id=user.id)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with (
            patch("app.mcp.tools.validate_category", return_value=cat),
            patch("app.mcp.tools.prepare_deleted_category_info", return_value={"id": str(cat.id), "name": cat.name}),
        ):
            result = await delete_category_impl(str(cat.id))
            assert "deleted_item" in result
    finally:
        reset_context(t1, t2)


# ---------------------------------------------------------------------------
# Cuan — transaction CRUD permissions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_transaction_allows_regular_user():
    from app.mcp.tools import create_transaction_impl

    user = make_user()
    account = make_account(user_id=user.id)
    category = make_category(user_id=user.id)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with (
            patch("app.mcp.tools.validate_account", return_value=account),
            patch("app.mcp.tools.validate_category", return_value=category),
            patch("app.mcp.tools.validate_transaction_category_match"),
            patch("app.mcp.tools.validate_transfer"),
            patch("app.mcp.tools.prepare_transaction_for_db") as mock_prep,
        ):
            mock_tx = make_transaction()
            mock_prep.return_value = mock_tx
            result = await create_transaction_impl(
                transaction_date="2026-05-30T12:00:00",
                description="Lunch",
                amount=25.50,
                transaction_type="expense",
                account_id=str(account.id),
                category_id=str(category.id),
            )
            assert result["description"] == "Lunch"
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_delete_transaction_not_found():
    from app.mcp.tools import delete_transaction_impl

    user = make_user()
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(LookupError):
            await delete_transaction_impl(str(uuid7()))
    finally:
        reset_context(t1, t2)


# ---------------------------------------------------------------------------
# Cuan — statistics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_financial_summary_empty():
    from app.mcp.tools import get_financial_summary_impl

    user = make_user()
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value.group_by.return_value.all.return_value = []
    mock_db.query.return_value = mock_query

    t1, t2 = setup_context(user, mock_db)
    try:
        with patch("app.mcp.tools.calculate_date_range", return_value=(
            datetime(2026, 5, 1), datetime(2026, 5, 31)
        )):
            result = await get_financial_summary_impl()
            assert result["totals"]["income"] == 0.0
            assert result["totals"]["expense"] == 0.0
            assert result["totals"]["net"] == 0.0
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_category_distribution_empty():
    from app.mcp.tools import get_category_distribution_impl

    user = make_user()
    mock_db = MagicMock()

    mock_outerjoin = MagicMock()
    mock_outerjoin.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []

    mock_sum_query = MagicMock()
    mock_sum_query.filter.return_value.scalar.return_value = Decimal("0")

    call_count = [0]
    def query_side_effect(*args):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_outerjoin
        return mock_sum_query

    mock_db.query.side_effect = query_side_effect

    t1, t2 = setup_context(user, mock_db)
    try:
        with patch("app.mcp.tools.calculate_date_range", return_value=(
            datetime(2026, 5, 1), datetime(2026, 5, 31)
        )):
            result = await get_category_distribution_impl()
            assert result["total"] == 0
            assert result["categories"] == []
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_trends_empty():
    from app.mcp.tools import get_trends_impl

    user = make_user()
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []
    mock_db.query.return_value = mock_query

    t1, t2 = setup_context(user, mock_db)
    try:
        with patch("app.mcp.tools.calculate_date_range", return_value=(
            datetime(2026, 5, 1), datetime(2026, 5, 31)
        )):
            result = await get_trends_impl()
            assert result["trends"] == []
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_account_summary_empty():
    from app.mcp.tools import get_account_summary_impl

    user = make_user()
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with patch("app.mcp.tools.get_accounts_with_balance", return_value=[]):
            result = await get_account_summary_impl()
            assert result["total_balance"] == 0
            assert result["accounts"] == []
    finally:
        reset_context(t1, t2)


# ---------------------------------------------------------------------------
# File tools — permissions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_orphans_requires_superuser():
    from app.mcp.tools import cleanup_orphans_impl

    user = make_user(is_superuser=False)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(PermissionError, match="Superuser"):
            await cleanup_orphans_impl()
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_cleanup_guest_data_requires_superuser():
    from app.mcp.tools import cleanup_guest_data_impl

    user = make_user(is_superuser=False)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(PermissionError, match="Superuser"):
            await cleanup_guest_data_impl()
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_list_files_calls_db():
    from app.mcp.tools import list_files_impl

    user = make_user()
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    t1, t2 = setup_context(user, mock_db)
    try:
        result = await list_files_impl()
        assert result == []
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_delete_file_not_found():
    from app.mcp.tools import delete_file_impl

    user = make_user()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    mock_db = MagicMock()
    mock_db.query.return_value = mock_query

    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(ValueError, match="not found"):
            await delete_file_impl(str(uuid7()))
    finally:
        reset_context(t1, t2)


# ---------------------------------------------------------------------------
# Auth tools — permissions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_user_requires_superuser():
    from app.mcp.tools import register_user_impl

    user = make_user(is_superuser=False)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(PermissionError, match="Superuser"):
            await register_user_impl("new", "new@e.com", "pass")
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_delete_user_requires_superuser():
    from app.mcp.tools import delete_user_impl

    user = make_user(is_superuser=False)
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(PermissionError, match="Superuser"):
            await delete_user_impl(str(uuid7()))
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_delete_user_cannot_delete_self():
    from app.mcp.tools import delete_user_impl

    user = make_user(is_superuser=True)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = user

    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(PermissionError, match="Cannot delete your own"):
            await delete_user_impl(str(user.id))
    finally:
        reset_context(t1, t2)
