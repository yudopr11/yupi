from pydantic import BaseModel, UUID4
from typing import TypeVar, Generic

T = TypeVar('T')

class DeletedItemInfo(BaseModel):
    id: int
    uuid: UUID4 | str

class DeleteResponse(BaseModel, Generic[T]):
    message: str
    deleted_item: T 