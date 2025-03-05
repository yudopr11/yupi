from sqlalchemy import Column, String, Integer, Enum, ForeignKey
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text
from sqlalchemy.orm import relationship
from app.utils.database import Base
from app.models.account import EnumAsString
import enum

class CategoryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"

class Category(Base):
    __tablename__ = "categories"
    
    category_id = Column(Integer, primary_key=True, nullable=False)
    uuid = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    type = Column(EnumAsString(CategoryType), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'), onupdate=text('now()'))
    
    user = relationship("User") 