from pydantic import BaseModel, Field, UUID4
from typing import Optional
from datetime import datetime
from decimal import Decimal
from app.models.account import AccountType
from app.schemas.common import DeletedItemInfo, DeleteResponse

class AccountBase(BaseModel):
    name: str
    type: AccountType
    description: Optional[str] = None
    limit: Optional[Decimal] = None

class AccountCreate(AccountBase):
    pass

class Account(AccountBase):
    account_id: int
    uuid: UUID4
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AccountWithBalance(Account):
    balance: Decimal = Decimal('0.0')
    payable_balance: Optional[Decimal] = None
    total_income: Optional[Decimal] = None
    total_expenses: Optional[Decimal] = None
    total_transfers_in: Optional[Decimal] = None
    total_transfers_out: Optional[Decimal] = None
    total_transfer_fees: Optional[Decimal] = None

class AccountResponse(BaseModel):
    data: Account
    message: str = "Success"

class DeletedAccountInfo(DeletedItemInfo):
    """
    Schema for deleted account information
    """
    name: str = Field(..., description="Name of the deleted account")
    type: str = Field(..., description="Type of the deleted account")

class DeleteAccountResponse(DeleteResponse[DeletedAccountInfo]):
    """
    Schema for delete account response
    
    Example:
        {
            "message": "Account deleted successfully",
            "deleted_item": {
                "id": 1,
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "name": "My Bank Account",
                "type": "bank_account"
            }
        }
    """
    pass 