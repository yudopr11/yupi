from pydantic import BaseModel, Field
from typing import TypeVar, Generic
import uuid

T = TypeVar('T')

class DeletedItemInfo(BaseModel):
    id: uuid.UUID = Field(..., description="Universally unique identifier of the deleted item")

class DeleteResponse(BaseModel, Generic[T]):
    message: str = Field(..., description="Response message indicating the result of the delete operation")
    deleted_item: T = Field(..., description="Details about the deleted item")