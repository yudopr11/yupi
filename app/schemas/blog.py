from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional, List
import uuid

class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="User ID")
    username: str = Field(..., description="User's username")
    email: EmailStr = Field(..., description="User's email address")

class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Post title")
    content: str = Field(..., min_length=1, description="Post content in Markdown format")
    published: bool = Field(False, description="Is the post published?")
    tags: Optional[List[str]] = Field(None, description="List of tags")
    excerpt: Optional[str] = Field(None, description="A short excerpt of the post")

class PostCreate(PostBase):
    pass

class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID = Field(..., description="Post ID")
    slug: str = Field(..., description="URL-friendly slug")
    reading_time: int = Field(..., description="Estimated reading time in minutes")
    created_at: datetime = Field(..., description="Post creation timestamp")
    updated_at: datetime = Field(..., description="Post last update timestamp")
    author: "UserBase" = Field(..., alias="user")

class PostListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID = Field(..., description="Post ID")
    title: str = Field(..., description="Post title")
    slug: str = Field(..., description="URL-friendly slug")
    excerpt: Optional[str] = Field(None, description="A short excerpt of the post")
    tags: Optional[List[str]] = Field(None, description="List of tags")
    reading_time: int = Field(..., description="Estimated reading time in minutes")
    published: bool = Field(False, description="Is the post published?")
    created_at: datetime = Field(..., description="Post creation timestamp")
    updated_at: datetime = Field(..., description="Post last update timestamp")
    author: "UserBase" = Field(..., alias="user")

class PaginatedPostsResponse(BaseModel):
    items: List[PostListResponse]
    total_count: int
    has_more: bool
    limit: int
    skip: int
    next_cursor: Optional[str] = None
