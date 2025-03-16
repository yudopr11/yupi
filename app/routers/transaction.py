from fastapi import APIRouter, Depends, HTTPException, status, Query as FastAPIQuery
from sqlalchemy.orm import Session, Query
from sqlalchemy import func, case, or_, desc
from typing import List, Optional, Union
import uuid
from datetime import datetime, timedelta, UTC
import calendar
from decimal import Decimal

from app.utils.database import get_db
from app.utils.auth import get_current_user, get_non_guest_user
from app.utils.transaction_helpers import (
    validate_account, 
    validate_category, 
    validate_transaction_category_match, 
    validate_transfer,
    prepare_account_for_db,
    prepare_category_for_db,
    prepare_transaction_for_db,
    prepare_deleted_account_info,
    prepare_deleted_category_info,
    prepare_deleted_transaction_info,
    get_filtered_accounts,
    get_filtered_categories,
    calculate_account_balance,
    get_filtered_transactions,
    calculate_date_range
)
from app.models.transaction import Transaction, TransactionType
from app.models.account import Account as AccountModel, AccountType
from app.models.category import Category as CategoryModel, CategoryType
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionResponse, AccountBalanceResponse, DeleteTransactionResponse, TransactionList
from app.schemas.account import AccountCreate, AccountResponse, AccountWithBalance, DeleteAccountResponse
from app.schemas.category import CategoryCreate, CategoryResponse, Category, DeleteCategoryResponse
from app.schemas.statistics import (
    FinancialSummaryResponse, 
    CategoryDistributionResponse, 
    TransactionTrendsResponse, 
    AccountSummaryResponse
)

router = APIRouter(
    prefix="/personal-transactions",
    tags=['Personal Transactions']
)

