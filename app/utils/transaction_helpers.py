from fastapi import HTTPException, status
from sqlalchemy.orm import Session, Query
from typing import Dict, Any, Tuple, Union, Optional
import uuid
from datetime import datetime, timedelta
import calendar
from decimal import Decimal

from app.models.account import TrxAccount, TrxAccountType
from app.models.category import TrxCategory, TrxCategoryType
from app.models.transaction import Transaction, TransactionType
from app.models.user import User

def validate_account(db: Session, account_id: int, user_id: int) -> TrxAccount:
    """
    Validates that an account exists and belongs to the user
    
    Args:
        db: Database session
        account_id: ID of the account to validate
        user_id: ID of the user who should own the account
        
    Returns:
        The account object if valid
        
    Raises:
        HTTPException: If account doesn't exist or doesn't belong to user
    """
    account = db.query(TrxAccount).filter(
        TrxAccount.account_id == account_id,
        TrxAccount.user_id == user_id
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TrxAccount with id {account_id} not found"
        )
    
    return account

def validate_category(db: Session, category_id: Optional[int], user_id: int) -> Optional[TrxCategory]:
    """
    Validates that a category exists and belongs to the user
    
    Args:
        db: Database session
        category_id: ID of the category to validate (can be None)
        user_id: ID of the user who should own the category
        
    Returns:
        The category object if valid, or None if category_id is None
        
    Raises:
        HTTPException: If category doesn't exist or doesn't belong to user
    """
    if category_id is None:
        return None
        
    category = db.query(TrxCategory).filter(
        TrxCategory.category_id == category_id,
        TrxCategory.user_id == user_id
    ).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TrxCategory with id {category_id} not found"
        )
    
    return category

def validate_transaction_category_match(transaction_type: TransactionType, category: Optional[TrxCategory]) -> None:
    """
    Validates that the transaction type matches the category type
    
    Args:
        transaction_type: Type of the transaction
        category: TrxCategory object to validate against (can be None)
        
    Raises:
        HTTPException: If transaction type doesn't match category type
    """
    if category is None:
        return
        
    if transaction_type in [TransactionType.INCOME, TransactionType.EXPENSE]:
        if transaction_type == TransactionType.INCOME and category.type != TrxCategoryType.INCOME:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Income transactions must use an income category"
            )
        elif transaction_type == TransactionType.EXPENSE and category.type != TrxCategoryType.EXPENSE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expense transactions must use an expense category"
            )

def validate_transfer(
    transaction_type: TransactionType,
    destination_account_id: Optional[int], 
    source_account_id: int,
    transfer_fee: float,
    db: Session, 
    user_id: int
) -> Optional[TrxAccount]:
    """
    Validates transfer transaction details
    
    Args:
        transaction_type: Type of the transaction
        destination_account_id: ID of destination account
        source_account_id: ID of source account
        transfer_fee: Fee for the transfer transaction
        db: Database session
        user_id: ID of the user
        
    Returns:
        The destination account object if valid, or None if not a transfer
        
    Raises:
        HTTPException: If transfer validation fails
    """
    # For non-transfer transactions, ensure transfer fee is zero
    if transaction_type != TransactionType.TRANSFER:
        if transfer_fee > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transfer fee can only be applied to transfer transactions"
            )
        return None
        
    # For transfer transactions, validate required fields
    if not destination_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Destination account is required for transfers"
        )
    
    # Validate transfer fee is not negative
    if transfer_fee < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transfer fee cannot be negative"
        )
    
    # Prevent using the same account as both source and destination
    if source_account_id == destination_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination accounts cannot be the same for transfers"
        )
    
    dest_account = db.query(TrxAccount).filter(
        TrxAccount.account_id == destination_account_id,
        TrxAccount.user_id == user_id
    ).first()
    
    if not dest_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination account with id {destination_account_id} not found"
        )
    
    return dest_account

def prepare_account_for_db(account_data: Dict[str, Any], user_id: int) -> TrxAccount:
    """
    Prepares an account object for database insertion
    
    Args:
        account_data: Dictionary containing account data
        user_id: ID of the user who owns the account
        
    Returns:
        TrxAccount object ready for database insertion
    """
    if account_data.get("type") == TrxAccountType.CREDIT_CARD and account_data.get("limit") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credit card accounts must have a limit"
        )
    
    new_account = TrxAccount(**account_data)
    new_account.uuid = str(uuid.uuid4())
    new_account.user_id = user_id
    
    return new_account

