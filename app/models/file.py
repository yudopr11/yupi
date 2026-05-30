from sqlalchemy import Column, String, BigInteger, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.utils.database import Base
from app.utils.uuid import uuid7


class FileUpload(Base):
    __tablename__ = "file_uploads"
    __table_args__ = (
        Index("ix_file_uploads_user_id", "user_id"),
        Index("ix_file_uploads_is_orphan", "is_orphan"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_key = Column(String(500), nullable=False, unique=True)
    bucket = Column(String(100), nullable=False)
    is_orphan = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="file_uploads")
