from fastapi import APIRouter, Depends, HTTPException, status, Query as FastAPIQuery
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc
from typing import List, Optional
import uuid
from datetime import datetime, UTC
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
from app.models.account import TrxAccount as AccountModel, TrxAccountType
from app.models.category import TrxCategory as CategoryModel, TrxCategoryType
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionResponse, AccountBalanceResponse, DeleteTransactionResponse, TransactionList
from app.schemas.account import TrxAccountCreate, TrxAccountResponse, TrxAccountWithBalance, TrxDeleteAccountResponse
from app.schemas.category import TrxCategoryCreate, TrxCategoryResponse, TrxCategory, TrxDeleteCategoryResponse
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
@router.post("/accounts", response_model=TrxAccountResponse)
def create_account(account: TrxAccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Create a new financial account
    
    This endpoint creates a new account (bank account, credit card, or other) for the user.
    For credit card accounts, it automatically creates an initial balance transaction equal to the limit.
    
    Args:
        account (TrxAccountCreate): Account creation data including name, type, and optional limit
        db (Session): Database session
        current_user (User): The authenticated user creating the account
        
    Returns:
        TrxAccountResponse: Created account information and success message
        
    Raises:
        HTTPException: If user is not authenticated or is a guest user
    """
    # Create and validate account object
    new_account = prepare_account_for_db(account.model_dump(), current_user.user_id)
    
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    
    # For credit cards, create an initial balance transaction equal to the limit
    if new_account.type == TrxAccountType.CREDIT_CARD and new_account.limit is not None:
        # Find or create "Other" category for income
        other_category = db.query(CategoryModel).filter(
            CategoryModel.name == "Other",
            CategoryModel.type == TrxCategoryType.INCOME,
            CategoryModel.user_id == current_user.user_id
        ).first()
        
        if not other_category:
            # Create "Other" category if it doesn't exist
            other_category = CategoryModel(
                name="Other",
                type=TrxCategoryType.INCOME,
                user_id=current_user.user_id,
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
            user_id=current_user.user_id,
            uuid=uuid.uuid4()
        )
        
        db.add(initial_balance_tx)
        db.commit()
    
    return {"data": new_account, "message": "Account created successfully"}

@router.put("/accounts/{account_id}", response_model=TrxAccountResponse)
def update_account(account_id: int, account: TrxAccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Update an existing financial account
    
    This endpoint allows updating an account's details. For credit card accounts,
    it ensures that a limit is specified.
    
    Args:
        account_id (int): ID of the account to update
        account (TrxAccountCreate): Updated account data
        db (Session): Database session
        current_user (User): The authenticated user updating the account
        
    Returns:
        TrxAccountResponse: Updated account information and success message
        
    Raises:
        HTTPException: If account not found or user is not authorized
    """
    # Validate that account exists and belongs to user
    existing_account = validate_account(db, account_id, current_user.user_id)
    
    # Validate credit card accounts have a limit
    if account.type == TrxAccountType.CREDIT_CARD and account.limit is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credit card accounts must have a limit"
        )
    
    # Update account
    account_query = db.query(AccountModel).filter(AccountModel.account_id == account_id, AccountModel.user_id == current_user.user_id)
    account_query.update(account.model_dump(), synchronize_session=False)
    db.commit()
    db.refresh(existing_account)
    
    return {"data": existing_account, "message": "Account updated successfully"}

