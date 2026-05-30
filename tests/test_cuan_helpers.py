"""Tests for app/utils/cuan_helpers.py."""
from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import MagicMock
from app.utils.uuid import uuid7

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_account(type_val, limit=None, account_number=None):
    from app.models.cuan import TrxAccount, TrxAccountType
    acc = MagicMock(spec=TrxAccount)
    acc.id = uuid7()
    acc.type = type_val
    acc.limit = limit
    acc.account_number = account_number
    acc.name = "Test"
    acc.description = None
    acc.user_id = uuid7()
    acc.created_at = datetime.now(UTC)
    acc.updated_at = datetime.now(UTC)
    return acc


def _make_category(type_val):
    from app.models.cuan import TrxCategory, TrxCategoryType
    cat = MagicMock(spec=TrxCategory)
    cat.id = uuid7()
    cat.type = type_val
    cat.name = "Cat"
    return cat


# ---------------------------------------------------------------------------
# validate_account
# ---------------------------------------------------------------------------

def test_validate_account_found():
    from app.utils.cuan_helpers import validate_account
    from app.models.cuan import TrxAccountType

    acc = _make_account(TrxAccountType.BANK_ACCOUNT)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = acc

    result = validate_account(mock_db, acc.id, acc.user_id)
    assert result is acc


def test_validate_account_not_found_raises_404():
    from app.utils.cuan_helpers import validate_account

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        validate_account(mock_db, uuid7(), uuid7())
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# validate_category
# ---------------------------------------------------------------------------

def test_validate_category_none_id_returns_none():
    from app.utils.cuan_helpers import validate_category
    mock_db = MagicMock()
    result = validate_category(mock_db, None, uuid7())
    assert result is None


def test_validate_category_found():
    from app.utils.cuan_helpers import validate_category
    from app.models.cuan import TrxCategoryType

    cat = _make_category(TrxCategoryType.INCOME)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = cat

    result = validate_category(mock_db, cat.id, uuid7())
    assert result is cat


def test_validate_category_not_found_raises_404():
    from app.utils.cuan_helpers import validate_category

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        validate_category(mock_db, uuid7(), uuid7())
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# validate_transaction_category_match
# ---------------------------------------------------------------------------

def test_income_tx_with_income_category_ok():
    from app.utils.cuan_helpers import validate_transaction_category_match
    from app.models.cuan import TrxCategoryType, TransactionType

    cat = _make_category(TrxCategoryType.INCOME)
    validate_transaction_category_match(TransactionType.INCOME, cat)  # no raise


def test_income_tx_with_expense_category_raises_400():
    from app.utils.cuan_helpers import validate_transaction_category_match
    from app.models.cuan import TrxCategoryType, TransactionType

    cat = _make_category(TrxCategoryType.EXPENSE)
    with pytest.raises(HTTPException) as exc:
        validate_transaction_category_match(TransactionType.INCOME, cat)
    assert exc.value.status_code == 400


def test_expense_tx_with_expense_category_ok():
    from app.utils.cuan_helpers import validate_transaction_category_match
    from app.models.cuan import TrxCategoryType, TransactionType

    cat = _make_category(TrxCategoryType.EXPENSE)
    validate_transaction_category_match(TransactionType.EXPENSE, cat)  # no raise


def test_expense_tx_with_income_category_raises_400():
    from app.utils.cuan_helpers import validate_transaction_category_match
    from app.models.cuan import TrxCategoryType, TransactionType

    cat = _make_category(TrxCategoryType.INCOME)
    with pytest.raises(HTTPException) as exc:
        validate_transaction_category_match(TransactionType.EXPENSE, cat)
    assert exc.value.status_code == 400


def test_transfer_tx_with_any_category_ok():
    from app.utils.cuan_helpers import validate_transaction_category_match
    from app.models.cuan import TrxCategoryType, TransactionType

    cat = _make_category(TrxCategoryType.INCOME)
    validate_transaction_category_match(TransactionType.TRANSFER, cat)  # no raise


def test_any_tx_with_none_category_ok():
    from app.utils.cuan_helpers import validate_transaction_category_match
    from app.models.cuan import TransactionType

    validate_transaction_category_match(TransactionType.INCOME, None)  # no raise


# ---------------------------------------------------------------------------
# validate_transfer
# ---------------------------------------------------------------------------

def test_validate_transfer_non_transfer_with_fee_raises_400():
    from app.utils.cuan_helpers import validate_transfer
    from app.models.cuan import TransactionType

    with pytest.raises(HTTPException) as exc:
        validate_transfer(TransactionType.INCOME, None, uuid7(), Decimal("10"), MagicMock(), uuid7())
    assert exc.value.status_code == 400


def test_validate_transfer_non_transfer_no_fee_returns_none():
    from app.utils.cuan_helpers import validate_transfer
    from app.models.cuan import TransactionType

    result = validate_transfer(TransactionType.INCOME, None, uuid7(), Decimal("0"), MagicMock(), uuid7())
    assert result is None


