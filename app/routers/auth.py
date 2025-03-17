from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Annotated, List

from app.utils.database import get_db
from app.utils.auth import (
    verify_password, 
    get_password_hash, 
    create_tokens,
    create_token,
    verify_token,
    get_current_superuser,
    create_password_reset_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)
from app.utils.email import send_password_reset_email
from app.models.user import User
from app.schemas.user import (
    UserCreate, 
    UserResponse, 
    Token, 
    DeleteUserResponse, 
    DeletedUserInfo,
    ForgotPasswordRequest,
    ResetPasswordRequest
)
from app.schemas.error import (
    ErrorDetail, 
    UNAUTHORIZED_ERROR, 
    NOT_FOUND_ERROR,
    USERNAME_TAKEN_ERROR,
    EMAIL_TAKEN_ERROR,
    DELETE_SELF_ERROR
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get(
    "/users", 
    response_model=List[UserResponse],
    responses={
        401: {"model": ErrorDetail, "description": "Not authenticated"},
        403: {"model": ErrorDetail, "description": "Not enough permissions"}
    }
)
async def get_users(
    current_superuser: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """
    Get list of all users (superuser only)
    
    This endpoint returns all registered users in the system.
    Only superusers have access to this endpoint.
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users 

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

@router.post(
    "/forgot-password",
    responses={
        200: {"description": "Password reset email sent"},
        404: {"model": ErrorDetail, "description": "Email not found"},
        422: {"model": ErrorDetail, "description": "Validation error"}
    }
)
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Request password reset
    
    This endpoint sends a password reset link to the provided email address
    if it's associated with a registered user account.
    """
    # Check if user with this email exists
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        return {"message": "If the email exists in our system, a reset link has been sent."}
    
    # Generate password reset token
    reset_token = create_password_reset_token(user.email)
    
    # Send email with reset link
    await send_password_reset_email(
        email=user.email,
        token=reset_token,
        background_tasks=background_tasks
    )
    
    # Return success message (same whether email exists or not for security)
    return {"message": "If the email exists in our system, a reset token will be sent."}

@router.post(
    "/reset-password",
    responses={
        200: {"description": "Password reset successful"},
        401: {"model": ErrorDetail, "description": "Invalid or expired token"},
        404: {"model": ErrorDetail, "description": "User not found"},
        422: {"model": ErrorDetail, "description": "Validation error"}
    }
)
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using token
    
    This endpoint allows a user to reset their password using a valid
    reset token received via email.
    """
    # Verify token
    try:
        token_data = verify_token(request.token, "reset")
        email = token_data.sub
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired password reset token"
        )
    
    # Find user by email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        NOT_FOUND_ERROR("User").raise_exception()
    
    # Update user's password
    user.password = get_password_hash(request.new_password)
    db.commit()
    
    return {"message": "Password has been reset successfully"}

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
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        NOT_FOUND_ERROR("User").raise_exception()
    
    if user.user_id == current_superuser.user_id:
        DELETE_SELF_ERROR.raise_exception()
    
    user_info = DeletedUserInfo(id=user.user_id, username=user.username, uuid=str(user.uuid))
    db.delete(user)
    db.commit()

    return DeleteUserResponse(
        message="User has been deleted successfully",
        deleted_item=user_info
    )
