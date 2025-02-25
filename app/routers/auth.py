from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Annotated

from app.utils.database import get_db
from app.utils.auth import (
    verify_password, 
    get_password_hash, 
    create_tokens,
    create_token,
    verify_token,
    get_current_superuser,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, Token, DeleteUserResponse, DeletedUserInfo
from app.schemas.error import (
    ErrorDetail, 
    UNAUTHORIZED_ERROR, 
    NOT_FOUND_ERROR,
    USERNAME_TAKEN_ERROR,
    EMAIL_TAKEN_ERROR,
    DELETE_SELF_ERROR
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/register", 
    response_model=UserResponse,
    responses={
        400: {"model": ErrorDetail, "description": "Username or email already registered"},
        401: {"model": ErrorDetail, "description": "Not authenticated"},
        403: {"model": ErrorDetail, "description": "Not enough permissions"},
        422: {"model": ErrorDetail, "description": "Validation error"}
    }
)
async def register(
    user: UserCreate, 
    current_superuser: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Register new user (superuser only)"""
    if db.query(User).filter(User.username == user.username).first():
        USERNAME_TAKEN_ERROR.raise_exception()
    
    if db.query(User).filter(User.email == user.email).first():
        EMAIL_TAKEN_ERROR.raise_exception()
    
    db_user = User(
        username=user.username,
        email=user.email,
        password=get_password_hash(user.password),
        is_superuser=user.is_superuser
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post(
    "/login", 
    response_model=Token,
    responses={
        401: {"model": ErrorDetail, "description": "Incorrect username or password"},
        422: {"model": ErrorDetail, "description": "Validation error"}
    }
)
async def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    """Login to get access token (in response) and refresh token (in HTTP-only cookie)"""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        UNAUTHORIZED_ERROR.raise_exception()
    
    access_token, refresh_token = create_tokens(user.username)
    
    # Set refresh token as HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,  # Only send cookie over HTTPS
        samesite="lax",  # Protect against CSRF
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # Convert days to seconds
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post(
    "/refresh", 
    response_model=Token,
    responses={
        401: {"model": ErrorDetail, "description": "Invalid refresh token"},
        422: {"model": ErrorDetail, "description": "Validation error"}
    }
)
async def refresh_token(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias="refresh_token")] = None,
    db: Session = Depends(get_db)
):
    """Get new access token using refresh token from HTTP-only cookie"""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )
    
    # Verify refresh token
    token_data = verify_token(refresh_token, "refresh")
    
    # Check if user exists
    user = db.query(User).filter(User.username == token_data.sub).first()
    if not user:
        response.delete_cookie("refresh_token")
        UNAUTHORIZED_ERROR.raise_exception()
    
    # Create only new access token
    access_token = create_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access"
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/logout")
async def logout(response: Response):
    """Logout by clearing the refresh token cookie"""
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return {"message": "Successfully logged out"}

@router.delete(
    "/users/{user_id}", 
    response_model=DeleteUserResponse,
    responses={
        400: {"model": ErrorDetail, "description": "Cannot delete own superuser account"},
        401: {"model": ErrorDetail, "description": "Not authenticated"},
        403: {"model": ErrorDetail, "description": "Not enough permissions"},
        404: {"model": ErrorDetail, "description": "User not found"}
    }
)
async def delete_user(
    user_id: int,
    current_superuser: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Delete user by ID (superuser only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        NOT_FOUND_ERROR("User").raise_exception()
    
    if user.id == current_superuser.id:
        DELETE_SELF_ERROR.raise_exception()
    
    user_info = DeletedUserInfo(id=user.id, username=user.username, uuid=str(user.uuid))
    db.delete(user)
    db.commit()

    return DeleteUserResponse(
        message="User has been deleted successfully",
        deleted_user=user_info
    ) 