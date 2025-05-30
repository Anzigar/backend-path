from pydantic import BaseModel, Field, HttpUrl, EmailStr, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date
from enum import Enum
from newsEvents.schema import TagResponse, CommentResponse, ContentType

# Base schemas
class BlogCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    slug: Optional[str] = None

class BlogCategoryCreate(BlogCategoryBase):
    pass

class BlogCategoryResponse(BlogCategoryBase):
    id: int
    
    class Config:
        orm_mode = True

# Blog schemas
class BlogBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    introduction: Optional[str] = None
    content: str
    author_name: Optional[str] = None
    cta_text: Optional[str] = None
    cta_link: Optional[str] = None
    author_bio: Optional[str] = None
    
    # SEO fields
    seo_title: Optional[str] = Field(None, max_length=100)
    meta_description: Optional[str] = Field(None, max_length=255)

class BlogCreate(BlogBase):
    slug: Optional[str] = None
    publish_date: Optional[datetime] = None
    category_id: Optional[int] = None
    author_id: Optional[int] = None
    featured_image_id: Optional[int] = None
    og_image_id: Optional[int] = None
    is_published: bool = False
    tag_ids: Optional[List[int]] = Field(default_factory=list)
    related_blog_ids: Optional[List[int]] = Field(default_factory=list)

class BlogUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    slug: Optional[str] = None
    introduction: Optional[str] = None
    content: Optional[str] = None
    publish_date: Optional[datetime] = None
    author_name: Optional[str] = None
    author_id: Optional[int] = None
    category_id: Optional[int] = None
    featured_image_id: Optional[int] = None
    og_image_id: Optional[int] = None
    is_published: Optional[bool] = None
    cta_text: Optional[str] = None
    cta_link: Optional[str] = None
    author_bio: Optional[str] = None
    seo_title: Optional[str] = None
    meta_description: Optional[str] = None
    tag_ids: Optional[List[int]] = None
    related_blog_ids: Optional[List[int]] = None

class BlogResponse(BlogBase):
    id: int
    slug: str
    publish_date: datetime
    reading_time_minutes: int
    is_published: bool
    view_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    category: Optional[BlogCategoryResponse] = None
    featured_image: Optional[Dict[str, Any]] = None
    og_image: Optional[Dict[str, Any]] = None
    tags: List[TagResponse] = []
    
    class Config:
        orm_mode = True

class BlogDetailResponse(BlogResponse):
    comments: List[CommentResponse] = []
    related_blogs: List[BlogResponse] = []
    
    class Config:
        orm_mode = True

# Newsletter subscription schemas
class SubscriptionCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    source: Optional[str] = None

class SubscriptionResponse(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    is_confirmed: bool
    subscribed_at: datetime
    
    class Config:
        orm_mode = True

# Blog comment schema (extends existing comment schema)
class BlogCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    author_name: Optional[str] = None
    author_email: Optional[EmailStr] = None
    blog_id: int
    user_id: Optional[int] = None

# Query parameters
class BlogPaginationParams(BaseModel):
    page: int = 1
    limit: int = 10
    search: Optional[str] = None
    category_id: Optional[int] = None
    tag_ids: List[int] = Field(default_factory=list)
    author_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_published: Optional[bool] = True

# Response list
class BlogListResponse(BaseModel):
    items: List[BlogResponse]
    total: int
    
    class Config:
        orm_mode = True
