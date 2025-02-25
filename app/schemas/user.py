from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from uuid import UUID
from .common import DeletedItemInfo, DeleteResponse

class UserBase(BaseModel):
    """
    Base schema for user with common fields
    """
    username: str = Field(..., description="Username for login", example="johndoe")
    email: EmailStr = Field(..., description="User's email address", example="john@example.com")

class UserCreate(UserBase):
    """
    Schema for creating a new user
    """
    password: str = Field(..., description="User's password", example="strongpassword123")
    is_superuser: bool = Field(default=False, description="Whether user has superuser privileges", example=False)

class UserResponse(UserBase):
    """
    Schema for user response with additional fields
    """
    id: int = Field(..., description="User ID", example=1)
    uuid: UUID = Field(..., description="Unique identifier", example="123e4567-e89b-12d3-a456-426614174000")
    is_superuser: bool = Field(..., description="Whether user has superuser privileges", example=False)
    created_at: datetime = Field(..., description="Account creation timestamp")

    class Config:
        from_attributes = True

class TokenData(BaseModel):
    """
    Schema for token payload data
    """
    username: Optional[str] = Field(default=None, description="Username stored in token")

class Token(BaseModel):
    """
    Schema for authentication token response
    
    Example:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
    """
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(..., description="Token type (always 'bearer')", example="bearer")

class TokenPayload(BaseModel):
    """
    Schema for token payload data
    """
    sub: str = Field(..., description="Subject of the token")
    exp: int = Field(..., description="Expiration time of the token")
    type: str = Field(..., description="Type of the token")

class DeletedUserInfo(DeletedItemInfo):
    """
    Schema for deleted user information
    """
    username: str = Field(..., description="Username of the deleted user", example="johndoe")

class DeleteUserResponse(DeleteResponse[DeletedUserInfo]):
    """
    Schema for delete user response
    
    Example:
        {
            "message": "User has been deleted successfully",
            "deleted_user": {
                "id": 1,
                "username": "johndoe",
                "uuid": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    """
    pass 