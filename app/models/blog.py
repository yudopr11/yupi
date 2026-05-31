from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ARRAY, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.utils.uuid import uuid7
from app.utils.database import Base
from pgvector.sqlalchemy import Vector

class Post(Base):
    __tablename__ = "blog_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    title = Column(String, nullable=False)
    excerpt = Column(String, nullable=True)
    content = Column(Text, nullable=False)  # Using Text for longer content
    slug = Column(String, unique=True, nullable=False)
    published = Column(Boolean, default=False)
    reading_time = Column(Integer, nullable=False)
    tags = Column(ARRAY(String), nullable=True)
    embedding = Column(Vector(1536), nullable=True)  # Vector embedding for RAG search
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    user_id = Column(UUID(as_uuid=True), ForeignKey('auth_users.id', ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        Index('ix_blog_posts_user_id', 'user_id'),
        Index('ix_blog_posts_published', 'published'),
    )

    # Use string reference instead of class reference to avoid circular imports
    user = relationship("User", back_populates="posts")