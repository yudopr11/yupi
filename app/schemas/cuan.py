from pydantic import BaseModel, Field
from typing import Optional, List, TypeVar, Generic
from datetime import datetime
from decimal import Decimal
import uuid

from app.models.cuan import TrxAccountType, TrxCategoryType, TransactionType, TrxAccount, TrxCategory
from app.schemas.common import DeletedItemInfo, DeleteResponse

# Generic TypeVar for DeleteResponse
T = TypeVar('T')

# --- Account Schemas ---
class TrxAccountBase(BaseModel):
    """
    Base schema for transaction account with common fields
    """
    name: str = Field(..., description="Name of the account", example="My Bank Account")
    type: TrxAccountType = Field(..., description="Type of the account (bank_account, credit_card, other)")
    description: Optional[str] = Field(None, description="Optional description of the account", example="Main checking account")
    limit: Optional[Decimal] = Field(None, description="Credit limit for credit card accounts", example="5000.00")

class TrxAccountCreate(TrxAccountBase):
    """
    Schema for creating a new transaction account
    """
    pass

class TrxAccountResponseData(TrxAccountBase):
    id: uuid.UUID = Field(..., description="Unique identifier for the account", example=uuid.uuid4())
    user_id: uuid.UUID = Field(..., description="ID of the user who owns this account", example=uuid.uuid4())
    created_at: datetime = Field(..., description="Timestamp when the account was created")
    updated_at: datetime = Field(..., description="Timestamp when the account was last updated")

    class Config:
        from_attributes = True

class TrxAccountResponse(BaseModel):
    data: TrxAccountResponseData
    message: str

class TrxAccountWithBalance(TrxAccountResponseData):
    balance: Decimal = Field(..., description="Current balance of the account")
    total_income: Decimal = Field(..., description="Total income for the account")
    total_expenses: Decimal = Field(..., description="Total expenses for the account")
    total_transfers_in: Decimal = Field(..., description="Total transfers in for the account")
    total_transfers_out: Decimal = Field(..., description="Total transfers out for the account")
    total_transfer_fees: Decimal = Field(..., description="Total transfer fees for the account")
    payable_balance: Optional[Decimal] = Field(None, description="Payable balance for credit card accounts")

class TrxDeletedAccountInfo(DeletedItemInfo):
    """
    Schema for deleted account information
    """
    name: str = Field(..., description="Name of the deleted account", example="My Bank Account")
    type: str = Field(..., description="Type of the deleted account", example="bank_account")

class TrxDeleteAccountResponse(DeleteResponse[TrxDeletedAccountInfo]):
    """
    Schema for delete account response
    """
    pass

# --- Category Schemas ---
class TrxCategoryBase(BaseModel):
    """
    Base schema for transaction category with common fields
    """
    name: str = Field(..., description="Name of the category", example="Salary")
    type: TrxCategoryType = Field(..., description="Type of the category (income, expense, or transfer)")

class TrxCategoryCreate(TrxCategoryBase):
    """
    Schema for creating a new transaction category
    
    This schema is used when creating a new category in the system.
    It inherits the base fields from TrxCategoryBase.
    """
    pass

class TrxCategoryResponseData(TrxCategoryBase):
    id: uuid.UUID = Field(..., description="Unique identifier for the category", example=uuid.uuid4())
    user_id: uuid.UUID = Field(..., description="ID of the user who owns this category", example=uuid.uuid4())
    created_at: datetime = Field(..., description="Timestamp when the category was created")
    updated_at: datetime = Field(..., description="Timestamp when the category was last updated")

    class Config:
        from_attributes = True

class TrxCategoryResponse(BaseModel):
    data: TrxCategoryResponseData
    message: str

class TrxDeletedCategoryInfo(DeletedItemInfo):
    """
    Schema for deleted category information
    """
    name: str = Field(..., description="Name of the deleted category", example="Salary")
    type: str = Field(..., description="Type of the deleted category", example="income")

class TrxDeleteCategoryResponse(DeleteResponse[TrxDeletedCategoryInfo]):
    """
    Schema for delete category response
    """
    pass

