from fastapi import HTTPException, status
from sqlalchemy.orm import Session, Query, aliased
from sqlalchemy import func, case, or_, desc, and_
from typing import Dict, Any, Tuple, Union, Optional, List
import uuid
from datetime import datetime, timedelta, UTC
import calendar
from decimal import Decimal

from app.models.cuan import TrxAccount, TrxAccountType, TrxCategory, TrxCategoryType, Transaction, TransactionType
from app.models.auth import User

# --- Validation Helpers ---

def validate_account(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> TrxAccount:
    """
    Validates that an account exists and belongs to the user.
    """
    account = db.query(TrxAccount).filter(
        TrxAccount.id == id,
        TrxAccount.user_id == user_id
    ).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TrxAccount with id {id} not found"
        )
    return account

def validate_category(db: Session, id: Optional[uuid.UUID], user_id: uuid.UUID) -> Optional[TrxCategory]:
    """
    Validates that a category exists and belongs to the user.
    Returns None if id is None.
    """
    if id is None:
        return None
    category = db.query(TrxCategory).filter(
        TrxCategory.id == id,
        TrxCategory.user_id == user_id
    ).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TrxCategory with id {id} not found"
        )
    return category

def validate_transaction_category_match(transaction_type: TransactionType, category: Optional[TrxCategory]) -> None:
    """
    Validates that transaction type matches category type.
    """
    if category is None:
        return
    if transaction_type == TransactionType.INCOME and category.type != TrxCategoryType.INCOME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Income transactions must use an income category"
        )
    if transaction_type == TransactionType.EXPENSE and category.type != TrxCategoryType.EXPENSE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expense transactions must use an expense category"
        )

def validate_transfer(
    transaction_type: TransactionType,
    destination_account_id: Optional[uuid.UUID],
    source_account_id: uuid.UUID,
    transfer_fee: Decimal,
    db: Session,
    user_id: uuid.UUID
) -> Optional[TrxAccount]:
    """
    Validates transfer transaction details.
    """
    if transaction_type != TransactionType.TRANSFER:
        if transfer_fee > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transfer fee can only be applied to transfer transactions"
            )
        return None

    if not destination_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Destination account is required for transfers"
        )
    if transfer_fee < Decimal('0'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transfer fee cannot be negative"
        )
    if source_account_id == destination_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination accounts cannot be the same for transfers"
        )

    dest_account = db.query(TrxAccount).filter(
        TrxAccount.id == destination_account_id,
        TrxAccount.user_id == user_id
    ).first()
    if not dest_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination account with id {destination_account_id} not found"
        )
    return dest_account

# --- Data Preparation Helpers ---

def prepare_account_for_db(account_data: Dict[str, Any], user_id: uuid.UUID) -> TrxAccount:
    """
    Prepares an account object for database insertion.
    """
    account_type = account_data.get("type")
    limit = account_data.get("limit")

    if account_type == TrxAccountType.CREDIT_CARD:
        if limit is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credit card accounts must have a limit."
            )
    elif limit is not None:
        # Convert enum value to a user-friendly string (e.g., "bank_account" -> "Bank Account")
        pretty_account_type = account_type.replace("_", " ").title()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account type '{pretty_account_type}' cannot have a limit. Only credit cards are allowed a limit."
        )

    return TrxAccount(id=uuid.uuid4(), user_id=user_id, **account_data)

def prepare_category_for_db(category_data: Dict[str, Any], user_id: uuid.UUID) -> TrxCategory:
    """
    Prepares a category object for database insertion.
    """
    return TrxCategory(id=uuid.uuid4(), user_id=user_id, **category_data)

def prepare_transaction_for_db(transaction_data: Dict[str, Any], user_id: uuid.UUID) -> Transaction:
    """
    Prepares a transaction object for database insertion.
    """
    return Transaction(id=uuid.uuid4(), user_id=user_id, **transaction_data)

def prepare_deleted_account_info(account: TrxAccount) -> Dict[str, Any]:
    """
    Prepares account information for deletion response.
    """
    return {"id": account.id, "name": account.name, "type": account.type.value}

def prepare_deleted_category_info(category: TrxCategory) -> Dict[str, Any]:
    """
    Prepares category information for deletion response.
    """
    return {"id": category.id, "name": category.name, "type": category.type.value}

def prepare_deleted_transaction_info(transaction: Transaction) -> Dict[str, Any]:
    """
    Prepares transaction information for deletion response.
    """
    return {
        "id": transaction.id,
        "description": transaction.description,
        "amount": transaction.amount,
        "transaction_type": transaction.transaction_type.value
    }

# --- Query & Calculation Helpers ---