def prepare_category_for_db(category_data: Dict[str, Any], user_id: int) -> TrxCategory:
    """
    Prepares a category object for database insertion
    
    Args:
        category_data: Dictionary containing category data
        user_id: ID of the user who owns the category
        
    Returns:
        TrxCategory object ready for database insertion
    """
    new_category = TrxCategory(**category_data)
    new_category.uuid = str(uuid.uuid4())
    new_category.user_id = user_id
    
    return new_category

def prepare_transaction_for_db(transaction_data: Dict[str, Any], user_id: int) -> Transaction:
    """
    Prepares a transaction object for database insertion
    
    Args:
        transaction_data: Dictionary containing transaction data
        user_id: ID of the user who owns the transaction
        
    Returns:
        Transaction object ready for database insertion
    """
    new_transaction = Transaction(**transaction_data)
    new_transaction.uuid = str(uuid.uuid4())
    new_transaction.user_id = user_id
    
    return new_transaction

def prepare_deleted_account_info(account: TrxAccount) -> Dict[str, Any]:
    """
    Prepares account information for deletion response
    
    Args:
        account: TrxAccount object being deleted
        
    Returns:
        Dictionary with formatted account info for deletion response
    """
    return {
        "id": account.account_id,
        "uuid": account.uuid,
        "name": account.name,
        "type": account.type.value
    }

def prepare_deleted_category_info(category: TrxCategory) -> Dict[str, Any]:
    """
    Prepares category information for deletion response
    
    Args:
        category: TrxCategory object being deleted
        
    Returns:
        Dictionary with formatted category info for deletion response
    """
    return {
        "id": category.category_id,
        "uuid": category.uuid,
        "name": category.name,
        "type": category.type.value
    }

def prepare_deleted_transaction_info(transaction: Transaction) -> Dict[str, Any]:
    """
    Prepares transaction information for deletion response
    
    Args:
        transaction: Transaction object being deleted
        
    Returns:
        Dictionary with formatted transaction info for deletion response
    """
    return {
        "id": transaction.transaction_id,
        "uuid": transaction.uuid,
        "description": transaction.description,
        "amount": transaction.amount,
        "transaction_type": transaction.transaction_type.value
    }

def get_filtered_categories(
    db: Session,
    user_id: int, 
    category_type: Optional[str] = None
) -> list[TrxCategory]:
    """
    Get user categories with optional type filtering
    
    Args:
        db: Database session
        user_id: ID of the user whose categories to retrieve
        category_type: Optional category type to filter by
        
    Returns:
        List of categories
        
    Raises:
        HTTPException: If category_type is invalid
    """
    # Start with base query for user's categories
    query = db.query(TrxCategory).filter(TrxCategory.user_id == user_id)
    
    # Apply category type filter if provided
    if category_type:
        # Convert to lowercase to match enum values
        category_type = category_type.lower()
        
        # Validate that it's a valid category type
        try:
            # Try to convert the string to enum
            filter_type = TrxCategoryType(category_type)
            query = query.filter(TrxCategory.type == filter_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category type: {category_type}. Must be one of: {[t.value for t in TrxCategoryType]}"
            )
    
    # Return results ordered by name
    return query.order_by(TrxCategory.name).all()
    
def get_filtered_accounts(
    db: Session,
    user_id: int, 
    account_type: Optional[str] = None
) -> list[TrxAccount]:
    """
    Get user accounts with optional type filtering
    
    Args:
        db: Database session
        user_id: ID of the user whose accounts to retrieve
        account_type: Optional account type to filter by
        
    Returns:
        List of accounts
        
    Raises:
        HTTPException: If account_type is invalid
    """
    # Start with base query for user's accounts
    query = db.query(TrxAccount).filter(TrxAccount.user_id == user_id)
    
    # Apply account type filter if provided
    if account_type:
        # Convert to lowercase to match enum values
        account_type = account_type.lower()
        
        # Validate that it's a valid account type
        try:
            # Try to convert the string to enum
            filter_type = TrxAccountType(account_type)
            query = query.filter(TrxAccount.type == filter_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid account type: {account_type}. Must be one of: {[t.value for t in TrxAccountType]}"
            )
    
    # Return results ordered by name
    return query.order_by(TrxAccount.name).all()

