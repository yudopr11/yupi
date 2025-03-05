from sqlalchemy import Column, String, Integer, Text, Float, Enum, ForeignKey, TypeDecorator
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text
from sqlalchemy.orm import relationship
from app.utils.database import Base
import enum

class AccountType(str, enum.Enum):
    BANK_ACCOUNT = "bank_account"
    CREDIT_CARD = "credit_card"
    OTHER = "other"

# Custom type decorator to handle enum values properly
class EnumAsString(TypeDecorator):
    impl = String
    
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

class Account(Base):
    __tablename__ = "accounts"
    
    account_id = Column(Integer, primary_key=True, nullable=False)
    uuid = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    type = Column(EnumAsString(AccountType), nullable=False)
    description = Column(Text)
    limit = Column(Float)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'), onupdate=text('now()'))
    
    user = relationship("User") 