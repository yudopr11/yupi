from pydantic import BaseModel, Field, UUID4
from typing import Optional
from datetime import datetime
from app.models.category import CategoryType
from app.schemas.common import DeletedItemInfo, DeleteResponse

class CategoryBase(BaseModel):
    name: str
    type: CategoryType

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    category_id: int
    uuid: UUID4
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CategoryResponse(BaseModel):
    data: Category
    message: str = "Success"

class DeletedCategoryInfo(DeletedItemInfo):
    """
    Schema for deleted category information
    """
    name: str = Field(..., description="Name of the deleted category")
    type: str = Field(..., description="Type of the deleted category")

class DeleteCategoryResponse(DeleteResponse[DeletedCategoryInfo]):
    """
    Schema for delete category response
    
    Example:
        {
            "message": "Category deleted successfully",
            "deleted_item": {
                "id": 1,
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Salary",
                "type": "income"
            }
        }
    """
    pass 