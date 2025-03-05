# This file marks the models directory as a Python package
from .user import User
from .post import Post
from .account import Account    
from .category import Category
from .transaction import Transaction

# This ensures all models are registered with SQLAlchemy
__all__ = ["User", "Post", "Account", "Category", "Transaction"]