from pydantic import BaseModel, Field, UUID4
from datetime import datetime
from app.models.category import TrxCategoryType
from app.schemas.common import DeletedItemInfo, DeleteResponse

class TrxCategoryBase(BaseModel):
    name: str
    type: TrxCategoryType

class TrxCategoryCreate(TrxCategoryBase):
    pass

class TrxCategory(TrxCategoryBase):
    category_id: int
    uuid: UUID4
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TrxCategoryResponse(BaseModel):
    data: TrxCategory
    message: str = "Success"

class TrxDeletedCategoryInfo(DeletedItemInfo):
    """
    Schema for deleted category information
    """
    name: str = Field(..., description="Name of the deleted category")
    type: str = Field(..., description="Type of the deleted category")

class TrxDeleteCategoryResponse(DeleteResponse[TrxDeletedCategoryInfo]):
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