from sqlalchemy import Column, String, Integer, Text, ForeignKey, TypeDecorator, DECIMAL, DateTime
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.utils.database import Base
import enum, uuid

# Custom type decorator to handle enum values properly
class EnumAsString(TypeDecorator):
    impl = String
    cache_ok = True  # Safe to use in cache keys as enum values don't change
    
    def __init__(self, enumtype, *args, **kwargs):
        super(EnumAsString, self).__init__(*args, **kwargs)
        self._enumtype = enumtype
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return value.lower()
        return value.value
    
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self._enumtype(value)

class TrxAccountType(str, enum.Enum):
    BANK_ACCOUNT = "bank_account"
    CREDIT_CARD = "credit_card"
    OTHER = "other"

class TrxAccount(Base):
    __tablename__ = "cuan_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    type = Column(EnumAsString(TrxAccountType), nullable=False)
    description = Column(Text)
    limit = Column(DECIMAL(10, 2))
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="trx_accounts")

class TrxCategoryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"

class TrxCategory(Base):
    __tablename__ = "cuan_categories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    type = Column(EnumAsString(TrxCategoryType), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="trx_categories")

class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"

class Transaction(Base):
    __tablename__ = "cuan_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    transaction_type = Column(EnumAsString(TransactionType), nullable=False)
    transfer_fee = Column(DECIMAL(10, 2), nullable=False, default=0.0)
    
    account_id = Column(UUID(as_uuid=True), ForeignKey("cuan_accounts.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("cuan_categories.id", ondelete="SET NULL"), nullable=True)
    destination_account_id = Column(UUID(as_uuid=True), ForeignKey("cuan_accounts.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)
    
    account = relationship("TrxAccount", foreign_keys=[account_id])
    category = relationship("TrxCategory")
    destination_account = relationship("TrxAccount", foreign_keys=[destination_account_id])
    user = relationship("User", back_populates="transactions")
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())