# --- Transaction Schemas ---
class TransactionBase(BaseModel):
    """
    Base schema for transaction with common fields
    """
    transaction_date: datetime = Field(..., description="Date and time when the transaction occurred")
    description: str = Field(..., description="Description or note about the transaction", example="Grocery shopping at Walmart")
    amount: Decimal = Field(..., description="Transaction amount", example="50.25")
    transaction_type: TransactionType = Field(..., description="Type of transaction (income, expense, or transfer)")
    account_id: uuid.UUID = Field(..., description="ID of the account where the transaction occurred")
    category_id: Optional[uuid.UUID] = Field(None, description="ID of the category for the transaction (optional)")
    destination_account_id: Optional[uuid.UUID] = Field(None, description="ID of the destination account for transfer transactions (optional)")
    transfer_fee: Optional[Decimal] = Field(default=Decimal('0.0'), description="Transfer fee amount, only applicable for transfer transactions")

class TransactionCreate(TransactionBase):
    """
    Schema for creating a new transaction
    """
    pass

class TransactionResponseData(TransactionBase):
    id: uuid.UUID = Field(..., description="Unique identifier for the transaction")
    user_id: uuid.UUID = Field(..., description="ID of the user who owns this transaction")
    account: TrxAccountResponseData = Field(..., description="Account details where the transaction occurred")
    category: Optional[TrxCategoryResponseData] = Field(None, description="Category details for the transaction (optional)")
    destination_account: Optional[TrxAccountResponseData] = Field(None, description="Destination account details for transfer transactions (optional)")
    created_at: datetime = Field(..., description="Timestamp when the transaction was created")
    updated_at: datetime = Field(..., description="Timestamp when the transaction was last updated")

    class Config:
        from_attributes = True

class TransactionResponse(BaseModel):
    """
    Schema for transaction response
    """
    data: TransactionResponseData = Field(..., description="Transaction data")
    message: str = Field(default="Success", description="Response message")

class DeletedTransactionInfo(DeletedItemInfo):
    """
    Schema for deleted transaction information
    """
    description: str = Field(..., description="Description of the deleted transaction")
    amount: Decimal = Field(..., description="Amount of the deleted transaction")
    transaction_type: str = Field(..., description="Type of the deleted transaction")

class DeleteTransactionResponse(DeleteResponse[DeletedTransactionInfo]):
    """
    Schema for delete transaction response
    """
    pass

class AccountBalance(BaseModel):
    """
    Schema for account balance information
    """
    account_id: uuid.UUID = Field(..., description="ID of the account")
    balance: Decimal = Field(..., description="Current balance of the account")
    total_income: Decimal = Field(..., description="Total income transactions for the account")
    total_expenses: Decimal = Field(..., description="Total expense transactions for the account")
    total_transfers_in: Decimal = Field(..., description="Total amount received from transfers")
    total_transfers_out: Decimal = Field(..., description="Total amount sent in transfers")
    total_transfer_fees: Decimal = Field(..., description="Total fees paid for transfers")
    account: TrxAccountResponseData = Field(..., description="Account details")

class AccountBalanceResponse(BaseModel):
    """
    Schema for account balance response
    """
    data: AccountBalance = Field(..., description="Account balance data")
    message: str = Field(default="Success", description="Response message")

class TransactionList(BaseModel):
    """
    Schema for list of transactions with pagination
    """
    data: List[TransactionResponseData] = Field(..., description="List of transactions")
    total_count: int = Field(..., description="Total number of transactions")
    has_more: bool = Field(default=False, description="Whether there are more transactions to load")
    limit: int = Field(..., description="Maximum number of transactions per page")
    skip: int = Field(..., description="Number of transactions skipped")
    message: str = Field(default="Success", description="Response message")

# --- Statistics Schemas ---
class PeriodInfo(BaseModel):
    """
    Schema for period information used in statistics
    """
    start_date: datetime = Field(..., description="Start date of the period")
    end_date: datetime = Field(..., description="End date of the period")
    period_type: str = Field(..., description="Type of period (day, week, month, year, all)")

