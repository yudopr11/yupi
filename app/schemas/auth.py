from pydantic import BaseModel, ConfigDict, EmailStr, Field
import uuid
from datetime import datetime
from typing import Optional
from .common import DeletedItemInfo, DeleteResponse

class UserBase(BaseModel):
    username: str = Field(..., description="Username for login")
    email: EmailStr = Field(..., description="User's email address")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User's password")
    is_superuser: bool = Field(default=False, description="Whether user has superuser privileges")

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="User ID")
    is_superuser: bool = Field(..., description="Whether user has superuser privileges")
    created_at: datetime = Field(..., description="Account creation timestamp")

class TokenData(BaseModel):
    username: Optional[str] = Field(default=None, description="Username stored in token")

class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(..., description="Token type (always 'bearer')")

class TokenPayload(BaseModel):
    sub: str = Field(..., description="Subject of the token")
    exp: int = Field(..., description="Expiration time of the token")
    type: str = Field(..., description="Type of the token")

class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address to send reset link to")

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Password reset token received in email")
    new_password: str = Field(..., min_length=8, description="New password")

class ForgotPasswordResponse(BaseModel):
    message: str = Field(..., description="Response message")

class ResetPasswordResponse(BaseModel):
    message: str = Field(..., description="Response message")

class DeletedUserInfo(DeletedItemInfo):
    username: str = Field(..., description="Username of the deleted user")

class DeleteUserResponse(DeleteResponse[DeletedUserInfo]):
    pass
