from pydantic import BaseModel, UUID4, Field
from typing import TypeVar, Generic

T = TypeVar('T')

class DeletedItemInfo(BaseModel):
    """
    Base schema for deleted item information
    """
    id: int = Field(..., description="Numeric identifier of the deleted item", example=1)
    uuid: UUID4 | str = Field(..., description="Universally unique identifier of the deleted item", example="123e4567-e89b-12d3-a456-426614174000")

class DeleteResponse(BaseModel, Generic[T]):
    """
    Generic response schema for delete operations
    """
    message: str = Field(..., description="Response message indicating the result of the delete operation", example="Item has been deleted successfully")
    deleted_item: T = Field(..., description="Details about the deleted item") 