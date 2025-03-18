from pydantic import BaseModel, Field, UUID4
from datetime import datetime
from app.models.category import TrxCategoryType
from app.schemas.common import DeletedItemInfo, DeleteResponse

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

class TrxCategory(TrxCategoryBase):
    """
    Schema for transaction category with additional fields
    """
    category_id: int = Field(..., description="Unique identifier for the category", example=1)
    uuid: UUID4 = Field(..., description="Universally unique identifier for the category", example="123e4567-e89b-12d3-a456-426614174000")
    user_id: int = Field(..., description="ID of the user who owns this category", example=1)
    created_at: datetime = Field(..., description="Timestamp when the category was created")
    updated_at: datetime = Field(..., description="Timestamp when the category was last updated")

    class Config:
        from_attributes = True

class TrxCategoryResponse(BaseModel):
    """
    Schema for category response
    """
    data: TrxCategory = Field(..., description="Category data")
    message: str = Field(default="Success", description="Response message")

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