def test_validate_transfer_missing_destination_raises_400():
    from app.utils.cuan_helpers import validate_transfer
    from app.models.cuan import TransactionType

    with pytest.raises(HTTPException) as exc:
        validate_transfer(TransactionType.TRANSFER, None, uuid7(), Decimal("0"), MagicMock(), uuid7())
    assert exc.value.status_code == 400


def test_validate_transfer_negative_fee_raises_400():
    from app.utils.cuan_helpers import validate_transfer
    from app.models.cuan import TransactionType

    src_id = uuid7()
    dst_id = uuid7()
    with pytest.raises(HTTPException) as exc:
        validate_transfer(TransactionType.TRANSFER, dst_id, src_id, Decimal("-1"), MagicMock(), uuid7())
    assert exc.value.status_code == 400


def test_validate_transfer_same_account_raises_400():
    from app.utils.cuan_helpers import validate_transfer
    from app.models.cuan import TransactionType

    same_id = uuid7()
    with pytest.raises(HTTPException) as exc:
        validate_transfer(TransactionType.TRANSFER, same_id, same_id, Decimal("0"), MagicMock(), uuid7())
    assert exc.value.status_code == 400


def test_validate_transfer_dest_not_found_raises_404():
    from app.utils.cuan_helpers import validate_transfer
    from app.models.cuan import TransactionType

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        validate_transfer(TransactionType.TRANSFER, uuid7(), uuid7(), Decimal("0"), mock_db, uuid7())
    assert exc.value.status_code == 404


def test_validate_transfer_valid_returns_dest_account():
    from app.utils.cuan_helpers import validate_transfer
    from app.models.cuan import TransactionType, TrxAccountType

    dest = _make_account(TrxAccountType.BANK_ACCOUNT)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = dest

    result = validate_transfer(TransactionType.TRANSFER, dest.id, uuid7(), Decimal("5"), mock_db, uuid7())
    assert result is dest


# ---------------------------------------------------------------------------
# prepare_account_for_db
# ---------------------------------------------------------------------------

def test_prepare_account_bank_no_limit_ok():
    from app.utils.cuan_helpers import prepare_account_for_db
    from app.models.cuan import TrxAccountType, TrxAccount

    acc = prepare_account_for_db(
        {"name": "BCA", "type": TrxAccountType.BANK_ACCOUNT, "description": None, "limit": None, "account_number": "123"},
        uuid7()
    )
    assert isinstance(acc, TrxAccount)
    assert acc.name == "BCA"


def test_prepare_account_credit_card_no_limit_raises_400():
    from app.utils.cuan_helpers import prepare_account_for_db
    from app.models.cuan import TrxAccountType

    with pytest.raises(HTTPException) as exc:
        prepare_account_for_db(
            {"name": "Visa", "type": TrxAccountType.CREDIT_CARD, "description": None, "limit": None, "account_number": "4111"},
            uuid7()
        )
    assert exc.value.status_code == 400


def test_prepare_account_bank_with_limit_raises_400():
    from app.utils.cuan_helpers import prepare_account_for_db
    from app.models.cuan import TrxAccountType

    with pytest.raises(HTTPException) as exc:
        prepare_account_for_db(
            {"name": "BCA", "type": TrxAccountType.BANK_ACCOUNT, "description": None, "limit": Decimal("5000"), "account_number": "123"},
            uuid7()
        )
    assert exc.value.status_code == 400


def test_prepare_account_other_no_limit_ok():
    from app.utils.cuan_helpers import prepare_account_for_db
    from app.models.cuan import TrxAccountType, TrxAccount

    acc = prepare_account_for_db(
        {"name": "Cash", "type": TrxAccountType.OTHER, "description": None, "limit": None, "account_number": None},
        uuid7()
    )
    assert isinstance(acc, TrxAccount)


# ---------------------------------------------------------------------------
# prepare_category_for_db
# ---------------------------------------------------------------------------

def test_prepare_category_for_db():
    from app.utils.cuan_helpers import prepare_category_for_db
    from app.models.cuan import TrxCategoryType, TrxCategory

    cat = prepare_category_for_db({"name": "Food", "type": TrxCategoryType.EXPENSE}, uuid7())
    assert isinstance(cat, TrxCategory)
    assert cat.name == "Food"


# ---------------------------------------------------------------------------
# prepare_transaction_for_db
# ---------------------------------------------------------------------------

def test_prepare_transaction_for_db():
    from app.utils.cuan_helpers import prepare_transaction_for_db
    from app.models.cuan import Transaction, TransactionType

    tx = prepare_transaction_for_db(
        {
            "description": "Salary",
            "amount": Decimal("1000"),
            "transaction_type": TransactionType.INCOME,
            "account_id": uuid7(),
            "category_id": None,
            "transaction_date": datetime.now(UTC),
            "destination_account_id": None,
            "transfer_fee": Decimal("0"),
        },
        uuid7()
    )
    assert isinstance(tx, Transaction)
    assert tx.amount == Decimal("1000")


