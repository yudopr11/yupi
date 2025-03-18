from pydantic import BaseModel, Field, UUID4
from typing import Optional
from datetime import datetime
from decimal import Decimal
from app.models.account import TrxAccountType
from app.schemas.common import DeletedItemInfo, DeleteResponse

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

class TrxAccount(TrxAccountBase):
    """
    Schema for transaction account with additional fields
    """
    account_id: int = Field(..., description="Unique identifier for the account", example=1)
    uuid: UUID4 = Field(..., description="Universally unique identifier for the account", example="123e4567-e89b-12d3-a456-426614174000")
    user_id: int = Field(..., description="ID of the user who owns this account", example=1)
    created_at: datetime = Field(..., description="Timestamp when the account was created")
    updated_at: datetime = Field(..., description="Timestamp when the account was last updated")

    class Config:
        from_attributes = True

class TrxAccountWithBalance(TrxAccount):
    """
    Schema for transaction account with balance information
    """
    balance: Decimal = Field(Decimal('0.0'), description="Current balance of the account", example="1000.00")
    payable_balance: Optional[Decimal] = Field(None, description="Payable balance for credit cards", example="500.00")
    total_income: Optional[Decimal] = Field(None, description="Total income transactions for the account", example="2000.00")
    total_expenses: Optional[Decimal] = Field(None, description="Total expense transactions for the account", example="1500.00")
    total_transfers_in: Optional[Decimal] = Field(None, description="Total amount received from transfers", example="500.00")
    total_transfers_out: Optional[Decimal] = Field(None, description="Total amount sent in transfers", example="300.00")
    total_transfer_fees: Optional[Decimal] = Field(None, description="Total fees paid for transfers", example="5.00")

class TrxAccountResponse(BaseModel):
    """
    Schema for account response
    """
    data: TrxAccount = Field(..., description="Account data")
    message: str = Field(default="Success", description="Response message")

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