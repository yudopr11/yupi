from pydantic import BaseModel, Field
from typing import TypeVar, Generic
import uuid

T = TypeVar('T')

class DeletedItemInfo(BaseModel):
    """
    Base schema for deleted item information
    """
    id: uuid.UUID = Field(..., description="Universally unique identifier of the deleted item", example=uuid.uuid4())

class DeleteResponse(BaseModel, Generic[T]):
    """
    Generic response schema for delete operations
    """
    message: str = Field(..., description="Response message indicating the result of the delete operation", example="Item has been deleted successfully")
    deleted_item: T = Field(..., description="Details about the deleted item") 