class FinancialTotals(BaseModel):
    """
    Schema for financial totals in a given period
    """
    income: Decimal = Field(Decimal('0.0'), description="Total income in the period")
    expense: Decimal = Field(Decimal('0.0'), description="Total expenses in the period")
    transfer: Decimal = Field(Decimal('0.0'), description="Total transfers in the period")
    net: Decimal = Field(Decimal('0.0'), description="Net balance (income - expense)")

class FinancialSummaryResponse(BaseModel):
    """
    Schema for financial summary response including period and totals
    """
    period: PeriodInfo = Field(..., description="Period information for the summary")
    totals: FinancialTotals = Field(..., description="Financial totals for the period")

class CategoryDistributionItem(BaseModel):
    """
    Schema for individual category distribution item
    """
    name: str = Field(..., description="Category name")
    id: Optional[uuid.UUID] = Field(None, description="Category UUID. Will be null for 'Uncategorized' transactions.")
    total: Decimal = Field(..., description="Total amount for this category")
    percentage: Optional[Decimal] = Field(None, description="Percentage of total (0-100)")

class CategoryDistributionResponse(BaseModel):
    """
    Schema for category distribution response showing how transactions are distributed across categories
    """
    period: PeriodInfo = Field(..., description="Period information for the distribution")
    transaction_type: str = Field(..., description="Type of transactions analyzed (income, expense, or transfer)")
    total: Decimal = Field(..., description="Total amount for all categories")
    categories: List[CategoryDistributionItem] = Field(..., description="List of categories with their distribution")

class TrendPeriodInfo(PeriodInfo):
    """
    Schema for trend period information with grouping level
    """
    group_by: str = Field(..., description="Grouping level (day, week, month, year)")

class TrendDataPoint(BaseModel):
    """
    Schema for a single data point in trends
    """
    date: str = Field(..., description="Date string in YYYY-MM-DD format")
    income: Decimal = Field(Decimal('0.0'), description="Income amount for this date")
    expense: Decimal = Field(Decimal('0.0'), description="Expense amount for this date")
    transfer: Decimal = Field(Decimal('0.0'), description="Transfer amount for this date")
    net: Decimal = Field(Decimal('0.0'), description="Net amount (income - expense)")

class TransactionTrendsResponse(BaseModel):
    """
    Schema for transaction trends response showing financial data over time
    """
    period: TrendPeriodInfo = Field(..., description="Period information with grouping level")
    trends: List[TrendDataPoint] = Field(..., description="List of data points showing trends over time")

class AccountTypeBalances(BaseModel):
    """
    Schema for account balances grouped by account type
    """
    bank_account: Decimal = Field(Decimal('0.0'), description="Total balance in bank accounts")
    credit_card: Decimal = Field(Decimal('0.0'), description="Total balance in credit cards")
    other: Decimal = Field(Decimal('0.0'), description="Total balance in other accounts")

class AccountSummaryItem(BaseModel):
    """
    Schema for individual account summary item
    """
    id: uuid.UUID = Field(..., description="Account ID")
    name: str = Field(..., description="Account name")
    type: str = Field(..., description="Account type (bank_account, credit_card, other)")
    balance: Decimal = Field(..., description="Current balance")
    payable_balance: Optional[Decimal] = Field(None, description="Payable balance (for credit cards)")
    limit: Optional[Decimal] = Field(None, description="Credit limit (for credit cards)")
    utilization_percentage: Optional[Decimal] = Field(None, description="Credit utilization percentage (for credit cards)")

class AccountSummaryResponse(BaseModel):
    """
    Schema for account summary response showing overall financial position
    """
    total_balance: Decimal = Field(..., description="Total balance across all accounts")
    available_credit: Decimal = Field(..., description="Available credit across all credit cards")
    credit_utilization: Decimal = Field(..., description="Overall credit utilization percentage")
    by_account_type: AccountTypeBalances = Field(..., description="Balances grouped by account type")
    accounts: List[AccountSummaryItem] = Field(..., description="List of accounts with balance details")
