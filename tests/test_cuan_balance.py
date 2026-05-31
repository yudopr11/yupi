"""Tests for cuan_helpers balance calculation."""
import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException


def test_calculate_account_balance_not_found():
    """Should raise 404 when account doesn't exist."""
    from app.utils.cuan_helpers import calculate_account_balance

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        calculate_account_balance(mock_db, uuid.uuid4())
    assert exc.value.status_code == 404


def test_calculate_account_balance_basic():
    """Should return balance dict with all required keys."""
    from app.utils.cuan_helpers import calculate_account_balance

    mock_account = MagicMock()
    mock_account.account_type = "cash"
    mock_account.limit = None
    mock_account.initial_balance = 0

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_account
    # Mock the aggregation query
    mock_result = MagicMock()
    mock_result.total_income = 1000
    mock_result.total_expenses = 300
    mock_result.total_transfers_in = 200
    mock_result.total_transfers_out = 100
    mock_result.total_transfer_fees = 5
    mock_db.query.return_value.filter.return_value.one.return_value = mock_result

    result = calculate_account_balance(mock_db, uuid.uuid4())

    assert "balance" in result
    assert "total_income" in result
    assert "total_expenses" in result
    assert "total_transfers_in" in result
    assert "total_transfers_out" in result
    assert "total_transfer_fees" in result


def test_calculate_account_balance_with_user_filter():
    """Should filter by user_id when provided."""
    from app.utils.cuan_helpers import calculate_account_balance

    mock_account = MagicMock()
    mock_account.account_type = "cash"
    mock_account.limit = None
    mock_account.initial_balance = 0

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_account
    mock_result = MagicMock()
    mock_result.total_income = 500
    mock_result.total_expenses = 100
    mock_result.total_transfers_in = 0
    mock_result.total_transfers_out = 0
    mock_result.total_transfer_fees = 0
    mock_db.query.return_value.filter.return_value.one.return_value = mock_result

    user_id = uuid.uuid4()
    result = calculate_account_balance(mock_db, uuid.uuid4(), user_id=user_id)

    assert result["balance"] == 400
