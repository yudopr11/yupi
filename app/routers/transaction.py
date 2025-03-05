from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import calendar

from app.utils.database import get_db
from app.utils.auth import get_current_user
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
    get_filtered_transactions
)
from app.models.transaction import Transaction, TransactionType
from app.models.account import Account, AccountType
from app.models.category import Category, CategoryType
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionResponse, AccountBalanceResponse, DeleteTransactionResponse, TransactionList
from app.schemas.account import AccountCreate, AccountResponse, Account, AccountWithBalance, DeleteAccountResponse
from app.schemas.category import CategoryCreate, CategoryResponse, Category, DeleteCategoryResponse

router = APIRouter(
    prefix="/personal-transactions",
    tags=['Personal Transactions']
)

# Account endpoints
@router.post("/accounts", response_model=AccountResponse)
def create_account(account: AccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Create and validate account object
    new_account = prepare_account_for_db(account.model_dump(), current_user.id)
    
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    
    return {"data": new_account, "message": "Account created successfully"}

@router.put("/accounts/{account_id}", response_model=AccountResponse)
def update_account(account_id: int, account: AccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Validate that account exists and belongs to user
    existing_account = validate_account(db, account_id, current_user.id)
    
    # Validate credit card accounts have a limit
    if account.type == AccountType.CREDIT_CARD and account.limit is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credit card accounts must have a limit"
        )
    
    # Update account
    account_query = db.query(Account).filter(Account.account_id == account_id, Account.user_id == current_user.id)
    account_query.update(account.model_dump(), synchronize_session=False)
    db.commit()
    db.refresh(existing_account)
    
    return {"data": existing_account, "message": "Account updated successfully"}

@router.delete("/accounts/{account_id}", response_model=DeleteAccountResponse)
def delete_account(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Validate account
    account = validate_account(db, account_id, current_user.id)
    
    # Prepare deletion info
    deleted_account_info = prepare_deleted_account_info(account)
    
    # Delete account
    account_query = db.query(Account).filter(Account.account_id == account_id, Account.user_id == current_user.id)
    account_query.delete(synchronize_session=False)
    db.commit()
    
    return {
        "message": f"Account with id {account_id} deleted successfully",
        "deleted_item": deleted_account_info
    }

@router.get("/accounts/{account_id}/balance", response_model=AccountBalanceResponse)
def get_account_balance(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = db.query(Account).filter(Account.account_id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id {account_id} not found"
        )
    
    # Calculate balance details using the helper function
    balance_details = calculate_account_balance(db, account_id, current_user.id)
    
    return {
        "data": {
            "account_id": account_id,
            "balance": balance_details["balance"],
            "total_income": balance_details["total_income"],
            "total_expenses": balance_details["total_expenses"],
            "total_transfers_in": balance_details["total_transfers_in"],
            "total_transfers_out": balance_details["total_transfers_out"],
            "account": account
        },
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
        List of accounts with balances
    """
    accounts = get_filtered_accounts(db, current_user.id, account_type)
    
    # Add balance to each account
    result = []
    for account in accounts:
        account_dict = account.__dict__.copy()
        balance_details = calculate_account_balance(db, account.account_id, current_user.id)
        account_dict['balance'] = balance_details["balance"]
        # Create AccountWithBalance object
        account_with_balance = AccountWithBalance.model_validate(account_dict)
        result.append(account_with_balance)
        
    return result

# Category endpoints
@router.post("/categories", response_model=CategoryResponse)
def create_category(category: CategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Create and validate category object
    new_category = prepare_category_for_db(category.model_dump(), current_user.id)
    
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    
    return {"data": new_category, "message": "Category created successfully"}

@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, category: CategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Validate category
    existing_category = validate_category(db, category_id, current_user.id)
    
    # Update category
    category_query = db.query(Category).filter(Category.category_id == category_id, Category.user_id == current_user.id)
    category_query.update(category.model_dump(), synchronize_session=False)
    db.commit()
    db.refresh(existing_category)
    
    return {"data": existing_category, "message": "Category updated successfully"}

@router.delete("/categories/{category_id}", response_model=DeleteCategoryResponse)
def delete_category(category_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Validate category
    category = validate_category(db, category_id, current_user.id)
    
    # Prepare deletion info
    deleted_category_info = prepare_deleted_category_info(category)
    
    # Delete category
    category_query = db.query(Category).filter(Category.category_id == category_id, Category.user_id == current_user.id)
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
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Validate account exists and belongs to user
    account = validate_account(db, transaction.account_id, current_user.id)
    
    # Validate category if provided
    category = validate_category(db, transaction.category_id, current_user.id)
    
    # Validate category type matches transaction type
    validate_transaction_category_match(transaction.transaction_type, category)
    
    # Validate transfer details
    validate_transfer(
        transaction.transaction_type,
        transaction.destination_account_id,
        transaction.account_id,
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
def update_transaction(transaction_id: int, transaction: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    
    # Validate transfer details
    validate_transfer(
        transaction.transaction_type,
        transaction.destination_account_id,
        transaction.account_id,
        db,
        current_user.id
    )
    
    transaction_query.update(transaction.model_dump(), synchronize_session=False)
    db.commit()
    db.refresh(existing_transaction)
    
    return {"data": existing_transaction, "message": "Transaction updated successfully"}

@router.delete("/transactions/{transaction_id}", response_model=DeleteTransactionResponse)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None, 
    date_filter_type: Optional[str] = None,
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
        start_date: Optional start date for custom date range filter
        end_date: Optional end date for custom date range filter
        date_filter_type: Optional filter by predefined date range ('day', 'week', 'month', 'year')
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
            start_date=start_date,
            end_date=end_date,
            date_filter_type=date_filter_type,
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