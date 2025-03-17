from pydantic import BaseModel, Field, UUID4
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.models.transaction import TransactionType
from app.schemas.account import TrxAccount
from app.schemas.category import TrxCategory
from app.schemas.common import DeletedItemInfo, DeleteResponse

class TransactionBase(BaseModel):
    transaction_date: datetime
    description: str
    amount: Decimal
    transaction_type: TransactionType
    account_id: int
    category_id: Optional[int] = None
    destination_account_id: Optional[int] = None
    transfer_fee: Optional[Decimal] = Field(default=Decimal('0.0'), description="Transfer fee amount, only applicable for transfer transactions")

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    transaction_id: int
    uuid: UUID4
    user_id: int
    account: TrxAccount
    category: Optional[TrxCategory] = None
    destination_account: Optional[TrxAccount] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TransactionResponse(BaseModel):
    data: Transaction
    message: str = "Success"

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
    
    Example:
        {
            "message": "Transaction deleted successfully",
            "deleted_item": {
                "id": 1,
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "description": "Monthly salary",
                "amount": 5000.0,
                "transaction_type": "income"
            }
        }
    """
    pass

class AccountBalance(BaseModel):
    account_id: int
    balance: Decimal
    total_income: Decimal
    total_expenses: Decimal
    total_transfers_in: Decimal
    total_transfers_out: Decimal
    total_transfer_fees: Decimal
    account: TrxAccount

class AccountBalanceResponse(BaseModel):
    data: AccountBalance
    message: str = "Success"

class TransactionList(BaseModel):
    """
    Schema for a list of transactions with pagination metadata
    """
    data: List[Transaction]
    total_count: int
    has_more: bool = False
    limit: int
    skip: int
    message: str = "Success"

