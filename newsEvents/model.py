from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum
from sqlalchemy import Enum

# Association tables for many-to-many relationships
news_tags = Table(
    "news_tags",
    Base.metadata,
    Column("news_id", Integer, ForeignKey("news.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True)
)

event_tags = Table(
    "event_tags",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True)
)

class ContentType(str, enum.Enum):
    NEWS = "news"
    EVENT = "event"

class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    
    # Relationships
    news_items = relationship("News", secondary=news_tags, back_populates="tags")
    events = relationship("Event", secondary=event_tags, back_populates="tags")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    
    # Relationships
    news_items = relationship("News", back_populates="category")
    events = relationship("Event", back_populates="category")

class News(Base):
    __tablename__ = "news"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    featured_image_id = Column(Integer, ForeignKey("stored_files.id"), nullable=True)
    publish_date = Column(DateTime(timezone=True), nullable=False)
    author = Column(String(100), nullable=True)
    source = Column(String(100), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    summary = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    contact_info = Column(Text, nullable=True)
    is_published = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    category = relationship("Category", back_populates="news_items")
    tags = relationship("Tag", secondary=news_tags, back_populates="news_items")
    featured_image = relationship("StoredFile", foreign_keys=[featured_image_id])
    comments = relationship("Comment", back_populates="news")
    related_news = relationship(
        "News",
        secondary="related_news",
        primaryjoin="News.id == related_news.c.news_id",
        secondaryjoin="News.id == related_news.c.related_news_id",
        backref="related_by"
    )
    related_events = relationship(
        "Event",
        secondary="news_events",
        back_populates="related_news"
    )

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    featured_image_id = Column(Integer, ForeignKey("stored_files.id"), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    organizer = Column(String(100), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    summary = Column(String(500), nullable=True)
    description = Column(Text, nullable=False)
    venue = Column(String(255), nullable=True)
    location_address = Column(String(255), nullable=True)
    location_coordinates = Column(String(100), nullable=True)  # "lat,lng" format
    registration_link = Column(String(255), nullable=True)
    has_registration_form = Column(Boolean, default=False)
    ticket_price = Column(Float, nullable=True)
    is_free = Column(Boolean, default=True)
    contact_info = Column(Text, nullable=True)
    is_published = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    category = relationship("Category", back_populates="events")
    tags = relationship("Tag", secondary=event_tags, back_populates="events")
    featured_image = relationship("StoredFile", foreign_keys=[featured_image_id])
    comments = relationship("Comment", back_populates="event")
    related_events = relationship(
        "Event",
        secondary="related_events",
        primaryjoin="Event.id == related_events.c.event_id",
        secondaryjoin="Event.id == related_events.c.related_event_id",
        backref="related_by"
    )
    related_news = relationship(
        "News",
        secondary="news_events",
        back_populates="related_events"
    )

# Table for related news
related_news = Table(
    "related_news",
    Base.metadata,
    Column("news_id", Integer, ForeignKey("news.id"), primary_key=True),
    Column("related_news_id", Integer, ForeignKey("news.id"), primary_key=True)
)

# Table for related events
related_events = Table(
    "related_events",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id"), primary_key=True),
    Column("related_event_id", Integer, ForeignKey("events.id"), primary_key=True)
)

# Table for news-events relationships
news_events = Table(
    "news_events",
    Base.metadata,
    Column("news_id", Integer, ForeignKey("news.id"), primary_key=True),
    Column("event_id", Integer, ForeignKey("events.id"), primary_key=True)
)

class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    author_name = Column(String(100), nullable=True)
    author_email = Column(String(100), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    news_id = Column(Integer, ForeignKey("news.id"), nullable=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    content_type = Column(Enum(ContentType), nullable=False)
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    news = relationship("News", back_populates="comments")
    event = relationship("Event", back_populates="comments")
    user = relationship("User", backref="comments")
