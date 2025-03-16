from datetime import datetime, timedelta, UTC
from typing import Optional, Tuple
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.utils.database import get_db
from app.models.user import User
from app.schemas.user import TokenData, TokenPayload

# JWT configuration
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')

def create_token(data: dict, expires_delta: timedelta, token_type: str = "access") -> str:
    """Create a JWT token with specified expiration and type"""
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({
        "exp": expire,
        "type": token_type
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_tokens(username: str) -> Tuple[str, str]:
    """Create both access and refresh tokens"""
    # Create access token
    access_token = create_token(
        data={"sub": username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access"
    )
    
    # Create refresh token
    refresh_token = create_token(
        data={"sub": username},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh"
    )
    
    return access_token, refresh_token

def create_password_reset_token(email: str) -> str:
    """Create a password reset token"""
    return create_token(
        data={"sub": email},
        expires_delta=timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        token_type="reset"
    )

def verify_token(token: str, token_type: str) -> TokenPayload:
    """Verify a token and return its payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
        
        if token_data.type != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type} token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        return token_data
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    token_data = verify_token(token, "access")
    user = db.query(User).filter(User.username == token_data.sub).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superuser can perform this action"
        )
    return current_user

async def get_non_guest_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.username == "guest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest users cannot access this endpoint"
        )
    return current_user

async def get_non_guest_superuser(
    current_user: User = Depends(get_current_superuser)
) -> User:
    if current_user.username == "guest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest users cannot access this endpoint"
        )
    return current_user 