def get_filtered_categories(
    db: Session,
    user_id: uuid.UUID,
    category_type: Optional[str] = None
) -> list[TrxCategory]:
    """
    Get user categories with optional type filtering.
    """
    query = db.query(TrxCategory).filter(TrxCategory.user_id == user_id)
    if category_type:
        try:
            filter_type = TrxCategoryType(category_type.lower())
            query = query.filter(TrxCategory.type == filter_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category type: {category_type}. Must be one of: {[t.value for t in TrxCategoryType]}"
            )
    return query.order_by(TrxCategory.name).all()

def get_filtered_accounts(
    db: Session,
    user_id: uuid.UUID,
    account_type: Optional[str] = None
) -> list[TrxAccount]:
    """
    Get user accounts with optional type filtering, sorted for display.
    """
    query = db.query(TrxAccount).filter(TrxAccount.user_id == user_id)
    if account_type:
        try:
            filter_type = TrxAccountType(account_type.lower())
            query = query.filter(TrxAccount.type == filter_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid account type: {account_type}. Must be one of: {[t.value for t in TrxAccountType]}"
            )
    type_order = case(
        (TrxAccount.type == TrxAccountType.BANK_ACCOUNT, 1),
        (TrxAccount.type == TrxAccountType.OTHER, 2),
        (TrxAccount.type == TrxAccountType.CREDIT_CARD, 3),
        else_=4
    )
    return query.order_by(type_order, TrxAccount.name).all()

def calculate_account_balance(db: Session, account_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> dict:
    """
    Calculates the detailed balance of a financial account using a single, optimized query.
    """
    account_query = db.query(TrxAccount)
    if user_id:
        account_query = account_query.filter(TrxAccount.id == account_id, TrxAccount.user_id == user_id)
    else:
        account_query = account_query.filter(TrxAccount.id == account_id)
    
    account = account_query.first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"TrxAccount with id {account_id} not found")

    # Single query to aggregate all transaction types
    totals = db.query(
        func.sum(case((Transaction.transaction_type == TransactionType.INCOME, Transaction.amount), else_=0)).label("total_income"),
        func.sum(case((Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount), else_=0)).label("total_expenses"),
        func.sum(case((and_(Transaction.transaction_type == TransactionType.TRANSFER, Transaction.account_id == account_id), Transaction.amount), else_=0)).label("total_transfers_out"),
        func.sum(case((and_(Transaction.transaction_type == TransactionType.TRANSFER, Transaction.account_id == account_id), Transaction.transfer_fee), else_=0)).label("total_transfer_fees"),
        func.sum(case((Transaction.destination_account_id == account_id, Transaction.amount), else_=0)).label("total_transfers_in")
    ).filter(
        or_(Transaction.account_id == account_id, Transaction.destination_account_id == account_id),
        Transaction.user_id == (user_id if user_id else account.user_id)
    ).one()

    total_income = totals.total_income or Decimal('0.0')
    total_expenses = totals.total_expenses or Decimal('0.0')
    total_transfers_out = totals.total_transfers_out or Decimal('0.0')
    total_transfer_fees = totals.total_transfer_fees or Decimal('0.0')
    total_transfers_in = totals.total_transfers_in or Decimal('0.0')

    balance = total_income + total_transfers_in - total_expenses - total_transfers_out - total_transfer_fees
    
    payable_balance = None
    if account.type == TrxAccountType.CREDIT_CARD and account.limit is not None:
        payable_balance = account.limit - balance

    return {
        "balance": balance,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "total_transfers_in": total_transfers_in,
        "total_transfers_out": total_transfers_out,
        "total_transfer_fees": total_transfer_fees,
        "payable_balance": payable_balance
    }

