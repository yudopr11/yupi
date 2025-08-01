from pydantic import BaseModel, EmailStr, Field
import uuid
from datetime import datetime
from typing import Optional
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
    id: uuid.UUID = Field(..., description="User ID", example=uuid.uuid4())
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

class ForgotPasswordRequest(BaseModel):
    """
    Schema for requesting a password reset
    """
    email: EmailStr = Field(..., description="Email address to send reset link to", example="user@example.com")

class ResetPasswordRequest(BaseModel):
    """
    Schema for resetting password with token
    """
    token: str = Field(..., description="Password reset token received in email")
    new_password: str = Field(..., description="New password", example="newStrongPassword123")

class ForgotPasswordResponse(BaseModel):
    """
    Schema for forgot password response
    """
    message: str = Field(..., description="Response message", example="If the email exists in our system, a reset token will be sent.")

class ResetPasswordResponse(BaseModel):
    """
    Schema for reset password response
    """
    message: str = Field(..., description="Response message", example="Password has been reset successfully")

class DeletedUserInfo(DeletedItemInfo):
    """
    Schema for deleted user information
    """
    username: str = Field(..., description="Username of the deleted user", example="johndoe")

class DeleteUserResponse(DeleteResponse[DeletedUserInfo]):
    """
    Schema for delete user response
    """
    pass 