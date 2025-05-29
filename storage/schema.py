from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class FileType(str, Enum):
    BLOG_IMAGE = "blog_image"
    NEWS_IMAGE = "news_image"
    OTHER = "other"

class FileUploadResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_path: str
    file_type: FileType
    content_type: str
    size_bytes: int
    bucket_name: str
    public_url: Optional[str]
    created_at: datetime
    
    class Config:
        orm_mode = True

class FileList(BaseModel):
    files: List[FileUploadResponse]
    count: int

class FileTypeFilter(BaseModel):
    file_type: Optional[FileType] = None
    related_entity_id: Optional[int] = None
