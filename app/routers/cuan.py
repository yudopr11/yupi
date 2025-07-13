from fastapi import APIRouter, Depends, HTTPException, status, Query as FastAPIQuery
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc
from typing import List, Optional
import uuid
from datetime import datetime, UTC
from decimal import Decimal

from app.utils.database import get_db
from app.utils.auth import get_current_user, get_non_guest_user
from app.utils.cuan_helpers import (
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
    calculate_date_range,
    get_accounts_with_balance
)
from app.models.cuan import Transaction, TransactionType, TrxAccount as AccountModel, TrxAccountType, TrxCategory as CategoryModel, TrxCategoryType
from app.models.auth import User
from app.schemas.cuan import (
    TrxAccountCreate, TrxAccountResponse, TrxAccountWithBalance, TrxDeleteAccountResponse,
    TrxCategoryCreate, TrxCategoryResponse, TrxDeleteCategoryResponse,
    TransactionCreate, TransactionResponse, AccountBalanceResponse, DeleteTransactionResponse, TransactionList,
    TrxCategoryResponseData, TransactionResponseData, AccountBalance
)
from app.schemas.cuan import (
    FinancialSummaryResponse, 
    CategoryDistributionResponse, 
    TransactionTrendsResponse, 
    AccountSummaryResponse
)

router = APIRouter(
    prefix="/cuan",
    tags=['Cuan']
)

# --- Account Endpoints ---

