# This file marks the models directory as a Python package
from .user import User
from .post import Post

# This ensures all models are registered with SQLAlchemy
__all__ = ["User", "Post"]