def get_accounts_with_balance(db: Session, user_id: uuid.UUID, account_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Gets all accounts for a user with their balances, optimized to prevent N+1 queries.
    """
    # Base query for user's accounts
    query = db.query(
        TrxAccount,
        func.sum(case((Transaction.transaction_type == TransactionType.INCOME, Transaction.amount), else_=0)).label("total_income"),
        func.sum(case((Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount), else_=0)).label("total_expenses"),
        func.sum(case((and_(Transaction.transaction_type == TransactionType.TRANSFER, Transaction.account_id == TrxAccount.id), Transaction.amount), else_=0)).label("total_transfers_out"),
        func.sum(case((and_(Transaction.transaction_type == TransactionType.TRANSFER, Transaction.account_id == TrxAccount.id), Transaction.transfer_fee), else_=0)).label("total_transfer_fees"),
        func.sum(case((Transaction.destination_account_id == TrxAccount.id, Transaction.amount), else_=0)).label("total_transfers_in")
    ).outerjoin(Transaction, or_(
        Transaction.account_id == TrxAccount.id,
        Transaction.destination_account_id == TrxAccount.id
    )).filter(TrxAccount.user_id == user_id).group_by(TrxAccount.id)

    # Optional filtering by account type
    if account_type:
        try:
            filter_type = TrxAccountType(account_type.lower())
            query = query.filter(TrxAccount.type == filter_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid account type: {account_type}. Must be one of: {[t.value for t in TrxAccountType]}"
            )

    # Sorting for consistent display
    type_order = case(
        (TrxAccount.type == TrxAccountType.BANK_ACCOUNT, 1),
        (TrxAccount.type == TrxAccountType.OTHER, 2),
        (TrxAccount.type == TrxAccountType.CREDIT_CARD, 3),
        else_=4
    )
    results = query.order_by(type_order, TrxAccount.name).all()

    # Process results
    accounts_with_balances = []
    for account, income, expenses, transfers_out, transfer_fees, transfers_in in results:
        total_income = income or Decimal('0.0')
        total_expenses = expenses or Decimal('0.0')
        total_transfers_out = transfers_out or Decimal('0.0')
        total_transfer_fees = transfer_fees or Decimal('0.0')
        total_transfers_in = transfers_in or Decimal('0.0')

        balance = total_income + total_transfers_in - total_expenses - total_transfers_out - total_transfer_fees
        
        account_data = {
            "id": account.id,
            "name": account.name,
            "type": account.type,
            "description": account.description,
            "limit": account.limit,
            "user_id": account.user_id,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
            "balance": balance,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "total_transfers_in": total_transfers_in,
            "total_transfers_out": total_transfers_out,
            "total_transfer_fees": total_transfer_fees,
            "payable_balance": None
        }

        if account.type == TrxAccountType.CREDIT_CARD and account.limit is not None:
            account_data["payable_balance"] = account.limit - balance
        
        accounts_with_balances.append(account_data)
        
    return accounts_with_balances

def get_filtered_transactions(
    db: Session,
    user_id: uuid.UUID,
    account_name: Optional[str] = None,
    category_name: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    date_filter_type: Optional[str] = None,
    order_by: str = 'created_at',
    sort_order: str = 'desc',
    return_query: bool = False
) -> Union[List[Transaction], Query]:
    """
    Retrieve a list of transactions with advanced filtering and sorting.
    """
    query = db.query(Transaction).filter(Transaction.user_id == user_id)

    if account_name:
        account_ids = [acc.id for acc in db.query(TrxAccount.id).filter(
            TrxAccount.user_id == user_id,
            TrxAccount.name.ilike(f"%{account_name}%")
        ).all()]
        if not account_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Account with name '{account_name}' not found")
        query = query.filter(or_(Transaction.account_id.in_(account_ids), Transaction.destination_account_id.in_(account_ids)))

    if category_name:
        category_ids = [cat.id for cat in db.query(TrxCategory.id).filter(
            TrxCategory.user_id == user_id,
            TrxCategory.name.ilike(f"%{category_name}%")
        ).all()]
        if not category_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Category with name '{category_name}' not found")
        query = query.filter(Transaction.category_id.in_(category_ids))

    if transaction_type:
        try:
            query = query.filter(Transaction.transaction_type == TransactionType(transaction_type.lower()))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid transaction type: {transaction_type}")

    if date_filter_type:
        try:
            start_date, end_date = calculate_date_range(date_filter_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)

    valid_fields = ['created_at', 'transaction_date', 'amount']
    if order_by not in valid_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid order_by field. Must be one of: {', '.join(valid_fields)}")
    
    sort_attr = getattr(Transaction, order_by)
    query = query.order_by(desc(sort_attr) if sort_order.lower() == 'desc' else sort_attr)

    return query if return_query else query.all()

def calculate_date_range(period: str) -> Tuple[datetime, datetime]:
    """
    Calculate start and end dates based on a predefined period string.
    """
    now = datetime.now(UTC)
    period = period.lower()
    
    if period == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1) - timedelta(microseconds=1)
    elif period == "week":
        start_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7) - timedelta(microseconds=1)
    elif period == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        _, last_day = calendar.monthrange(now.year, now.month)
        end_date = start_date.replace(day=last_day) + timedelta(days=1) - timedelta(microseconds=1)
    elif period == "year":
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date.replace(year=now.year + 1) - timedelta(microseconds=1)
    elif period == "all":
        start_date = datetime(2000, 1, 1, tzinfo=UTC)
        end_date = now
    else:
        raise ValueError(f"Invalid period: '{period}'. Must be one of: day, week, month, year, all")
        
    return start_date, end_date