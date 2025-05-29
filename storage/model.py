from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.sql import func
from database import Base
import enum

class FileType(str, enum.Enum):
    BLOG_IMAGE = "blog_image"
    NEWS_IMAGE = "news_image"
    OTHER = "other"

class StoredFile(Base):
    __tablename__ = "stored_files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)  # S3 key
    file_type = Column(Enum(FileType), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    bucket_name = Column(String(255), nullable=False)
    public_url = Column(String(512), nullable=True)
    related_entity_id = Column(Integer, nullable=True)  # Blog or news ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