# ---------------------------------------------------------------------------
# prepare_deleted_* info helpers
# ---------------------------------------------------------------------------

def test_prepare_deleted_account_info():
    from app.utils.cuan_helpers import prepare_deleted_account_info
    from app.models.cuan import TrxAccountType

    acc = _make_account(TrxAccountType.BANK_ACCOUNT)
    info = prepare_deleted_account_info(acc)
    assert info["id"] == acc.id
    assert info["name"] == acc.name
    assert info["type"] == TrxAccountType.BANK_ACCOUNT.value


def test_prepare_deleted_category_info():
    from app.utils.cuan_helpers import prepare_deleted_category_info
    from app.models.cuan import TrxCategoryType

    cat = _make_category(TrxCategoryType.EXPENSE)
    info = prepare_deleted_category_info(cat)
    assert info["id"] == cat.id
    assert info["name"] == cat.name
    assert info["type"] == TrxCategoryType.EXPENSE.value


def test_prepare_deleted_transaction_info():
    from app.utils.cuan_helpers import prepare_deleted_transaction_info
    from app.models.cuan import Transaction, TransactionType

    tx = MagicMock(spec=Transaction)
    tx.id = uuid7()
    tx.description = "Salary"
    tx.amount = Decimal("500")
    tx.transaction_type = TransactionType.INCOME

    info = prepare_deleted_transaction_info(tx)
    assert info["id"] == tx.id
    assert info["description"] == "Salary"
    assert info["amount"] == Decimal("500")
    assert info["transaction_type"] == TransactionType.INCOME.value


# ---------------------------------------------------------------------------
# get_filtered_categories
# ---------------------------------------------------------------------------

def test_get_filtered_categories_no_filter():
    from app.utils.cuan_helpers import get_filtered_categories

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    result = get_filtered_categories(mock_db, uuid7())
    assert result == []


def test_get_filtered_categories_income():
    from app.utils.cuan_helpers import get_filtered_categories

    cat = _make_category(__import__("app.models.cuan", fromlist=["TrxCategoryType"]).TrxCategoryType.INCOME)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [cat]

    result = get_filtered_categories(mock_db, uuid7(), "income")
    assert result == [cat]


def test_get_filtered_categories_invalid_type_raises_400():
    from app.utils.cuan_helpers import get_filtered_categories

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    with pytest.raises(HTTPException) as exc:
        get_filtered_categories(mock_db, uuid7(), "invalid_type")
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# get_year_end
# ---------------------------------------------------------------------------

def test_get_year_end_2024():
    from app.utils.cuan_helpers import get_year_end
    result = get_year_end(2024)
    assert result == datetime(2025, 1, 1, tzinfo=UTC)


def test_get_year_end_2000():
    from app.utils.cuan_helpers import get_year_end
    result = get_year_end(2000)
    assert result == datetime(2001, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# calculate_date_range
# ---------------------------------------------------------------------------

def test_calculate_date_range_day_produces_today_bounds():
    from app.utils.cuan_helpers import calculate_date_range
    start, end = calculate_date_range("day", "UTC")
    assert start.hour == 0 and start.minute == 0 and start.second == 0
    assert end.hour == 23 and end.minute == 59


def test_calculate_date_range_week():
    from app.utils.cuan_helpers import calculate_date_range
    start, end = calculate_date_range("week", "UTC")
    assert start.weekday() == 0  # Monday


def test_calculate_date_range_month_starts_day_1():
    from app.utils.cuan_helpers import calculate_date_range
    start, end = calculate_date_range("month", "UTC")
    assert start.day == 1


def test_calculate_date_range_year():
    from app.utils.cuan_helpers import calculate_date_range
    start, end = calculate_date_range("year", "UTC")
    assert start.month == 1 and start.day == 1


def test_calculate_date_range_all():
    from app.utils.cuan_helpers import calculate_date_range
    start, end = calculate_date_range("all", "UTC")
    assert start.year == 2000


def test_calculate_date_range_invalid_period_raises():
    from app.utils.cuan_helpers import calculate_date_range
    with pytest.raises(ValueError, match="Invalid period"):
        calculate_date_range("fortnight", "UTC")


def test_calculate_date_range_invalid_timezone_raises():
    from app.utils.cuan_helpers import calculate_date_range
    with pytest.raises(ValueError, match="Invalid timezone"):
        calculate_date_range("day", "Fake/Zone")


def test_calculate_date_range_valid_timezone():
    from app.utils.cuan_helpers import calculate_date_range
    start, end = calculate_date_range("day", "Asia/Jakarta")
    assert start.tzinfo is not None
