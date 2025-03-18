from pydantic import BaseModel, Field, UUID4
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.models.transaction import TransactionType
from app.schemas.account import TrxAccount
from app.schemas.category import TrxCategory
from app.schemas.common import DeletedItemInfo, DeleteResponse

class TransactionBase(BaseModel):
    """
    Base schema for transaction with common fields
    """
    transaction_date: datetime = Field(..., description="Date and time when the transaction occurred")
    description: str = Field(..., description="Description or note about the transaction", example="Grocery shopping at Walmart")
    amount: Decimal = Field(..., description="Transaction amount", example="50.25")
    transaction_type: TransactionType = Field(..., description="Type of transaction (income, expense, or transfer)")
    account_id: int = Field(..., description="ID of the account where the transaction occurred")
    category_id: Optional[int] = Field(None, description="ID of the category for the transaction (optional)")
    destination_account_id: Optional[int] = Field(None, description="ID of the destination account for transfer transactions (optional)")
    transfer_fee: Optional[Decimal] = Field(default=Decimal('0.0'), description="Transfer fee amount, only applicable for transfer transactions")

class TransactionCreate(TransactionBase):
    """
    Schema for creating a new transaction
    """
    pass

class Transaction(TransactionBase):
    """
    Schema for transaction with additional fields
    """
    transaction_id: int = Field(..., description="Unique identifier for the transaction")
    uuid: UUID4 = Field(..., description="Universally unique identifier for the transaction")
    user_id: int = Field(..., description="ID of the user who owns this transaction")
    account: TrxAccount = Field(..., description="Account details where the transaction occurred")
    category: Optional[TrxCategory] = Field(None, description="Category details for the transaction (optional)")
    destination_account: Optional[TrxAccount] = Field(None, description="Destination account details for transfer transactions (optional)")
    created_at: datetime = Field(..., description="Timestamp when the transaction was created")
    updated_at: datetime = Field(..., description="Timestamp when the transaction was last updated")

    class Config:
        from_attributes = True

class TransactionResponse(BaseModel):
    """
    Schema for transaction response
    """
    data: Transaction = Field(..., description="Transaction data")
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
    account_id: int = Field(..., description="ID of the account")
    balance: Decimal = Field(..., description="Current balance of the account")
    total_income: Decimal = Field(..., description="Total income transactions for the account")
    total_expenses: Decimal = Field(..., description="Total expense transactions for the account")
    total_transfers_in: Decimal = Field(..., description="Total amount received from transfers")
    total_transfers_out: Decimal = Field(..., description="Total amount sent in transfers")
    total_transfer_fees: Decimal = Field(..., description="Total fees paid for transfers")
    account: TrxAccount = Field(..., description="Account details")

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
    data: List[Transaction] = Field(..., description="List of transactions")
    total_count: int = Field(..., description="Total number of transactions")
    has_more: bool = Field(default=False, description="Whether there are more transactions to load")
    limit: int = Field(..., description="Maximum number of transactions per page")
    skip: int = Field(..., description="Number of transactions skipped")
    message: str = Field(default="Success", description="Response message")

