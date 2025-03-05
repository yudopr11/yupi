from sqlalchemy import Column, String, Integer, Text, Float, ForeignKey, Enum
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text
from sqlalchemy.orm import relationship
from app.utils.database import Base
from app.models.account import EnumAsString
import enum

class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"

class Transaction(Base):
    __tablename__ = "transactions"
    
    transaction_id = Column(Integer, primary_key=True, nullable=False)
    uuid = Column(String, nullable=False, unique=True)
    transaction_date = Column(TIMESTAMP(timezone=True), nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(EnumAsString(TransactionType), nullable=False)
    
    account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.category_id", ondelete="SET NULL"), nullable=True)
    destination_account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    account = relationship("Account", foreign_keys=[account_id])
    category = relationship("Category")
    destination_account = relationship("Account", foreign_keys=[destination_account_id])
    user = relationship("User")
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'), onupdate=text('now()')) 