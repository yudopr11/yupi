from sqlalchemy import Column, String, Integer, Text, ForeignKey, TypeDecorator, DECIMAL
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.utils.database import Base
import enum, uuid

class TrxAccountType(str, enum.Enum):
    BANK_ACCOUNT = "bank_account"
    CREDIT_CARD = "credit_card"
    OTHER = "other"

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

class TrxAccount(Base):
    __tablename__ = "trx_accounts"
    
    account_id = Column(Integer, primary_key=True, nullable=False)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    name = Column(String, nullable=False)
    type = Column(EnumAsString(TrxAccountType), nullable=False)
    description = Column(Text)
    limit = Column(DECIMAL(10, 2))
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'), onupdate=text('now()'))
    
    user = relationship("User", back_populates="accounts") 