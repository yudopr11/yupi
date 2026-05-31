from sqlalchemy import Column, String, DateTime, Boolean, Integer
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.utils.uuid import uuid7
from app.utils.database import Base
from sqlalchemy.orm import relationship


class UsedResetToken(Base):
    __tablename__ = "auth_used_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = "auth_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String, nullable=False)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    posts = relationship("Post", back_populates="user")
    trx_accounts = relationship("TrxAccount", back_populates="user")
    trx_categories = relationship("TrxCategory", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    file_uploads = relationship("FileUpload", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"