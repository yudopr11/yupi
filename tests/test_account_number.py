"""TDD tests for account_number field on TrxAccount."""
from datetime import datetime, UTC
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def test_bank_account_requires_account_number():
    from app.schemas.cuan import TrxAccountCreate
    with pytest.raises(ValidationError):
        TrxAccountCreate(name="BCA", type="bank_account")


def test_credit_card_requires_account_number():
    from app.schemas.cuan import TrxAccountCreate
    with pytest.raises(ValidationError):
        TrxAccountCreate(name="Visa", type="credit_card", limit=5000)


def test_other_account_number_optional():
    from app.schemas.cuan import TrxAccountCreate
    schema = TrxAccountCreate(name="Cash", type="other")
    assert schema.account_number is None


def test_bank_account_with_account_number_ok():
    from app.schemas.cuan import TrxAccountCreate
    schema = TrxAccountCreate(name="BCA", type="bank_account", account_number="1234567890")
    assert schema.account_number == "1234567890"


def test_credit_card_with_account_number_ok():
    from app.schemas.cuan import TrxAccountCreate
    schema = TrxAccountCreate(name="Visa", type="credit_card", limit=5000, account_number="4111111111111111")
    assert schema.account_number == "4111111111111111"


def test_response_schema_includes_account_number():
    from app.schemas.cuan import TrxAccountResponseData
    import uuid
    data = TrxAccountResponseData(
        id=uuid.uuid4(),
        name="BCA",
        type="bank_account",
        account_number="9876543210",
        user_id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert data.account_number == "9876543210"


# ---------------------------------------------------------------------------
# prepare_account_for_db
# ---------------------------------------------------------------------------

def test_prepare_account_passes_account_number():
    from app.utils.cuan_helpers import prepare_account_for_db
    from app.models.cuan import TrxAccountType

    account = prepare_account_for_db(
        {"name": "Mandiri", "type": TrxAccountType.BANK_ACCOUNT, "description": None, "limit": None, "account_number": "1122334455"},
        uuid4(),
    )
    assert account.account_number == "1122334455"


def test_prepare_account_other_no_account_number():
    from app.utils.cuan_helpers import prepare_account_for_db
    from app.models.cuan import TrxAccountType

    account = prepare_account_for_db(
        {"name": "Cash", "type": TrxAccountType.OTHER, "description": None, "limit": None, "account_number": None},
        uuid4(),
    )
    assert account.account_number is None


# ---------------------------------------------------------------------------
# _serialize_account
# ---------------------------------------------------------------------------

def test_serialize_account_includes_account_number():
    from app.mcp.tools import _serialize_account

    mock_account = MagicMock()
    mock_account.id = uuid4()
    mock_account.name = "BCA"
    mock_account.type = MagicMock()
    mock_account.type.value = "bank_account"
    mock_account.description = None
    mock_account.limit = None
    mock_account.account_number = "5566778899"

    result = _serialize_account(mock_account)
    assert result["account_number"] == "5566778899"


def test_serialize_account_number_none():
    from app.mcp.tools import _serialize_account

    mock_account = MagicMock()
    mock_account.id = uuid4()
    mock_account.name = "Cash"
    mock_account.type = MagicMock()
    mock_account.type.value = "other"
    mock_account.description = None
    mock_account.limit = None
    mock_account.account_number = None

    result = _serialize_account(mock_account)
    assert result["account_number"] is None


# ---------------------------------------------------------------------------
# MCP tool: create_account_impl
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_account_impl_passes_account_number():
    from app.mcp.context import _current_user_var, _current_db_var
    from app.mcp.tools import create_account_impl

    user = MagicMock()
    user.id = uuid4()
    user.username = "alice"

    mock_account = MagicMock()
    mock_account.id = uuid4()
    mock_account.name = "BCA"
    mock_account.type = MagicMock()
    mock_account.type.value = "bank_account"
    mock_account.description = None
    mock_account.limit = None
    mock_account.account_number = "1234567890"

    mock_db = MagicMock()
    t1 = _current_user_var.set(user)
    t2 = _current_db_var.set(mock_db)
    try:
        with patch("app.mcp.tools.prepare_account_for_db", return_value=mock_account) as mock_prepare:
            await create_account_impl(
                name="BCA", type="bank_account", description=None, limit=None, account_number="1234567890"
            )
            called_data = mock_prepare.call_args[0][0]
            assert called_data.get("account_number") == "1234567890"
    finally:
        _current_user_var.reset(t1)
        _current_db_var.reset(t2)


# ---------------------------------------------------------------------------
# MCP tool: update_account_impl
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_account_impl_updates_account_number():
    from app.mcp.context import _current_user_var, _current_db_var
    from app.mcp.tools import update_account_impl
    from app.models.cuan import TrxAccountType

    user = MagicMock()
    user.id = uuid4()
    user.username = "alice"

    mock_account = MagicMock()
    mock_account.id = uuid4()
    mock_account.name = "BCA"
    mock_account.type = TrxAccountType.BANK_ACCOUNT
    mock_account.description = None
    mock_account.limit = None
    mock_account.account_number = "old_number"

    mock_db = MagicMock()
    t1 = _current_user_var.set(user)
    t2 = _current_db_var.set(mock_db)
    try:
        with patch("app.mcp.tools.validate_account", return_value=mock_account):
            await update_account_impl(
                account_id=str(mock_account.id),
                name="BCA Updated",
                type="bank_account",
                description=None,
                limit=None,
                account_number="new_number",
            )
            assert mock_account.account_number == "new_number"
    finally:
        _current_user_var.reset(t1)
        _current_db_var.reset(t2)
