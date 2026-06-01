"""TDD tests for create_transaction_from_receipt_impl MCP tool."""
import base64
import uuid
from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import MagicMock, patch

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
    t.transfer_fee = overrides.get("transfer_fee", Decimal("0"))
    t.receipt_file_id = overrides.get("receipt_file_id", uuid7())
    t.receipt_url = overrides.get("receipt_url", f"/files/{t.receipt_file_id}")
    t.user_id = user_id or uuid7()
    t.created_at = datetime.now(UTC)
    t.updated_at = datetime.now(UTC)
    return t


def make_file_upload(user_id=None):
    f = MagicMock()
    f.id = uuid7()
    f.user_id = user_id or uuid7()
    f.filename = "receipt.jpg"
    f.content_type = "image/jpeg"
    f.size_bytes = 1024
    f.storage_key = f"uploads/{f.user_id}/receipts/{f.id}.jpg"
    f.is_orphan = False
    f.created_at = datetime.now(UTC)
    return f


def setup_context(user, db):
    from app.mcp.context import _current_user_var, _current_db_var
    t1 = _current_user_var.set(user)
    t2 = _current_db_var.set(db)
    return t1, t2


def reset_context(t1, t2):
    from app.mcp.context import _current_user_var, _current_db_var
    _current_user_var.reset(t1)
    _current_db_var.reset(t2)


def valid_base64_image():
    """Return a minimal valid base64-encoded JPEG image."""
    # Minimal JPEG: SOI marker + APP0 + EOI marker
    jpeg_bytes = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9'
    return base64.b64encode(jpeg_bytes).decode("utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_transaction_from_receipt_success():
    from app.mcp.tools import create_transaction_from_receipt_impl

    user = make_user()
    account = make_account(user_id=user.id)
    category = make_category(user_id=user.id)
    mock_db = MagicMock()
    file_upload = make_file_upload(user_id=user.id)
    mock_tx = make_transaction(user_id=user.id, receipt_file_id=file_upload.id)

    t1, t2 = setup_context(user, mock_db)
    try:
        with (
            patch("app.mcp.tools.upload_file_to_storage", return_value=file_upload),
            patch("app.mcp.tools.validate_account", return_value=account),
            patch("app.mcp.tools.validate_category", return_value=category),
            patch("app.mcp.tools.validate_transaction_category_match"),
            patch("app.mcp.tools.validate_transfer"),
            patch("app.mcp.tools.prepare_transaction_for_db", return_value=mock_tx) as mock_prep,
        ):
            result = await create_transaction_from_receipt_impl(
                base64_image=valid_base64_image(),
                media_type="image/jpeg",
                transaction_date="2026-06-01T12:00:00",
                description="Grocery receipt",
                amount=50.00,
                transaction_type="expense",
                account_id=str(account.id),
                category_id=str(category.id),
            )
            # Verify prepare_transaction_for_db was called with correct data
            call_args = mock_prep.call_args[0][0]
            assert call_args["description"] == "Grocery receipt"
            assert call_args["amount"] == 50.00
            # Verify receipt_file_id was set on the transaction
            assert mock_tx.receipt_file_id == file_upload.id
            # Verify result comes from _serialize_transaction
            assert result["id"] is not None
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_create_transaction_from_receipt_invalid_media_type():
    from app.mcp.tools import create_transaction_from_receipt_impl

    user = make_user()
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(ValueError, match="Unsupported image type"):
            await create_transaction_from_receipt_impl(
                base64_image=valid_base64_image(),
                media_type="application/pdf",
                transaction_date="2026-06-01T12:00:00",
                description="Receipt",
                amount=50.00,
                transaction_type="expense",
                account_id=str(uuid7()),
            )
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_create_transaction_from_receipt_invalid_base64():
    from app.mcp.tools import create_transaction_from_receipt_impl

    user = make_user()
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        with pytest.raises(ValueError, match="Invalid base64"):
            await create_transaction_from_receipt_impl(
                base64_image="not-valid-base64!!!",
                media_type="image/jpeg",
                transaction_date="2026-06-01T12:00:00",
                description="Receipt",
                amount=50.00,
                transaction_type="expense",
                account_id=str(uuid7()),
            )
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_create_transaction_from_receipt_oversized_image():
    from app.mcp.tools import create_transaction_from_receipt_impl

    user = make_user()
    mock_db = MagicMock()
    t1, t2 = setup_context(user, mock_db)
    try:
        # Create base64 that decodes to > 10MB
        big_bytes = b'\x00' * (10 * 1024 * 1024 + 1)
        big_b64 = base64.b64encode(big_bytes).decode("utf-8")
        with pytest.raises(ValueError, match="exceeds 10MB"):
            await create_transaction_from_receipt_impl(
                base64_image=big_b64,
                media_type="image/jpeg",
                transaction_date="2026-06-01T12:00:00",
                description="Receipt",
                amount=50.00,
                transaction_type="expense",
                account_id=str(uuid7()),
            )
    finally:
        reset_context(t1, t2)


@pytest.mark.asyncio
async def test_create_transaction_from_receipt_invalid_account():
    from app.mcp.tools import create_transaction_from_receipt_impl

    user = make_user()
    mock_db = MagicMock()
    file_upload = make_file_upload(user_id=user.id)

    t1, t2 = setup_context(user, mock_db)
    try:
        with (
            patch("app.mcp.tools.upload_file_to_storage", return_value=file_upload),
            patch("app.mcp.tools.validate_account", side_effect=ValueError("Account not found")),
        ):
            with pytest.raises(ValueError, match="Account not found"):
                await create_transaction_from_receipt_impl(
                    base64_image=valid_base64_image(),
                    media_type="image/jpeg",
                    transaction_date="2026-06-01T12:00:00",
                    description="Receipt",
                    amount=50.00,
                    transaction_type="expense",
                    account_id=str(uuid7()),
                )
    finally:
        reset_context(t1, t2)
