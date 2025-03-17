from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.utils.database import Base
from app.models.account import EnumAsString
import enum, uuid

class TrxCategoryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"

class TrxCategory(Base):
    __tablename__ = "trx_categories"
    
    category_id = Column(Integer, primary_key=True, nullable=False)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    name = Column(String, nullable=False)
    type = Column(EnumAsString(TrxCategoryType), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'), onupdate=text('now()'))
    
    user = relationship("User") 