from sqlalchemy.orm import Session
from app.models.user import User
from app.utils.auth import get_password_hash
from app.core.config import settings

def create_superuser(db: Session) -> None:
    """
    Create a superuser account if it doesn't already exist
    
    This function checks if a superuser account with the configured username 
    exists in the database. If not, it creates a new superuser account using
    the credentials defined in the application settings.
    
    This function is typically called during application startup to ensure
    that an administrator account is always available, which is especially
    important for initial setup and recovery situations.
    
    Args:
        db (Session): SQLAlchemy database session for database operations
        
    Returns:
        None
        
    Side effects:
        - Creates a new user record in the database if a superuser doesn't exist
        - Prints confirmation message when a superuser is created
    """
    # Check if superuser exists
    superuser = db.query(User).filter(
        User.username == settings.SUPERUSER_USERNAME
    ).first()
    
    if not superuser:
        # Create superuser if not exists
        superuser = User(
            username=settings.SUPERUSER_USERNAME,
            email=settings.SUPERUSER_EMAIL,
            password=get_password_hash(settings.SUPERUSER_PASSWORD),
            is_superuser=True
        )
        db.add(superuser)
        db.commit()
        print(f"Superuser '{settings.SUPERUSER_USERNAME}' created successfully!") 