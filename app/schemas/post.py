from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from .common import DeletedItemInfo, DeleteResponse

class PostBase(BaseModel):
    """
    Base schema for blog posts with common fields
    """
    title: str = Field(..., description="Post title", example="My First Blog Post")
    excerpt: str = Field(..., description="Short summary of the post", example="A brief introduction to my blog post")
    reading_time: int = Field(..., description="Estimated reading time in minutes", example=5)
    tags: Optional[List[str]] = Field(default=[], description="List of post tags", example=["tech", "programming"])

class PostCreate(BaseModel):
    """
    Schema for creating a new blog post
    """
    title: str = Field(..., description="Post title", example="My First Blog Post")
    excerpt: str = Field(..., description="Short summary of the post", example="A brief introduction to my blog post")
    content: str = Field(..., description="Full post content in markdown format", example="# Introduction\n\nThis is my first blog post...")
    tags: Optional[List[str]] = Field(default=[], description="List of post tags", example=["tech", "programming"])
    published: bool = Field(default=False, description="Whether the post is published", example=False)

class PostResponse(PostCreate):
    """
    Schema for post response with additional fields
    """
    id: int = Field(..., description="Post ID", example=1)
    uuid: UUID = Field(..., description="Unique identifier", example="123e4567-e89b-12d3-a456-426614174000")
    slug: str = Field(..., description="URL-friendly version of the title", example="my-first-blog-post")
    reading_time: int = Field(..., description="Estimated reading time in minutes", example=5)
    created_at: datetime = Field(..., description="Post creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True

class PostList(PostBase):
    """
    Schema for listing posts with minimal information
    """
    id: int = Field(..., description="Post ID", example=1)
    uuid: UUID = Field(..., description="Unique identifier", example="123e4567-e89b-12d3-a456-426614174000")
    slug: str = Field(..., description="URL-friendly version of the title", example="my-first-blog-post")
    published: bool = Field(..., description="Whether the post is published", example=True)

    class Config:
        from_attributes = True

class DeletedPostInfo(DeletedItemInfo):
    """
    Schema for deleted post information
    """
    title: str = Field(..., description="Title of the deleted post", example="My First Blog Post")

class DeletePostResponse(DeleteResponse[DeletedPostInfo]):
    """
    Schema for delete post response
    
    Example:
        {
            "message": "Post has been deleted successfully",
            "deleted_post": {
                "id": 1,
                "title": "My First Blog Post",
                "uuid": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    """
    pass 