# Account endpoints
@router.post("/accounts", response_model=AccountResponse)
def create_account(account: AccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    # Create and validate account object
    new_account = prepare_account_for_db(account.model_dump(), current_user.id)
    
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    
    # For credit cards, create an initial balance transaction equal to the limit
    if new_account.type == AccountType.CREDIT_CARD and new_account.limit is not None:
        # Find or create "Other" category for income
        other_category = db.query(CategoryModel).filter(
            CategoryModel.name == "Other",
            CategoryModel.type == CategoryType.INCOME,
            CategoryModel.user_id == current_user.id
        ).first()
        
        if not other_category:
            # Create "Other" category if it doesn't exist
            other_category = CategoryModel(
                name="Other",
                type=CategoryType.INCOME,
                user_id=current_user.id,
                uuid=str(uuid.uuid4())
            )
            db.add(other_category)
            db.commit()
            db.refresh(other_category)
        
        initial_balance_tx = Transaction(
            transaction_date=datetime.now(UTC),
            description="Initial credit card balance",
            amount=new_account.limit,
            transaction_type=TransactionType.INCOME,  # Use income to add positive balance
            account_id=new_account.account_id,
            category_id=other_category.category_id,  # Set category to "Other"
            user_id=current_user.id,
            uuid=uuid.uuid4()
        )
        
        db.add(initial_balance_tx)
        db.commit()
    
    return {"data": new_account, "message": "Account created successfully"}

@router.put("/accounts/{account_id}", response_model=AccountResponse)
def update_account(account_id: int, account: AccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    # Validate that account exists and belongs to user
    existing_account = validate_account(db, account_id, current_user.id)
    
    # Validate credit card accounts have a limit
    if account.type == AccountType.CREDIT_CARD and account.limit is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credit card accounts must have a limit"
        )
    
    # Update account
    account_query = db.query(AccountModel).filter(AccountModel.account_id == account_id, AccountModel.user_id == current_user.id)
    account_query.update(account.model_dump(), synchronize_session=False)
    db.commit()
    db.refresh(existing_account)
    
    return {"data": existing_account, "message": "Account updated successfully"}

@router.delete("/accounts/{account_id}", response_model=DeleteAccountResponse)
def delete_account(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    # Validate account
    account = validate_account(db, account_id, current_user.id)
    
    # Prepare deletion info
    deleted_account_info = prepare_deleted_account_info(account)
    
    # Delete account
    account_query = db.query(AccountModel).filter(AccountModel.account_id == account_id, AccountModel.user_id == current_user.id)
    account_query.delete(synchronize_session=False)
    db.commit()
    
    return {
        "message": f"Account with id {account_id} deleted successfully",
        "deleted_item": deleted_account_info
    }

@router.get("/accounts/{account_id}/balance", response_model=AccountBalanceResponse)
def get_account_balance(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = db.query(AccountModel).filter(AccountModel.account_id == account_id, AccountModel.user_id == current_user.id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id {account_id} not found"
        )
    
    # Calculate balance details using the helper function
    balance_details = calculate_account_balance(db, account_id, current_user.id)
    
    response_data = {
        "account_id": account_id,
        "balance": balance_details["balance"],
        "total_income": balance_details["total_income"],
        "total_expenses": balance_details["total_expenses"],
        "total_transfers_in": balance_details["total_transfers_in"],
        "total_transfers_out": balance_details["total_transfers_out"],
        "total_transfer_fees": balance_details["total_transfer_fees"],
        "account": account
    }
    
    # Add payable_balance for credit cards
    if account.type == AccountType.CREDIT_CARD and account.limit is not None:
        response_data["payable_balance"] = balance_details.get("payable_balance")
    
    return {
        "data": response_data,
        "message": "Balance retrieved successfully"
    }

@router.get("/accounts", response_model=List[AccountWithBalance])
def get_accounts(
    account_type: Optional[str] = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Get all accounts for the current user with optional filtering by account type,
    including calculated balance for each account
    
    Args:
        account_type: Optional filter for account type ('bank_account', 'credit_card', or 'other')
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of accounts with calculated balances
    """
    # Get accounts based on filters
    accounts = get_filtered_accounts(db, current_user.id, account_type)
    
    # Calculate balances for each account and create result objects
    result = []
    for account in accounts:
        balance_details = calculate_account_balance(db, account.account_id)
        account_with_balance = AccountWithBalance.model_validate(account)
        account_with_balance.balance = balance_details["balance"]
        account_with_balance.total_income = balance_details["total_income"]
        account_with_balance.total_expenses = balance_details["total_expenses"]
        account_with_balance.total_transfers_in = balance_details["total_transfers_in"]
        account_with_balance.total_transfers_out = balance_details["total_transfers_out"]
        account_with_balance.total_transfer_fees = balance_details["total_transfer_fees"]
        
        # Add payable_balance for credit cards
        if account.type == AccountType.CREDIT_CARD and account.limit is not None:
            account_with_balance.payable_balance = balance_details.get("payable_balance")
        
        result.append(account_with_balance)
    
    return result

# Category endpoints
@router.post("/categories", response_model=CategoryResponse)
def create_category(category: CategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    # Create and validate category object
    new_category = prepare_category_for_db(category.model_dump(), current_user.id)
    
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    
    return {"data": new_category, "message": "Category created successfully"}

@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, category: CategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    # Validate category
    existing_category = validate_category(db, category_id, current_user.id)
    
    # Update category
    category_query = db.query(CategoryModel).filter(CategoryModel.category_id == category_id, CategoryModel.user_id == current_user.id)
    category_query.update(category.model_dump(), synchronize_session=False)
    db.commit()
    db.refresh(existing_category)
    
    return {"data": existing_category, "message": "Category updated successfully"}

@router.delete("/categories/{category_id}", response_model=DeleteCategoryResponse)
def delete_category(category_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    # Validate category
    category = validate_category(db, category_id, current_user.id)
    
    # Prepare deletion info
    deleted_category_info = prepare_deleted_category_info(category)
    
    # Delete category
    category_query = db.query(CategoryModel).filter(CategoryModel.category_id == category_id, CategoryModel.user_id == current_user.id)
    category_query.delete(synchronize_session=False)
    db.commit()
    
    return {
        "message": f"Category with id {category_id} deleted successfully",
        "deleted_item": deleted_category_info
    }

@router.get("/categories", response_model=List[Category])
def get_categories(
    category_type: Optional[str] = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Get all categories for the current user with optional filtering by category type
    
    Args:
        category_type: Optional filter for category type ('income' or 'expense')
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of categories
    """
    categories = get_filtered_categories(db, current_user.id, category_type)
    return categories

# Transaction endpoints
@router.post("/transactions", response_model=TransactionResponse)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    # Validate account exists and belongs to user
    account = validate_account(db, transaction.account_id, current_user.id)
    
    # Validate category if provided
    category = validate_category(db, transaction.category_id, current_user.id)
    
    # Validate category type matches transaction type
    validate_transaction_category_match(transaction.transaction_type, category)
    
    # Credit card validation for expenses
    if (
        transaction.transaction_type == TransactionType.EXPENSE and 
        account.type == AccountType.CREDIT_CARD
    ):
        # Calculate current balance
        balance_details = calculate_account_balance(db, account.account_id)
        if balance_details["balance"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Cannot create expense with this credit card - no available balance. Please top up by creating a transfer to this account."
            )
    
    # Validate transfer details
    validate_transfer(
        transaction.transaction_type,
        transaction.destination_account_id,
        transaction.account_id,
        transaction.transfer_fee,
        db,
        current_user.id
    )
    
    # Create transaction
    new_transaction = prepare_transaction_for_db(transaction.model_dump(), current_user.id)
    
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    
    return {"data": new_transaction, "message": "Transaction created successfully"}

@router.put("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(transaction_id: int, transaction: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    # Check if transaction exists and belongs to user
    transaction_query = db.query(Transaction).filter(
        Transaction.transaction_id == transaction_id,
        Transaction.user_id == current_user.id
    )
    existing_transaction = transaction_query.first()
    
    if not existing_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found"
        )
    
    # Validate account exists and belongs to user
    account = validate_account(db, transaction.account_id, current_user.id)
    
    # Validate category if provided
    category = validate_category(db, transaction.category_id, current_user.id)
    
    # Validate category type matches transaction type
    validate_transaction_category_match(transaction.transaction_type, category)
    
    # Credit card validation for expenses - only check if this is a new expense or amount increased
    if (
        transaction.transaction_type == TransactionType.EXPENSE and 
        account.type == AccountType.CREDIT_CARD and
        (existing_transaction.transaction_type != TransactionType.EXPENSE or
         transaction.amount > existing_transaction.amount)
    ):
        # Calculate current balance, excluding the current transaction
        balance_details = calculate_account_balance(db, account.account_id)
        
        # Add back the existing transaction amount if it's an expense from the same account
        if (existing_transaction.transaction_type == TransactionType.EXPENSE and 
            existing_transaction.account_id == transaction.account_id):
            adjusted_balance = balance_details["balance"] + existing_transaction.amount
        else:
            adjusted_balance = balance_details["balance"]
        
        # Check if there's enough balance for the new expense amount
        if adjusted_balance - transaction.amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Cannot update expense with this credit card - insufficient available balance. Please top up by creating a transfer to this account."
            )
    
    # Validate transfer details
    validate_transfer(
        transaction.transaction_type,
        transaction.destination_account_id,
        transaction.account_id,
        transaction.transfer_fee,
        db,
        current_user.id
    )
    
    transaction_query.update(transaction.model_dump(), synchronize_session=False)
    db.commit()
    db.refresh(existing_transaction)
    
    return {"data": existing_transaction, "message": "Transaction updated successfully"}

@router.delete("/transactions/{transaction_id}", response_model=DeleteTransactionResponse)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    # Find transaction
    transaction_query = db.query(Transaction).filter(
        Transaction.transaction_id == transaction_id,
        Transaction.user_id == current_user.id
    )
    transaction = transaction_query.first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found"
        )
    
    # Prepare deletion info
    deleted_transaction_info = prepare_deleted_transaction_info(transaction)
    
    # Delete transaction
    transaction_query.delete(synchronize_session=False)
    db.commit()
    
    return {
        "message": f"Transaction with id {transaction_id} deleted successfully",
        "deleted_item": deleted_transaction_info
    }

@router.get("/transactions", response_model=TransactionList)
def get_transactions(
    account_name: Optional[str] = None,
    category_name: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None, 
    date_filter_type: Optional[str] = None,
    order_by: Optional[str] = 'created_at',
    sort_order: Optional[str] = 'desc',
    limit: Optional[int] = 10,
    skip: Optional[int] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get transactions for the current user with various filtering options
    
    Args:
        account_name: Optional filter by account name (will match partially)
        category_name: Optional filter by category name (will match partially)
        transaction_type: Optional filter by transaction type ('income', 'expense', 'transfer')
        start_date: Optional start date for custom date range filter
        end_date: Optional end date for custom date range filter
        date_filter_type: Optional filter by predefined date range ('day', 'week', 'month', 'year')
        order_by: Field to order by (default: 'created_at')
        sort_order: Sort order ('asc' or 'desc', default: 'desc')
        limit: Maximum number of results to return (default: 10)
        skip: Number of results to skip for pagination (default: 0)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of transactions matching the filters with pagination metadata
    """
    try:
        # Get the base query with all filters applied but without pagination
        query = get_filtered_transactions(
            db=db,
            user_id=current_user.id,
            account_name=account_name,
            category_name=category_name,
            transaction_type=transaction_type,
            start_date=start_date,
            end_date=end_date,
            date_filter_type=date_filter_type,
            order_by=order_by,
            sort_order=sort_order,
            return_query=True  # Return query object instead of results
        )
        
        # Get total count using the same query (more efficient than fetching all results)
        total_count = query.count()
        
        # Apply pagination and get one extra item to check if there are more results
        transactions = query.offset(skip).limit(limit + 1).all()
        
        # Check if there are more items
        has_more = len(transactions) > limit
        if has_more:
            transactions = transactions[:limit]  # Remove the extra item
        
        return {
            "data": transactions,
            "total_count": total_count,
            "has_more": has_more,
            "limit": limit,
            "skip": skip,
            "message": "Transactions retrieved successfully"
        }
        
    except HTTPException as e:
        # Convert helper function exceptions to a consistent response format
        return {
            "data": [],
            "total_count": 0,
            "has_more": False,
            "limit": limit,
            "skip": skip,
            "message": e.detail
        }

# Statistics endpoints
@router.get("/statistics/summary", response_model=FinancialSummaryResponse)
def get_financial_summary(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    period: str = "month",  # Options: day, week, month, year, all
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get financial summary for a given period
    
    Args:
        start_date: Optional start date for custom date range
        end_date: Optional end date for custom date range
        period: Period to calculate summary for ('day', 'week', 'month', 'year', 'all')
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Summary of financial data for the specified period
    """
    # Calculate date range based on period if not provided
    if not start_date or not end_date:
        try:
            start_date, end_date = calculate_date_range(period)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # Get totals by transaction type
    query = db.query(
        Transaction.transaction_type,
        func.sum(Transaction.amount).label("total")
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date.between(start_date, end_date)
    ).group_by(Transaction.transaction_type)
    
    results = query.all()
    
    # Format the results
    summary = {
        "period": {
            "start_date": start_date,
            "end_date": end_date,
            "period_type": period
        },
        "totals": {
            "income": Decimal('0.0'),
            "expense": Decimal('0.0'),
            "transfer": Decimal('0.0'),
            "net": Decimal('0.0')
        }
    }
    
    for row in results:
        transaction_type, total = row
        summary["totals"][transaction_type.value] = total
    
    # Calculate net
    summary["totals"]["net"] = summary["totals"]["income"] - summary["totals"]["expense"]
    
    return summary

@router.get("/statistics/by-category", response_model=CategoryDistributionResponse)
def get_category_distribution(
    transaction_type: str = "expense",  # Default to expense
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    period: str = "month",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get distribution of transactions by category for a given period
    
    Args:
        transaction_type: Type of transactions to analyze (income or expense)
        start_date: Optional start date for custom date range
        end_date: Optional end date for custom date range
        period: Period to analyze trends for ('day', 'week', 'month', 'year', 'all')
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Distribution of transactions by category with percentages
    """
    # Validate transaction type
    if transaction_type not in ("income", "expense"):
        raise HTTPException(status_code=400, detail="Transaction type must be 'income' or 'expense'")
    
    # Calculate date range if not provided
    if not start_date or not end_date:
        try:
            start_date, end_date = calculate_date_range(period)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # Convert transaction_type to enum
    tx_type = TransactionType(transaction_type)
    
    # Query for totals by category
    query = db.query(
        CategoryModel.name,
        CategoryModel.uuid,
        func.sum(Transaction.amount).label("total")
    ).join(
        Transaction, 
        Transaction.category_id == CategoryModel.category_id
    ).filter(
        Transaction.user_id == current_user.id,
        CategoryModel.user_id == current_user.id,
        Transaction.transaction_date.between(start_date, end_date),
        Transaction.transaction_type == tx_type
    ).group_by(
        CategoryModel.category_id
    ).order_by(
        desc("total")
    )
    
    results = query.all()
    
    # Calculate total for the period
    total_query = db.query(
        func.sum(Transaction.amount).label("total")
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date.between(start_date, end_date),
        Transaction.transaction_type == tx_type
    )
    
    total_result = total_query.scalar() or Decimal('0.0')
    total = total_result
    
    # Process the results
    categories = []
    for name, uuid, category_total in results:
        percentage = (category_total / total * Decimal('100')) if total > Decimal('0') else Decimal('0.0')
        
        categories.append({
            "name": name,
            "uuid": str(uuid),
            "total": category_total,
            "percentage": percentage
        })
    
    return {
        "period": {
            "start_date": start_date,
            "end_date": end_date,
            "period_type": period
        },
        "transaction_type": transaction_type,
        "total": total,
        "categories": categories
    }

@router.get("/statistics/trends", response_model=TransactionTrendsResponse)
def get_transaction_trends(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    period: str = "month",
    group_by: str = "day",  # Options: day, week, month
    transaction_types: List[str] = FastAPIQuery(["income", "expense"]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get transaction trends over time
    
    Args:
        start_date: Optional start date for custom date range
        end_date: Optional end date for custom date range
        period: Period to analyze trends for ('day', 'week', 'month', 'year', 'all')
        group_by: How to group results ('day', 'week', 'month', 'year')
        transaction_types: Types of transactions to include in the analysis
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Trends of transactions over time
    """
    # Calculate date range if not provided
    if not start_date or not end_date:
        try:
            start_date, end_date = calculate_date_range(period)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # Validate group_by parameter
    if group_by not in ("day", "week", "month", "year"):
        raise HTTPException(status_code=400, detail="Invalid group_by parameter. Must be 'day', 'week', 'month', or 'year'")
    
    # Validate transaction_types
    for tx_type in transaction_types:
        if tx_type not in ("income", "expense", "transfer"):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid transaction type '{tx_type}'. Must be 'income', 'expense', or 'transfer'"
            )
    
    # Dynamically build the date grouping expression based on group_by
    if group_by == "day":
        date_trunc = func.date_trunc('day', Transaction.transaction_date)
    elif group_by == "week":
        date_trunc = func.date_trunc('week', Transaction.transaction_date)
    elif group_by == "month":
        date_trunc = func.date_trunc('month', Transaction.transaction_date)
    elif group_by == "year":
        date_trunc = func.date_trunc('year', Transaction.transaction_date)
    
    # Query to get totals by date and transaction type
    query = db.query(
        date_trunc.label("date"),
        Transaction.transaction_type,
        func.sum(Transaction.amount).label("total")
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date.between(start_date, end_date),
        Transaction.transaction_type.in_(transaction_types)
    ).group_by(
        date_trunc,
        Transaction.transaction_type
    ).order_by(
        date_trunc
    )
    
    results = query.all()
    
    # Process the results
    trends_data = {}
    for date, tx_type, total in results:
        date_str = date.strftime("%Y-%m-%d")
        if date_str not in trends_data:
            trends_data[date_str] = {
                "date": date_str,
                "income": Decimal('0.0'),
                "expense": Decimal('0.0'),
                "transfer": Decimal('0.0'),
                "net": Decimal('0.0')
            }
        
        trends_data[date_str][tx_type.value] = total
        # Update the net value
        trends_data[date_str]["net"] = trends_data[date_str]["income"] - trends_data[date_str]["expense"]
    
    # Convert the dictionary to a list for the response
    trends = list(trends_data.values())
    
    return {
        "period": {
            "start_date": start_date,
            "end_date": end_date,
            "period_type": period,
            "group_by": group_by
        },
        "trends": trends
    }

@router.get("/statistics/account-summary", response_model=AccountSummaryResponse)
def get_account_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a summary of all accounts with balances and credit utilization
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Summary of all accounts with total balance, credit utilization, and balance by account type.
        Accounts are sorted by the time of the latest transaction using that account.
    """
    # Get all accounts for the user
    accounts = db.query(AccountModel).filter(AccountModel.user_id == current_user.id).all()
    
    # For each account, calculate the balance and get latest transaction date
    account_summaries = []
    total_balance = Decimal('0.0')
    total_available_credit = Decimal('0.0')
    total_credit_limit = Decimal('0.0')
    balances_by_type = {
        "bank_account": Decimal('0.0'),
        "credit_card": Decimal('0.0'),
        "other": Decimal('0.0')
    }
    
    accounts_with_latest_tx = []
    
    for account in accounts:
        balance_info = calculate_account_balance(db, account.account_id, current_user.id)
        balance = balance_info["balance"]
        
        # Find the latest transaction date for this account (as source or destination)
        latest_tx_subquery = db.query(
            func.max(Transaction.transaction_date)
        ).filter(
            or_(
                Transaction.account_id == account.account_id,
                Transaction.destination_account_id == account.account_id
            ),
            Transaction.user_id == current_user.id
        ).scalar()
        
        # Default to account creation date if no transactions
        latest_tx_date = latest_tx_subquery or account.created_at
        
        # Add to total balance based on account type
        if account.type == "credit_card":
            # For credit cards, we track the negative balance (what we owe)
            payable_balance = balance_info["payable_balance"]
            
            account_summary = {
                "account_id": account.account_id,
                "uuid": str(account.uuid),
                "name": account.name,
                "type": account.type,
                "balance": balance,
                "payable_balance": payable_balance,
                "limit": account.limit,
                "utilization_percentage": (payable_balance / account.limit * Decimal('100')) if account.limit else Decimal('0.0')
            }
            
            total_available_credit += max(Decimal('0'), account.limit - payable_balance)
            total_credit_limit += account.limit
            balances_by_type["credit_card"] += balance
            
        else:
            account_summary = {
                "account_id": account.account_id,
                "uuid": str(account.uuid),
                "name": account.name,
                "type": account.type,
                "balance": balance
            }
            
            # Add to the appropriate account type balance
            if account.type in balances_by_type:
                balances_by_type[account.type] += balance
        
        # Store account with its latest transaction date
        accounts_with_latest_tx.append((account_summary, latest_tx_date))
        total_balance += balance
    
    # Sort accounts by latest transaction date (newest first)
    accounts_with_latest_tx.sort(key=lambda x: x[1], reverse=True)
    account_summaries = [account for account, _ in accounts_with_latest_tx]
    
    # Calculate credit utilization percentage
    credit_utilization = Decimal('0.0')
    if total_credit_limit > Decimal('0'):
        credit_utilization = (total_credit_limit - total_available_credit) / total_credit_limit * Decimal('100')
    
    return {
        "total_balance": total_balance,
        "available_credit": total_available_credit,
        "credit_utilization": credit_utilization,
        "by_account_type": balances_by_type,
        "accounts": account_summaries
    }

