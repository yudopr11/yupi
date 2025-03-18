from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create SQLAlchemy engine instance with database URL from settings
engine = create_engine(settings.DATABASE_URL)

# Create session factory bound to the engine
# autocommit=False: Changes won't be committed automatically
# autoflush=False: Changes won't be flushed automatically to the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a base class for all models
Base = declarative_base()

def get_db():
    """
    FastAPI dependency that provides a SQLAlchemy database session
    
    This function creates a new SQLAlchemy SessionLocal that will be used
    for a single request, and then closed once the request is finished.
    It uses the yield statement to create a context in which the database
    session is active, and ensures proper closure through try/finally.
    
    Usage:
        Include this as a dependency in FastAPI endpoint functions:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            ...
    
    Yields:
        Session: A SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 