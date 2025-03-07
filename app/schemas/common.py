from pydantic import BaseModel
from typing import TypeVar, Generic
from uuid import UUID

T = TypeVar('T')

class DeletedItemInfo(BaseModel):
    id: int
    uuid: UUID | str

class DeleteResponse(BaseModel, Generic[T]):
    message: str
    deleted_item: T 