@router.delete("/accounts/{account_id}", response_model=TrxDeleteAccountResponse)
def delete_account(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Delete a financial account
    
    This endpoint permanently deletes an account and its associated transactions.
    Only the account owner can delete their accounts.
    
    Args:
        account_id (int): ID of the account to delete
        db (Session): Database session
        current_user (User): The authenticated user deleting the account
        
    Returns:
        TrxDeleteAccountResponse: Deletion confirmation and deleted account information
        
    Raises:
        HTTPException: If account not found or user is not authorized
    """
    # Validate account
    account = validate_account(db, account_id, current_user.user_id)
    
    # Prepare deletion info
    deleted_account_info = prepare_deleted_account_info(account)
    
    # Delete account
    account_query = db.query(AccountModel).filter(AccountModel.account_id == account_id, AccountModel.user_id == current_user.user_id)
    account_query.delete(synchronize_session=False)
    db.commit()
    
    return {
        "message": f"Account with id {account_id} deleted successfully",
        "deleted_item": deleted_account_info
    }

@router.get("/accounts/{account_id}/balance", response_model=AccountBalanceResponse)
def get_account_balance(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get detailed balance information for an account
    
    This endpoint provides comprehensive balance information including:
    - Current balance
    - Total income and expenses
    - Transfer amounts (in/out)
    - Transfer fees
    - Payable balance (for credit cards)
    
    Args:
        account_id (int): ID of the account to get balance for
        db (Session): Database session
        current_user (User): The authenticated user requesting the balance
        
    Returns:
        AccountBalanceResponse: Detailed balance information and account details
        
    Raises:
        HTTPException: If account not found or user is not authorized
    """
    account = db.query(AccountModel).filter(AccountModel.account_id == account_id, AccountModel.user_id == current_user.user_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id {account_id} not found"
        )
    
    # Calculate balance details using the helper function
    balance_details = calculate_account_balance(db, account_id, current_user.user_id)
    
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
    if account.type == TrxAccountType.CREDIT_CARD and account.limit is not None:
        response_data["payable_balance"] = balance_details.get("payable_balance")
    
    return {
        "data": response_data,
        "message": "Balance retrieved successfully"
    }

@router.get("/accounts", response_model=List[TrxAccountWithBalance])
def get_accounts(
    account_type: Optional[str] = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Get all accounts for the current user with optional filtering
    
    This endpoint retrieves all accounts owned by the user, with optional filtering
    by account type. For each account, it includes:
    - Basic account information
    - Current balance
    - Transaction totals
    - Payable balance (for credit cards)
    
    Args:
        account_type (str, optional): Filter accounts by type ('bank_account', 'credit_card', or 'other')
        db (Session): Database session
        current_user (User): The authenticated user requesting the accounts
        
    Returns:
        List[TrxAccountWithBalance]: List of accounts with their current balances and transaction totals
    """
    # Get accounts based on filters
    accounts = get_filtered_accounts(db, current_user.user_id, account_type)
    
    # Calculate balances for each account and create result objects
    result = []
    for account in accounts:
        balance_details = calculate_account_balance(db, account.account_id)
        account_with_balance = TrxAccountWithBalance.model_validate(account)
        account_with_balance.balance = balance_details["balance"]
        account_with_balance.total_income = balance_details["total_income"]
        account_with_balance.total_expenses = balance_details["total_expenses"]
        account_with_balance.total_transfers_in = balance_details["total_transfers_in"]
        account_with_balance.total_transfers_out = balance_details["total_transfers_out"]
        account_with_balance.total_transfer_fees = balance_details["total_transfer_fees"]
        
        # Add payable_balance for credit cards
        if account.type == TrxAccountType.CREDIT_CARD and account.limit is not None:
            account_with_balance.payable_balance = balance_details.get("payable_balance")
        
        result.append(account_with_balance)
    
    return result

# Category endpoints
@router.post("/categories", response_model=TrxCategoryResponse)
def create_category(category: TrxCategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Create a new transaction category
    
    This endpoint creates a new category for organizing transactions by type
    (income, expense, or transfer).
    
    Args:
        category (TrxCategoryCreate): Category creation data including name and type
        db (Session): Database session
        current_user (User): The authenticated user creating the category
        
    Returns:
        TrxCategoryResponse: Created category information and success message
        
    Raises:
        HTTPException: If user is not authenticated or is a guest user
    """
    # Create and validate category object
    new_category = prepare_category_for_db(category.model_dump(), current_user.user_id)
    
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    
    return {"data": new_category, "message": "Category created successfully"}

@router.put("/categories/{category_id}", response_model=TrxCategoryResponse)
def update_category(category_id: int, category: TrxCategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Update an existing transaction category
    
    This endpoint allows updating a category's details. Only the category owner
    can modify their categories.
    
    Args:
        category_id (int): ID of the category to update
        category (TrxCategoryCreate): Updated category data
        db (Session): Database session
        current_user (User): The authenticated user updating the category
        
    Returns:
        TrxCategoryResponse: Updated category information and success message
        
    Raises:
        HTTPException: If category not found or user is not authorized
    """
    # Validate category
    existing_category = validate_category(db, category_id, current_user.user_id)
    
    # Update category
    category_query = db.query(CategoryModel).filter(CategoryModel.category_id == category_id, CategoryModel.user_id == current_user.user_id)
    category_query.update(category.model_dump(), synchronize_session=False)
    db.commit()
    db.refresh(existing_category)
    
    return {"data": existing_category, "message": "Category updated successfully"}

@router.delete("/categories/{category_id}", response_model=TrxDeleteCategoryResponse)
def delete_category(category_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Delete a transaction category
    
    This endpoint permanently deletes a category. Only the category owner
    can delete their categories.
    
    Args:
        category_id (int): ID of the category to delete
        db (Session): Database session
        current_user (User): The authenticated user deleting the category
        
    Returns:
        TrxDeleteCategoryResponse: Deletion confirmation and deleted category information
        
    Raises:
        HTTPException: If category not found or user is not authorized
    """
    # Validate category
    category = validate_category(db, category_id, current_user.user_id)
    
    # Prepare deletion info
    deleted_category_info = prepare_deleted_category_info(category)
    
    # Delete category
    category_query = db.query(CategoryModel).filter(CategoryModel.category_id == category_id, CategoryModel.user_id == current_user.user_id)
    category_query.delete(synchronize_session=False)
    db.commit()
    
    return {
        "message": f"Category with id {category_id} deleted successfully",
        "deleted_item": deleted_category_info
    }

@router.get("/categories", response_model=List[TrxCategory])
def get_categories(
    category_type: Optional[str] = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Get all categories for the current user with optional filtering
    
    This endpoint retrieves all categories owned by the user, with optional
    filtering by category type (income, expense, or transfer).
    
    Args:
        category_type (str, optional): Filter categories by type
        db (Session): Database session
        current_user (User): The authenticated user requesting the categories
        
    Returns:
        List[TrxCategory]: List of categories matching the filter criteria
    """
    categories = get_filtered_categories(db, current_user.user_id, category_type)
    return categories

# Transaction endpoints
@router.post("/transactions", response_model=TransactionResponse)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Create a new transaction
    
    This endpoint creates a new transaction (income, expense, or transfer) with
    validation for account and category compatibility.
    
    Args:
        transaction (TransactionCreate): Transaction creation data including amount, type, account, and category
        db (Session): Database session
        current_user (User): The authenticated user creating the transaction
        
    Returns:
        TransactionResponse: Created transaction information and success message
        
    Raises:
        HTTPException: If validation fails or user is not authorized
    """
    # Validate account exists and belongs to user
    account = validate_account(db, transaction.account_id, current_user.user_id)
    
    # Validate category if provided
    category = validate_category(db, transaction.category_id, current_user.user_id)
    
    # Validate category type matches transaction type
    validate_transaction_category_match(transaction.transaction_type, category)
    
    # Credit card validation for expenses
    if (
        transaction.transaction_type == TransactionType.EXPENSE and 
        account.type == TrxAccountType.CREDIT_CARD
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
        current_user.user_id
    )
    
    # Create transaction
    new_transaction = prepare_transaction_for_db(transaction.model_dump(), current_user.user_id)
    
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    
    return {"data": new_transaction, "message": "Transaction created successfully"}

@router.put("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(transaction_id: int, transaction: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Update an existing transaction
    
    This endpoint allows updating a transaction's details. Only the transaction
    owner can modify their transactions.
    
    Args:
        transaction_id (int): ID of the transaction to update
        transaction (TransactionCreate): Updated transaction data
        db (Session): Database session
        current_user (User): The authenticated user updating the transaction
        
    Returns:
        TransactionResponse: Updated transaction information and success message
        
    Raises:
        HTTPException: If transaction not found or user is not authorized
    """
    # Check if transaction exists and belongs to user
    transaction_query = db.query(Transaction).filter(
        Transaction.transaction_id == transaction_id,
        Transaction.user_id == current_user.user_id
    )
    existing_transaction = transaction_query.first()
    
    if not existing_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found"
        )
    
    # Validate account exists and belongs to user
    account = validate_account(db, transaction.account_id, current_user.user_id)
    
    # Validate category if provided
    category = validate_category(db, transaction.category_id, current_user.user_id)
    
    # Validate category type matches transaction type
    validate_transaction_category_match(transaction.transaction_type, category)
    
    # Credit card validation for expenses - only check if this is a new expense or amount increased
    if (
        transaction.transaction_type == TransactionType.EXPENSE and 
        account.type == TrxAccountType.CREDIT_CARD and
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
        current_user.user_id
    )
    
    transaction_query.update(transaction.model_dump(), synchronize_session=False)
    db.commit()
    db.refresh(existing_transaction)
    
    return {"data": existing_transaction, "message": "Transaction updated successfully"}

@router.delete("/transactions/{transaction_id}", response_model=DeleteTransactionResponse)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Delete a transaction
    
    This endpoint permanently deletes a transaction. Only the transaction
    owner can delete their transactions.
    
    Args:
        transaction_id (int): ID of the transaction to delete
        db (Session): Database session
        current_user (User): The authenticated user deleting the transaction
        
    Returns:
        DeleteTransactionResponse: Deletion confirmation and deleted transaction information
        
    Raises:
        HTTPException: If transaction not found or user is not authorized
    """
    # Find transaction
    transaction_query = db.query(Transaction).filter(
        Transaction.transaction_id == transaction_id,
        Transaction.user_id == current_user.user_id
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
    Get paginated list of transactions with advanced filtering
    
    This endpoint retrieves transactions with various filters:
    - Account and category filtering
    - Transaction type filtering
    - Date range filtering
    - Sorting and pagination
    
    Args:
        account_name (str, optional): Filter by account name
        category_name (str, optional): Filter by category name
        transaction_type (str, optional): Filter by transaction type
        start_date (datetime, optional): Start date for filtering
        end_date (datetime, optional): End date for filtering
        date_filter_type (str, optional): Type of date filtering
        order_by (str): Field to sort by
        sort_order (str): Sort order ('asc' or 'desc')
        limit (int): Maximum number of transactions to return
        skip (int): Number of transactions to skip
        db (Session): Database session
        current_user (User): The authenticated user requesting the transactions
        
    Returns:
        TransactionList: Paginated list of transactions with total count
    """
    try:
        # Get the base query with all filters applied but without pagination
        query = get_filtered_transactions(
            db=db,
            user_id=current_user.user_id,
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
    Get financial summary statistics
    
    This endpoint provides a comprehensive financial summary including:
    - Total income and expenses
    - Net income
    - Average transaction amounts
    - Transaction counts
    - Period-specific calculations
    
    Args:
        start_date (datetime, optional): Start date for statistics
        end_date (datetime, optional): End date for statistics
        period (str): Time period for calculations (day, week, month, year, all)
        db (Session): Database session
        current_user (User): The authenticated user requesting the statistics
        
    Returns:
        FinancialSummaryResponse: Detailed financial summary statistics
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
        Transaction.user_id == current_user.user_id,
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
    Get transaction distribution by category
    
    This endpoint provides statistics about how transactions are distributed
    across different categories, including:
    - Category-wise totals
    - Percentage distributions
    - Period-specific calculations
    
    Args:
        transaction_type (str): Type of transactions to analyze
        start_date (datetime, optional): Start date for statistics
        end_date (datetime, optional): End date for statistics
        period (str): Time period for calculations
        db (Session): Database session
        current_user (User): The authenticated user requesting the statistics
        
    Returns:
        CategoryDistributionResponse: Category-wise transaction distribution
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
        Transaction.user_id == current_user.user_id,
        CategoryModel.user_id == current_user.user_id,
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
        Transaction.user_id == current_user.user_id,
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
    
    This endpoint provides time-series data about transactions, including:
    - Daily/weekly/monthly trends
    - Multiple transaction type analysis
    - Period-specific aggregations
    
    Args:
        start_date (datetime, optional): Start date for trends
        end_date (datetime, optional): End date for trends
        period (str): Time period for calculations
        group_by (str): Grouping interval (day, week, month)
        transaction_types (List[str]): Types of transactions to analyze
        db (Session): Database session
        current_user (User): The authenticated user requesting the trends
        
    Returns:
        TransactionTrendsResponse: Time-series transaction trends
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
        Transaction.user_id == current_user.user_id,
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
    Get summary statistics for all accounts
    
    This endpoint provides an overview of all accounts, including:
    - Account balances
    - Transaction totals
    - Account-specific statistics
    
    Args:
        db (Session): Database session
        current_user (User): The authenticated user requesting the summary
        
    Returns:
        AccountSummaryResponse: Summary statistics for all accounts
    """
    # Get all accounts for the user
    accounts = db.query(AccountModel).filter(AccountModel.user_id == current_user.user_id).all()
    
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
        balance_info = calculate_account_balance(db, account.account_id, current_user.user_id)
        balance = balance_info["balance"]
        
        # Find the latest transaction date for this account (as source or destination)
        latest_tx_subquery = db.query(
            func.max(Transaction.transaction_date)
        ).filter(
            or_(
                Transaction.account_id == account.account_id,
                Transaction.destination_account_id == account.account_id
            ),
            Transaction.user_id == current_user.user_id
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

