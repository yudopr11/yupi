from sqlalchemy import Column, Integer, Text, ForeignKey, DECIMAL
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.utils.database import Base
from app.models.account import EnumAsString
import enum, uuid

class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"

class Transaction(Base):
    __tablename__ = "transactions"
    
    transaction_id = Column(Integer, primary_key=True, nullable=False)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    transaction_date = Column(TIMESTAMP(timezone=True), nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    transaction_type = Column(EnumAsString(TransactionType), nullable=False)
    transfer_fee = Column(DECIMAL(10, 2), nullable=False, default=0.0)
    
    account_id = Column(Integer, ForeignKey("trx_accounts.account_id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("trx_categories.category_id", ondelete="SET NULL"), nullable=True)
    destination_account_id = Column(Integer, ForeignKey("trx_accounts.account_id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    
    account = relationship("TrxAccount", foreign_keys=[account_id])
    category = relationship("TrxCategory")
    destination_account = relationship("TrxAccount", foreign_keys=[destination_account_id])
    user = relationship("User")
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'), onupdate=text('now()')) 