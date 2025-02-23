from sqlalchemy.orm import Session
from app.models.user import User
from app.utils.auth import get_password_hash
from app.utils.config import get_settings

def create_superuser(db: Session) -> None:
    """Create superuser if not exists"""
    settings = get_settings()
    
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