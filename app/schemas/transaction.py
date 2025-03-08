from pydantic import BaseModel, Field, UUID4
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.models.transaction import TransactionType
from app.schemas.account import Account
from app.schemas.category import Category
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
    account: Account
    category: Optional[Category] = None
    destination_account: Optional[Account] = None
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
    account: Account

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

class BulkTransactionError(BaseModel):
    """
    Schema for error information in bulk transaction operations
    """
    index: int = Field(..., description="Index of the transaction in the input array")
    description: str = Field(..., description="Description of the transaction that failed")
    error: str = Field(..., description="Error message describing why the transaction failed")

class BulkTransactionResponse(BaseModel):
    """
    Schema for bulk transaction creation response
    
    Example:
        {
            "success_count": 2,
            "error_count": 1,
            "created_transactions": [
                {
                    "transaction_id": 1,
                    "uuid": "123e4567-e89b-12d3-a456-426614174000",
                    "transaction_date": "2023-01-15T12:00:00Z",
                    "description": "Salary",
                    "amount": 5000.0,
                    "transaction_type": "income",
                    "account_id": 1,
                    "user_id": 1,
                    "created_at": "2023-01-15T12:05:00Z",
                    "updated_at": "2023-01-15T12:05:00Z"
                },
                {
                    "transaction_id": 2,
                    "uuid": "123e4567-e89b-12d3-a456-426614174001",
                    "transaction_date": "2023-01-15T12:10:00Z",
                    "description": "Groceries",
                    "amount": 100.0,
                    "transaction_type": "expense",
                    "account_id": 1,
                    "category_id": 1,
                    "user_id": 1,
                    "created_at": "2023-01-15T12:15:00Z",
                    "updated_at": "2023-01-15T12:15:00Z"
                }
            ],
            "errors": [
                {
                    "index": 2,
                    "description": "Invalid Transaction",
                    "error": "Account not found"
                }
            ]
        }
    """
    success_count: int = Field(..., description="Number of transactions successfully created")
    error_count: int = Field(..., description="Number of transactions that failed to create")
    created_transactions: List[Transaction] = Field(..., description="List of successfully created transactions")
    errors: List[BulkTransactionError] = Field(..., description="List of errors for failed transactions")

class BulkCategoryError(BaseModel):
    """
    Schema for error information in bulk category assignment
    """
    transaction_id: int = Field(..., description="ID of the transaction that failed categorization")
    error: str = Field(..., description="Error message describing why the categorization failed")

class BulkCategorizeResponse(BaseModel):
    """
    Schema for bulk categorize response
    
    Example:
        {
            "success_count": 2,
            "error_count": 1,
            "updated_transaction_ids": [1, 2],
            "errors": [
                {
                    "transaction_id": 3,
                    "error": "Income transaction cannot be assigned to expense category"
                }
            ],
            "message": "Successfully updated 2 transaction(s)"
        }
    """
    success_count: int = Field(..., description="Number of transactions successfully updated")
    error_count: int = Field(..., description="Number of transactions that failed to update")
    updated_transaction_ids: List[int] = Field(..., description="List of IDs of successfully updated transactions")
    errors: List[BulkCategoryError] = Field(..., description="List of errors for failed updates")
    message: str = Field(..., description="Success message") 