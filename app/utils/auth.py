from datetime import datetime, timedelta, UTC
from typing import Tuple
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.utils.database import get_db
from app.models.auth import User
from app.schemas.auth import TokenPayload

# JWT configuration
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password
    
    This function uses bcrypt to securely compare a plain text password
    with a previously hashed password.
    
    Args:
        plain_password (str): The plain text password to verify
        hashed_password (str): The hashed password to compare against
        
    Returns:
        bool: True if the passwords match, False otherwise
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def get_password_hash(password: str) -> str:
    """
    Generate a secure hash of a password
    
    This function uses bcrypt to generate a cryptographically secure
    hash of the provided password.
    
    Args:
        password (str): The plain text password to hash
        
    Returns:
        str: The hashed password
    """
    return bcrypt.hashpw(
        password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')

def create_token(data: dict, expires_delta: timedelta, token_type: str = "access") -> str:
    """
    Create a JWT token with specified expiration and type
    
    This function creates a JSON Web Token (JWT) with the provided data,
    expiration time, and token type. The token is signed using the
    application's secret key.
    
    Args:
        data (dict): The data to encode in the token
        expires_delta (timedelta): How long the token should be valid
        token_type (str): Type of token (access, refresh, or reset)
        
    Returns:
        str: The encoded JWT token
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({
        "exp": expire,
        "type": token_type
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_tokens(username: str) -> Tuple[str, str]:
    """
    Create both access and refresh tokens for a user
    
    This function generates a pair of tokens:
    - Access token: Short-lived token for API access
    - Refresh token: Long-lived token for obtaining new access tokens
    
    Args:
        username (str): The username to create tokens for
        
    Returns:
        Tuple[str, str]: A tuple containing (access_token, refresh_token)
    """
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
    """
    Create a password reset token
    
    This function generates a short-lived token specifically for
    password reset operations.
    
    Args:
        email (str): The email address to create the reset token for
        
    Returns:
        str: The password reset token
    """
    return create_token(
        data={"sub": email},
        expires_delta=timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        token_type="reset"
    )

def verify_token(token: str, token_type: str) -> TokenPayload:
    """
    Verify a JWT token and return its payload
    
    This function validates a JWT token by:
    - Checking the signature
    - Verifying the expiration time
    - Validating the token type
    - Decoding the payload
    
    Args:
        token (str): The JWT token to verify
        token_type (str): Expected type of the token
        
    Returns:
        TokenPayload: The decoded token payload
        
    Raises:
        HTTPException: If the token is invalid or has expired
    """
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
    """
    Get the current authenticated user
    
    This dependency function:
    - Extracts the JWT token from the request
    - Verifies the token
    - Retrieves the user from the database
    - Returns the user object
    
    Args:
        token (str): The JWT token from the request
        db (Session): Database session
        
    Returns:
        User: The authenticated user
        
    Raises:
        HTTPException: If the token is invalid or the user is not found
    """
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
    """
    Get the current authenticated superuser
    
    This dependency function verifies that the current user has
    superuser privileges.
    
    Args:
        current_user (User): The authenticated user
        
    Returns:
        User: The authenticated superuser
        
    Raises:
        HTTPException: If the user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superuser can perform this action"
        )
    return current_user

async def get_non_guest_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get the current authenticated non-guest user
    
    This dependency function verifies that the current user is not
    the guest user.
    
    Args:
        current_user (User): The authenticated user
        
    Returns:
        User: The authenticated non-guest user
        
    Raises:
        HTTPException: If the user is the guest user
    """
    if current_user.username == "guest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest users cannot access this endpoint"
        )
    return current_user

async def get_non_guest_superuser(
    current_user: User = Depends(get_current_superuser)
) -> User:
    """
    Get the current authenticated non-guest superuser
    
    This dependency function verifies that the current user is both
    a superuser and not the guest user.
    
    Args:
        current_user (User): The authenticated user
        
    Returns:
        User: The authenticated non-guest superuser
        
    Raises:
        HTTPException: If the user is not a superuser or is the guest user
    """
    if current_user.username == "guest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest users cannot access this endpoint"
        )
    return current_user 