def calculate_account_balance(db: Session, account_id: int, user_id: int = None) -> dict:
    """
    Calculate the balance and transaction totals for a specific account
    
    Args:
        db: Database session
        account_id: ID of the account
        user_id: ID of the user who owns the account (optional if account object is used elsewhere)
        
    Returns:
        Dictionary containing balance details (total_income, total_expenses, 
        total_transfers_in, total_transfers_out, total_transfer_fees, overall balance, and payable_balance for credit cards)
    """
    from sqlalchemy import func
    from app.models.transaction import Transaction, TransactionType
    
    # Get the account to check its type
    account = None
    if user_id:
        account = db.query(TrxAccount).filter(
            TrxAccount.account_id == account_id,
            TrxAccount.user_id == user_id
        ).first()
    else:
        account = db.query(TrxAccount).filter(
            TrxAccount.account_id == account_id
        ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TrxAccount with id {account_id} not found"
        )
    
    # Calculate income
    income = db.query(func.coalesce(func.sum(Transaction.amount), Decimal('0.0'))).filter(
        Transaction.account_id == account_id,
        Transaction.transaction_type == TransactionType.INCOME
    ).scalar()
    
    # Calculate expenses
    expenses = db.query(func.coalesce(func.sum(Transaction.amount), Decimal('0.0'))).filter(
        Transaction.account_id == account_id,
        Transaction.transaction_type == TransactionType.EXPENSE
    ).scalar()
    
    # Calculate transfers
    transfers_out = db.query(func.coalesce(func.sum(Transaction.amount), Decimal('0.0'))).filter(
        Transaction.account_id == account_id,
        Transaction.transaction_type == TransactionType.TRANSFER
    ).scalar()
    
    transfers_in = db.query(func.coalesce(func.sum(Transaction.amount), Decimal('0.0'))).filter(
        Transaction.destination_account_id == account_id,
        Transaction.transaction_type == TransactionType.TRANSFER
    ).scalar()
    
    # Calculate transfer fees
    transfer_fees = db.query(func.coalesce(func.sum(Transaction.transfer_fee), Decimal('0.0'))).filter(
        Transaction.account_id == account_id,
        Transaction.transaction_type == TransactionType.TRANSFER
    ).scalar()
    
    # Calculate overall balance: income - expenses - transfers_out - transfer_fees + transfers_in
    balance = income - expenses - transfers_out - transfer_fees + transfers_in
    
    result = {
        "total_income": income,
        "total_expenses": expenses,
        "total_transfers_in": transfers_in,
        "total_transfers_out": transfers_out,
        "total_transfer_fees": transfer_fees,
        "balance": balance
    }
    
    # Add payable_balance for credit cards
    if account.type == TrxAccountType.CREDIT_CARD and account.limit is not None:
        result["payable_balance"] = account.limit - balance
    
    return result

