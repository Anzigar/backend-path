from pydantic import BaseModel, Field, HttpUrl, EmailStr, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date
from enum import Enum

# Shared schemas
class ContentType(str, Enum):
    NEWS = "news"
    EVENT = "event"

# Tag schemas
class TagBase(BaseModel):
    name: str
    description: Optional[str] = None

class TagCreate(TagBase):
    pass

class TagResponse(TagBase):
    id: int
    
    class Config:
        orm_mode = True

# Category schemas
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    
    class Config:
        orm_mode = True

# Comment schemas
class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    author_name: Optional[str] = None
    author_email: Optional[EmailStr] = None
    content_type: ContentType

class CommentCreate(CommentBase):
    news_id: Optional[int] = None
    event_id: Optional[int] = None
    
    @validator('news_id', 'event_id')
    def check_content_reference(cls, v, values):
        # Only validate if content_type is present
        if 'content_type' in values:
            content_type = values.get('content_type')
            field = 'news_id' if content_type == ContentType.NEWS else 'event_id'
            
            # For NEWS type, we need a news_id
            if content_type == ContentType.NEWS and field == 'news_id' and v is None:
                if 'event_id' in values and values.get('event_id') is not None:
                    # If event_id is provided but content_type is NEWS, that's okay
                    pass
                else:
                    raise ValueError('News ID is required for news comments')
            
            # For EVENT type, we need an event_id
            if content_type == ContentType.EVENT and field == 'event_id' and v is None:
                if 'news_id' in values and values.get('news_id') is not None:
                    # If news_id is provided but content_type is EVENT, that's okay
                    pass
                else:
                    raise ValueError('Event ID is required for event comments')
        return v

class CommentResponse(CommentBase):
    id: int
    created_at: datetime
    is_approved: bool
    user_id: Optional[int] = None
    
    class Config:
        orm_mode = True

# News schemas
class NewsBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    summary: Optional[str] = Field(None, max_length=500)
    content: str
    author: Optional[str] = None
    source: Optional[str] = None
    contact_info: Optional[str] = None

class NewsCreate(NewsBase):
    slug: Optional[str] = None
    publish_date: Optional[datetime] = None
    category_id: Optional[int] = None
    tag_ids: Optional[List[int]] = Field(default_factory=list)
    featured_image_id: Optional[int] = None
    is_published: bool = False
    related_news_ids: Optional[List[int]] = Field(default_factory=list) 
    related_event_ids: Optional[List[int]] = Field(default_factory=list)

class NewsUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    slug: Optional[str] = None
    summary: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None
    publish_date: Optional[datetime] = None
    category_id: Optional[int] = None
    featured_image_id: Optional[int] = None
    is_published: Optional[bool] = None
    contact_info: Optional[str] = None
    tag_ids: Optional[List[int]] = None
    related_news_ids: Optional[List[int]] = None
    related_event_ids: Optional[List[int]] = None

class NewsResponse(NewsBase):
    id: int
    slug: str
    publish_date: datetime
    is_published: bool
    view_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    category: Optional[CategoryResponse] = None
    featured_image: Optional[Dict[str, Any]] = None
    tags: List[TagResponse] = []
    
    class Config:
        orm_mode = True

class NewsDetailResponse(NewsResponse):
    comments: List[CommentResponse] = []
    related_news: List["NewsResponse"] = []
    related_events: List["EventResponse"] = []
    
    class Config:
        orm_mode = True

# Event schemas
class EventBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    summary: Optional[str] = None
    description: str
    organizer: Optional[str] = None
    venue: Optional[str] = None
    location_address: Optional[str] = None
    location_coordinates: Optional[str] = None
    registration_link: Optional[str] = None
    has_registration_form: bool = False
    ticket_price: Optional[float] = None
    is_free: bool = False
    contact_info: Optional[str] = None

class EventCreate(EventBase):
    slug: Optional[str] = None
    start_date: datetime
    end_date: datetime
    category_id: Optional[int] = None
    featured_image_id: Optional[int] = None
    is_published: bool = False
    tag_ids: List[int] = Field(default_factory=list)
    related_news_ids: Optional[List[int]] = Field(default_factory=list) 
    related_event_ids: Optional[List[int]] = Field(default_factory=list)

class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    slug: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    organizer: Optional[str] = None
    category_id: Optional[int] = None
    featured_image_id: Optional[int] = None
    venue: Optional[str] = None
    location_address: Optional[str] = None
    location_coordinates: Optional[str] = None
    registration_link: Optional[str] = None
    has_registration_form: Optional[bool] = None
    ticket_price: Optional[float] = None
    is_free: Optional[bool] = None
    contact_info: Optional[str] = None
    is_published: Optional[bool] = None
    tag_ids: Optional[List[int]] = Field(default_factory=list)
    related_news_ids: Optional[List[int]] = Field(default_factory=list)
    related_event_ids: Optional[List[int]] = Field(default_factory=list)

class EventResponse(EventBase):
    id: int
    slug: str
    start_date: datetime
    end_date: Optional[datetime] = None
    is_published: bool
    view_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    category: Optional[CategoryResponse] = None
    featured_image: Optional[Dict[str, Any]] = None
    tags: List[TagResponse] = []
    
    class Config:
        orm_mode = True

class EventDetailResponse(EventResponse):
    comments: List[CommentResponse] = []
    related_news: List[NewsResponse] = []
    related_events: List["EventResponse"] = []
    
    class Config:
        orm_mode = True

# Query parameters schemas
class ContentPaginationParams(BaseModel):
    skip: int = 0
    limit: int = 10
    search: Optional[str] = None
    category_id: Optional[int] = None
    tag_ids: Optional[List[int]] = Field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_published: Optional[bool] = True

class EventPaginationParams(BaseModel):
    page: int = 1
    limit: int = 10
    search: Optional[str] = None
    category_id: Optional[int] = None
    tag_ids: List[int] = Field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_published: Optional[bool] = True

# Response list schemas
class NewsListResponse(BaseModel):
    items: List[NewsResponse]
    total: int
    
    class Config:
        orm_mode = True

class EventListResponse(BaseModel):
    items: List[EventResponse]
    total: int
    
    class Config:
        orm_mode = True
