"""Tests for app/schemas/cuan.py Pydantic schemas."""
from datetime import datetime, UTC
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# TrxAccountCreate
# ---------------------------------------------------------------------------

def test_account_create_bank_account_valid():
    from app.schemas.cuan import TrxAccountCreate
    schema = TrxAccountCreate(name="BCA", type="bank_account", account_number="1234567890")
    assert schema.name == "BCA"
    assert schema.account_number == "1234567890"


def test_account_create_credit_card_valid():
    from app.schemas.cuan import TrxAccountCreate
    schema = TrxAccountCreate(name="Visa", type="credit_card", limit=Decimal("5000"), account_number="4111")
    assert schema.limit == Decimal("5000")


def test_account_create_other_valid_no_number():
    from app.schemas.cuan import TrxAccountCreate
    schema = TrxAccountCreate(name="Cash", type="other")
    assert schema.account_number is None
    assert schema.limit is None


def test_account_create_bank_missing_number_raises():
    from app.schemas.cuan import TrxAccountCreate
    with pytest.raises(ValidationError):
        TrxAccountCreate(name="BCA", type="bank_account")


def test_account_create_credit_card_missing_number_raises():
    from app.schemas.cuan import TrxAccountCreate
    with pytest.raises(ValidationError):
        TrxAccountCreate(name="Visa", type="credit_card", limit=5000)


def test_account_create_missing_name_raises():
    from app.schemas.cuan import TrxAccountCreate
    with pytest.raises(ValidationError):
        TrxAccountCreate(type="other")


def test_account_create_invalid_type_raises():
    from app.schemas.cuan import TrxAccountCreate
    with pytest.raises(ValidationError):
        TrxAccountCreate(name="X", type="savings_account", account_number="123")


# ---------------------------------------------------------------------------
# TrxCategoryCreate
# ---------------------------------------------------------------------------

def test_category_create_income_valid():
    from app.schemas.cuan import TrxCategoryCreate
    schema = TrxCategoryCreate(name="Salary", type="income")
    assert schema.type.value == "income"


def test_category_create_expense_valid():
    from app.schemas.cuan import TrxCategoryCreate
    schema = TrxCategoryCreate(name="Food", type="expense")
    assert schema.type.value == "expense"


def test_category_create_missing_name_raises():
    from app.schemas.cuan import TrxCategoryCreate
    with pytest.raises(ValidationError):
        TrxCategoryCreate(type="income")


def test_category_create_invalid_type_raises():
    from app.schemas.cuan import TrxCategoryCreate
    with pytest.raises(ValidationError):
        TrxCategoryCreate(name="X", type="transfer")


# ---------------------------------------------------------------------------
# TransactionCreate
# ---------------------------------------------------------------------------

def test_transaction_create_income_valid():
    from app.schemas.cuan import TransactionCreate
    schema = TransactionCreate(
        description="Salary",
        amount=Decimal("1000"),
        transaction_type="income",
        account_id=uuid4(),
        category_id=uuid4(),
        transaction_date=datetime.now(UTC),
    )
    assert schema.transaction_type.value == "income"
    assert schema.transfer_fee == Decimal("0")
    assert schema.destination_account_id is None


def test_transaction_create_transfer_with_destination():
    from app.schemas.cuan import TransactionCreate
    schema = TransactionCreate(
        description="Move funds",
        amount=Decimal("500"),
        transaction_type="transfer",
        account_id=uuid4(),
        category_id=None,
        transaction_date=datetime.now(UTC),
        destination_account_id=uuid4(),
        transfer_fee=Decimal("5"),
    )
    assert schema.destination_account_id is not None
    assert schema.transfer_fee == Decimal("5")


def test_transaction_create_missing_amount_raises():
    from app.schemas.cuan import TransactionCreate
    with pytest.raises(ValidationError):
        TransactionCreate(
            description="X",
            transaction_type="income",
            account_id=uuid4(),
            transaction_date=datetime.now(UTC),
        )


def test_transaction_create_invalid_type_raises():
    from app.schemas.cuan import TransactionCreate
    with pytest.raises(ValidationError):
        TransactionCreate(
            description="X",
            amount=Decimal("100"),
            transaction_type="refund",
            account_id=uuid4(),
            transaction_date=datetime.now(UTC),
        )


def test_transaction_create_zero_amount_is_allowed():
    from app.schemas.cuan import TransactionCreate
    schema = TransactionCreate(
        description="X",
        amount=Decimal("0"),
        transaction_type="income",
        account_id=uuid4(),
        transaction_date=datetime.now(UTC),
    )
    assert schema.amount == Decimal("0")


# ---------------------------------------------------------------------------
# TrxAccountResponseData — from_attributes deserialization
# ---------------------------------------------------------------------------

def test_account_response_data_from_dict():
    from app.schemas.cuan import TrxAccountResponseData
    data = TrxAccountResponseData(
        id=uuid4(),
        name="BCA",
        type="bank_account",
        account_number="9876543210",
        user_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert data.account_number == "9876543210"
    assert data.limit is None
    assert data.description is None