def get_filtered_transactions(
    db: Session,
    user_id: int,
    account_name: Optional[str] = None,
    category_name: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    date_filter_type: Optional[str] = None,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
    order_by: Optional[str] = 'created_at',
    sort_order: Optional[str] = 'desc',
    return_query: bool = False
) -> Union[list[Transaction], Query]:
    """
    Get filtered transactions based on various criteria
    
    Args:
        db: Database session
        user_id: ID of the user who owns the transactions
        account_name: Optional filter by account name (will match partially)
        category_name: Optional filter by category name (will match partially)
        transaction_type: Optional filter by transaction type ('income', 'expense', 'transfer')
        start_date: Optional start date for custom date range filter
        end_date: Optional end date for custom date range filter
        date_filter_type: Optional filter by predefined date range ('day', 'week', 'month', 'year')
        limit: Maximum number of results to return
        skip: Number of results to skip for pagination
        order_by: Field to order by (default: 'created_at')
        sort_order: Sort order ('asc' or 'desc', default: 'desc')
        return_query: If True, returns the SQLAlchemy query object instead of results
        
    Returns:
        List of transactions matching the filters, or a query object if return_query is True
    """
    from sqlalchemy import or_
    from app.models.transaction import Transaction
    from app.models.account import TrxAccount
    from app.models.category import TrxCategory
    
    # Start with base query for user's transactions
    query = db.query(Transaction).filter(Transaction.user_id == user_id)
    
    # Apply account name filter if provided
    if account_name:
        # Find account(s) by name 
        account_ids = db.query(TrxAccount.account_id).filter(
            TrxAccount.user_id == user_id,
            TrxAccount.name.ilike(f"%{account_name}%")
        ).all()
        
        if not account_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No accounts found matching name: {account_name}"
            )
            
        # Get all transactions for any matching account (as source or destination)
        account_ids = [acc[0] for acc in account_ids]  # Extract IDs from result tuples
        query = query.filter(
            or_(
                Transaction.account_id.in_(account_ids),
                Transaction.destination_account_id.in_(account_ids)
            )
        )
    
    # Apply category name filter if provided
    if category_name:
        # Find category by name
        category_ids = db.query(TrxCategory.category_id).filter(
            TrxCategory.user_id == user_id,
            TrxCategory.name.ilike(f"%{category_name}%")
        ).all()
        
        if not category_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No categories found matching name: {category_name}"
            )
            
        # Get all transactions with matching category
        category_ids = [cat[0] for cat in category_ids]  # Extract IDs from result tuples
        query = query.filter(Transaction.category_id.in_(category_ids))
    
    # Apply transaction type filter if provided
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    # Apply date filters
    now = datetime.now()
    
    # Handle predefined date filter types
    if date_filter_type:
        date_filter_type = date_filter_type.lower()
        
        if date_filter_type == 'day':
            # Today
            start_date = datetime(now.year, now.month, now.day, 0, 0, 0)
            end_date = datetime(now.year, now.month, now.day, 23, 59, 59)
            
        elif date_filter_type == 'week':
            # Current week (starting Monday)
            start_date = now - timedelta(days=now.weekday())
            start_date = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
            end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59)
            
        elif date_filter_type == 'month':
            # Current month
            start_date = datetime(now.year, now.month, 1, 0, 0, 0)
            last_day = calendar.monthrange(now.year, now.month)[1]
            end_date = datetime(now.year, now.month, last_day, 23, 59, 59)
            
        elif date_filter_type == 'year':
            # Current year
            start_date = datetime(now.year, 1, 1, 0, 0, 0)
            end_date = datetime(now.year, 12, 31, 23, 59, 59)
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date filter type: {date_filter_type}. Must be one of: day, week, month, year"
            )
    
    # Apply custom date range if provided
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    
    # Apply sorting based on specified field and order
    if order_by:
        # Validate order_by field
        valid_fields = ['created_at', 'transaction_date', 'amount', 'description']
        if order_by not in valid_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid order_by field: {order_by}. Must be one of: {', '.join(valid_fields)}"
            )
        
        # Apply sorting direction
        sort_attr = getattr(Transaction, order_by)
        if sort_order and sort_order.lower() == 'asc':
            query = query.order_by(sort_attr.asc())
        else:
            query = query.order_by(sort_attr.desc())
    
    # Return query if requested (for counting or other operations)
    if return_query:
        return query
    
    # Apply pagination
    if skip:
        query = query.offset(skip)
    
    if limit:
        query = query.limit(limit)
    
    # Return results with joined relationships
    return query.all()

def calculate_date_range(period: str) -> Tuple[datetime, datetime]:
    """
    Calculate start and end dates based on period
    
    Args:
        period: String indicating the period ('day', 'week', 'month', 'year', 'all')
        
    Returns:
        Tuple containing (start_date, end_date)
        
    Raises:
        ValueError: If an invalid period is provided
    """
    from datetime import datetime, timedelta
    
    end_date = datetime.now()
    
    if period == "day":
        start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = end_date - timedelta(days=end_date.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "all":
        # Use a very old date as start
        start_date = datetime(2000, 1, 1)
    else:
        raise ValueError(f"Invalid period: {period}")
    
    return start_date, end_date 