@router.post("/accounts", status_code=status.HTTP_201_CREATED, response_model=TrxAccountResponse)
def create_account(account: TrxAccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Create a new financial account.
    For credit card accounts, an initial balance transaction is automatically created equal to the limit.
    """
    new_account = prepare_account_for_db(account.model_dump(), current_user.id)
    db.add(new_account)
    db.commit()
    db.refresh(new_account)

    if new_account.type == TrxAccountType.CREDIT_CARD and new_account.limit is not None:
        other_category = db.query(CategoryModel).filter(
            CategoryModel.name == "Other",
            CategoryModel.type == TrxCategoryType.INCOME,
            CategoryModel.user_id == current_user.id
        ).first()
        if not other_category:
            other_category = CategoryModel(id=uuid.uuid4(), name="Other", type=TrxCategoryType.INCOME, user_id=current_user.id)
            db.add(other_category)
            db.commit()
            db.refresh(other_category)
        
        initial_tx = Transaction(
            id=uuid.uuid4(),
            transaction_date=datetime.now(UTC),
            description="Initial credit card balance",
            amount=new_account.limit,
            transaction_type=TransactionType.INCOME,
            account_id=new_account.id,
            category_id=other_category.id,
            user_id=current_user.id
        )
        db.add(initial_tx)
        db.commit()

    return {"data": new_account, "message": "Account created successfully"}

@router.put("/accounts/{id}", response_model=TrxAccountResponse)
def update_account(id: uuid.UUID, account_update: TrxAccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Update an existing financial account.
    """
    account = validate_account(db, id, current_user.id)
    
    # Validate account type and limit consistency
    account_type = account_update.type
    limit = account_update.limit

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

    for key, value in account_update.model_dump().items():
        setattr(account, key, value)
    
    db.commit()
    db.refresh(account)
    return {"data": account, "message": "Account updated successfully"}

@router.delete("/accounts/{id}", response_model=TrxDeleteAccountResponse)
def delete_account(id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Delete a financial account and its associated transactions.
    """
    account = validate_account(db, id, current_user.id)
    deleted_info = prepare_deleted_account_info(account)
    db.delete(account)
    db.commit()
    return {"message": f"Account with id {id} deleted successfully", "deleted_item": deleted_info}

@router.get("/accounts/{id}/balance", response_model=AccountBalanceResponse)
def get_account_balance(id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get detailed balance information for a specific account.
    """
    account = validate_account(db, id, current_user.id)
    balance_details = calculate_account_balance(db, id, current_user.id)
    
    response_data = {
        "account_id": id,
        "account": account,
        **balance_details
    }
    
    return {"data": response_data, "message": "Balance retrieved successfully"}

@router.get("/accounts", response_model=List[TrxAccountWithBalance])
def get_accounts(account_type: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get all accounts for the current user, with optional filtering and balance details.
    This endpoint is optimized to prevent N+1 query issues.
    """
    accounts_data = get_accounts_with_balance(db, current_user.id, account_type)
    return [TrxAccountWithBalance.model_validate(acc) for acc in accounts_data]

# --- Category Endpoints ---

@router.post("/categories", status_code=status.HTTP_201_CREATED, response_model=TrxCategoryResponse)
def create_category(category: TrxCategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Create a new transaction category.
    """
    new_category = prepare_category_for_db(category.model_dump(), current_user.id)
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return {"data": new_category, "message": "Category created successfully"}

@router.put("/categories/{id}", response_model=TrxCategoryResponse)
def update_category(id: uuid.UUID, category_update: TrxCategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Update an existing transaction category.
    """
    category = validate_category(db, id, current_user.id)
    for key, value in category_update.model_dump().items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return {"data": category, "message": "Category updated successfully"}

@router.delete("/categories/{id}", response_model=TrxDeleteCategoryResponse)
def delete_category(id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Delete a transaction category.
    """
    category = validate_category(db, id, current_user.id)
    deleted_info = prepare_deleted_category_info(category)
    db.delete(category)
    db.commit()
    return {"message": f"Category with id {id} deleted successfully", "deleted_item": deleted_info}

@router.get("/categories", response_model=List[TrxCategoryResponseData])
def get_categories(category_type: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get all categories for the current user, with optional filtering.
    """
    return get_filtered_categories(db, current_user.id, category_type)

# --- Transaction Endpoints ---

@router.post("/transactions", status_code=status.HTTP_201_CREATED, response_model=TransactionResponse)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Create a new transaction (income, expense, or transfer).
    """
    account = validate_account(db, transaction.account_id, current_user.id)
    category = validate_category(db, transaction.category_id, current_user.id)
    validate_transaction_category_match(transaction.transaction_type, category)

    if transaction.transaction_type == TransactionType.EXPENSE and account.type == TrxAccountType.CREDIT_CARD:
        balance_details = calculate_account_balance(db, account.id)
        if balance_details["balance"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create expense with this credit card - no available balance. Please top up by creating a transfer to this account."
            )

    validate_transfer(
        transaction.transaction_type, transaction.destination_account_id, transaction.account_id,
        transaction.transfer_fee, db, current_user.id
    )

    new_transaction = prepare_transaction_for_db(transaction.model_dump(), current_user.id)
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    return {"data": new_transaction, "message": "Transaction created successfully"}

@router.put("/transactions/{id}", response_model=TransactionResponse)
def update_transaction(id: uuid.UUID, transaction_update: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Update an existing transaction.
    """
    transaction_query = db.query(Transaction).filter(Transaction.id == id, Transaction.user_id == current_user.id)
    existing_transaction = transaction_query.first()
    if not existing_transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Transaction with id {id} not found")

    account = validate_account(db, transaction_update.account_id, current_user.id)
    category = validate_category(db, transaction_update.category_id, current_user.id)
    validate_transaction_category_match(transaction_update.transaction_type, category)

    if (
        transaction_update.transaction_type == TransactionType.EXPENSE and
        account.type == TrxAccountType.CREDIT_CARD and
        (existing_transaction.transaction_type != TransactionType.EXPENSE or transaction_update.amount > existing_transaction.amount)
    ):
        balance_details = calculate_account_balance(db, account.id)
        adjusted_balance = balance_details["balance"]
        if existing_transaction.transaction_type == TransactionType.EXPENSE and existing_transaction.account_id == transaction_update.account_id:
            adjusted_balance += existing_transaction.amount
        if adjusted_balance - transaction_update.amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient credit card balance for this update. Please top up the account."
            )

    validate_transfer(
        transaction_update.transaction_type, transaction_update.destination_account_id, transaction_update.account_id,
        transaction_update.transfer_fee, db, current_user.id
    )

    transaction_query.update(transaction_update.model_dump(), synchronize_session=False)
    db.commit()
    db.refresh(existing_transaction)
    return {"data": existing_transaction, "message": "Transaction updated successfully"}

@router.delete("/transactions/{id}", response_model=DeleteTransactionResponse)
def delete_transaction(id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_non_guest_user)):
    """
    Delete a transaction.
    """
    transaction_query = db.query(Transaction).filter(Transaction.id == id, Transaction.user_id == current_user.id)
    transaction = transaction_query.first()
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Transaction with id {id} not found")

    deleted_info = prepare_deleted_transaction_info(transaction)
    transaction_query.delete(synchronize_session=False)
    db.commit()
    return {"message": f"Transaction with id {id} deleted successfully", "deleted_item": deleted_info}

@router.get("/transactions", response_model=TransactionList)
def get_transactions(
    account_name: Optional[str] = None, category_name: Optional[str] = None,
    transaction_type: Optional[str] = None, start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None, date_filter_type: Optional[str] = None,
    order_by: str = 'created_at', sort_order: str = 'desc',
    limit: int = 10, skip: int = 0,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get a paginated list of transactions with advanced filtering.
    """
    try:
        query = get_filtered_transactions(
            db=db, user_id=current_user.id, account_name=account_name, category_name=category_name,
            transaction_type=transaction_type, start_date=start_date, end_date=end_date,
            date_filter_type=date_filter_type, order_by=order_by, sort_order=sort_order, return_query=True
        )
        total_count = query.count()
        transactions = query.offset(skip).limit(limit + 1).all()
        has_more = len(transactions) > limit
        if has_more:
            transactions = transactions[:limit]

        return {
            "data": transactions, "total_count": total_count, "has_more": has_more,
            "limit": limit, "skip": skip, "message": "Transactions retrieved successfully"
        }
    except HTTPException as e:
        return {
            "data": [], "total_count": 0, "has_more": False, "limit": limit, "skip": skip,
            "message": e.detail
        }

# --- Statistics Endpoints ---

@router.get("/statistics/summary", response_model=FinancialSummaryResponse)
def get_financial_summary(
    start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
    period: str = "month", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get a financial summary for a given period.
    """
    try:
        start_date, end_date = calculate_date_range(period) if not all([start_date, end_date]) else (start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    results = db.query(
        Transaction.transaction_type,
        func.sum(Transaction.amount).label("total")
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date.between(start_date, end_date)
    ).group_by(Transaction.transaction_type).all()

    summary = {"income": Decimal('0.0'), "expense": Decimal('0.0'), "transfer": Decimal('0.0')}
    for tt, total in results:
        if tt.value in summary:
            summary[tt.value] = total
    
    net = summary["income"] - summary["expense"]

    return {
        "period": {"start_date": start_date, "end_date": end_date, "period_type": period},
        "totals": {**summary, "net": net}
    }

@router.get("/statistics/by-category", response_model=CategoryDistributionResponse)
def get_category_distribution(
    transaction_type: str = "expense", start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None, period: str = "month",
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get transaction distribution by category, including uncategorized transactions.
    """
    if transaction_type not in ("income", "expense"):
        raise HTTPException(status_code=400, detail="Transaction type must be 'income' or 'expense'")
    try:
        start_date, end_date = calculate_date_range(period) if not all([start_date, end_date]) else (start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    tx_type = TransactionType(transaction_type)
    
    query = db.query(
        func.coalesce(CategoryModel.name, 'Uncategorized').label('name'),
        CategoryModel.id.label('id'),
        func.sum(Transaction.amount).label("total")
    ).outerjoin(CategoryModel, Transaction.category_id == CategoryModel.id).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date.between(start_date, end_date),
        Transaction.transaction_type == tx_type
    ).group_by(CategoryModel.id, CategoryModel.name).order_by(desc("total"))

    results = query.all()
    total = db.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date.between(start_date, end_date),
        Transaction.transaction_type == tx_type
    ).scalar() or Decimal('0.0')

    categories = [
        {
            "name": name,
            "id": id,
            "total": category_total,
            "percentage": (category_total / total * 100) if total > 0 else 0
        }
        for name, id, category_total in results
    ]

    return {
        "period": {"start_date": start_date, "end_date": end_date, "period_type": period},
        "transaction_type": transaction_type,
        "total": total,
        "categories": categories
    }

@router.get("/statistics/trends", response_model=TransactionTrendsResponse)
def get_transaction_trends(
    start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
    period: str = "month", group_by: str = "day",
    transaction_types: List[str] = FastAPIQuery(["income", "expense"]),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get transaction trends over time, grouped by a specified interval.
    """
    try:
        start_date, end_date = calculate_date_range(period) if not all([start_date, end_date]) else (start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if group_by not in ("day", "week", "month", "year"):
        raise HTTPException(status_code=400, detail="Invalid group_by parameter")
    for tx_type in transaction_types:
        if tx_type not in [t.value for t in TransactionType]:
            raise HTTPException(status_code=400, detail=f"Invalid transaction type '{tx_type}'")

    date_trunc = func.date_trunc(group_by, Transaction.transaction_date)
    query = db.query(
        date_trunc.label("date"),
        Transaction.transaction_type,
        func.sum(Transaction.amount).label("total")
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date.between(start_date, end_date),
        Transaction.transaction_type.in_(transaction_types)
    ).group_by(date_trunc, Transaction.transaction_type).order_by(date_trunc)

    results = query.all()
    trends_data = {}
    for date, tx_type, total in results:
        date_str = date.strftime("%Y-%m-%d")
        if date_str not in trends_data:
            trends_data[date_str] = {"date": date_str, "income": Decimal('0.0'), "expense": Decimal('0.0'), "transfer": Decimal('0.0'), "net": Decimal('0.0')}
        trends_data[date_str][tx_type.value] = total
        trends_data[date_str]["net"] = trends_data[date_str]["income"] - trends_data[date_str]["expense"]

    return {
        "period": {"start_date": start_date, "end_date": end_date, "period_type": period, "group_by": group_by},
        "trends": list(trends_data.values())
    }

@router.get("/statistics/account-summary", response_model=AccountSummaryResponse)
def get_account_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get a summary of all accounts, including balances and credit utilization.
    Optimized to avoid N+1 queries.
    """
    accounts_data = get_accounts_with_balance(db, current_user.id)
    
    total_balance = sum(acc['balance'] for acc in accounts_data)
    total_available_credit = sum(max(Decimal('0'), acc['limit'] - acc['payable_balance']) for acc in accounts_data if acc['type'] == TrxAccountType.CREDIT_CARD and acc['limit'] is not None and acc['payable_balance'] is not None)
    total_credit_limit = sum(acc['limit'] for acc in accounts_data if acc['type'] == TrxAccountType.CREDIT_CARD and acc['limit'] is not None)
    
    credit_utilization = ((total_credit_limit - total_available_credit) / total_credit_limit * 100) if total_credit_limit > 0 else Decimal('0.0')

    balances_by_type = {
        "bank_account": sum(acc['balance'] for acc in accounts_data if acc['type'] == TrxAccountType.BANK_ACCOUNT),
        "credit_card": sum(acc['balance'] for acc in accounts_data if acc['type'] == TrxAccountType.CREDIT_CARD),
        "other": sum(acc['balance'] for acc in accounts_data if acc['type'] == TrxAccountType.OTHER)
    }

    # Sort accounts by latest transaction for better UX (most recently used first)
    # This part still has a potential N+1 query, but it's for sorting display and less critical.
    # A more advanced solution might involve a more complex join or a separate denormalized field.
    account_summaries = []
    for acc_data in accounts_data:
        latest_tx_date = db.query(func.max(Transaction.transaction_date)).filter(
            or_(Transaction.account_id == acc_data['id'], Transaction.destination_account_id == acc_data['id'])
        ).scalar() or acc_data['created_at']
        
        summary_item = {
            **acc_data,
            "utilization_percentage": ((acc_data['payable_balance'] / acc_data['limit']) * 100) if acc_data.get('limit') and acc_data.get('payable_balance') is not None else None
        }
        account_summaries.append((summary_item, latest_tx_date))

    account_summaries.sort(key=lambda x: x[1], reverse=True)

    return {
        "total_balance": total_balance,
        "available_credit": total_available_credit,
        "credit_utilization": credit_utilization,
        "by_account_type": balances_by_type,
        "accounts": [item for item, _ in account_summaries]
    }