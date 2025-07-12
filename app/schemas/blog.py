from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List
from .common import DeletedItemInfo, DeleteResponse
from app.schemas.auth import UserBase
import uuid

class UserBase(BaseModel):
    """
    Base schema for user information
    """
    id: uuid.UUID = Field(..., description="User ID", example=uuid.uuid4())
    username: str = Field(..., description="User's username", example="johndoe")
    email: EmailStr = Field(..., description="User's email address", example="john@example.com")
    
    class Config:
        from_attributes = True

class PostBase(BaseModel):
    title: str = Field(..., description="Post title", example="My First Post")
    content: str = Field(..., description="Post content in Markdown format")
    published: bool = Field(False, description="Is the post published?")
    tags: Optional[List[str]] = Field(None, description="List of tags")
    excerpt: Optional[str] = Field(None, description="A short excerpt of the post")

class PostCreate(PostBase):
    pass

class PostResponse(PostBase):
    id: uuid.UUID = Field(..., description="Post ID", example=uuid.uuid4())
    slug: str = Field(..., description="URL-friendly slug")
    reading_time: int = Field(..., description="Estimated reading time in minutes")
    created_at: datetime = Field(..., description="Post creation timestamp")
    updated_at: datetime = Field(..., description="Post last update timestamp")
    author: "UserBase"

    class Config:
        from_attributes = True

class PostListResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Post ID", example=uuid.uuid4())
    title: str = Field(..., description="Post title", example="My First Post")
    slug: str = Field(..., description="URL-friendly slug")
    excerpt: Optional[str] = Field(None, description="A short excerpt of the post")
    tags: Optional[List[str]] = Field(None, description="List of tags")
    reading_time: int = Field(..., description="Estimated reading time in minutes")
    published: bool = Field(False, description="Is the post published?")
    created_at: datetime = Field(..., description="Post creation timestamp")
    updated_at: datetime = Field(..., description="Post last update timestamp")
    author: "UserBase"

    class Config:
        from_attributes = True

class PaginatedPostsResponse(BaseModel):
    items: List[PostListResponse]
    total_count: int
    has_more: bool
    limit: int
    skip: int

