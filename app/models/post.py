from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ARRAY, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.utils.database import Base
from pgvector.sqlalchemy import Vector

class Post(Base):
    __tablename__ = "posts"

    post_id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    title = Column(String, nullable=False)
    excerpt = Column(String, nullable=False)
    content = Column(Text, nullable=False)  # Using Text for longer content
    slug = Column(String, unique=True, nullable=False)
    published = Column(Boolean, default=False)
    reading_time = Column(Integer, nullable=False)
    tags = Column(ARRAY(String), nullable=True)
    embedding = Column(Vector(1536), nullable=True)  # Vector embedding for RAG search
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    author_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)

    # Use string reference instead of class reference to avoid circular imports
    author = relationship("User", back_populates="posts") 