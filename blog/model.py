from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from newsEvents.model import Tag, Comment, ContentType
from storage.model import StoredFile  # Ensure proper import

# Association table for blog-tag many-to-many relationship
blog_tags = Table(
    "blog_tags",
    Base.metadata,
    Column("blog_id", Integer, ForeignKey("blogs.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True)
)

# Association table for related blogs
related_blogs = Table(
    "related_blogs",
    Base.metadata,
    Column("blog_id", Integer, ForeignKey("blogs.id"), primary_key=True),
    Column("related_blog_id", Integer, ForeignKey("blogs.id"), primary_key=True)
)

class BlogCategory(Base):
    __tablename__ = "blog_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    slug = Column(String(100), unique=True, nullable=False)
    
    # Relationships
    blogs = relationship("Blog", back_populates="category")

class Blog(Base):
    __tablename__ = "blogs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    featured_image_id = Column(Integer, ForeignKey("stored_files.id"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    author_name = Column(String(100), nullable=True)  # Used when author_id is not available
    publish_date = Column(DateTime(timezone=True), nullable=False)
    category_id = Column(Integer, ForeignKey("blog_categories.id"), nullable=True)
    introduction = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    cta_text = Column(String(255), nullable=True)
    cta_link = Column(String(255), nullable=True)
    author_bio = Column(Text, nullable=True)
    is_published = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    reading_time_minutes = Column(Integer, default=0)
    
    # SEO metadata
    seo_title = Column(String(100), nullable=True)
    meta_description = Column(String(255), nullable=True)
    og_image_id = Column(Integer, ForeignKey("stored_files.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    category = relationship("BlogCategory", back_populates="blogs")
    tags = relationship("Tag", secondary=blog_tags, backref="blog_posts")
    featured_image = relationship("StoredFile", foreign_keys=[featured_image_id])
    og_image = relationship("StoredFile", foreign_keys=[og_image_id])
    author = relationship("User", backref="blogs")
    comments = relationship("Comment", back_populates="blog")
    related_blogs = relationship(
        "Blog",
        secondary=related_blogs,
        primaryjoin="Blog.id == related_blogs.c.blog_id",
        secondaryjoin="Blog.id == related_blogs.c.related_blog_id",
        backref="referenced_by"
    )

class NewsletterSubscription(Base):
    __tablename__ = "newsletter_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=True)
    is_confirmed = Column(Boolean, default=False)
    confirmation_token = Column(String(100), nullable=True)
    source = Column(String(50), nullable=True)  # e.g. "blog", "homepage"
    subscribed_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    unsubscribed_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

# Extend the Comment model to include blog relationship
# This assumes we're using the Comment model from news&Events
Comment.blog_id = Column(Integer, ForeignKey("blogs.id"), nullable=True)
Comment.blog = relationship("Blog", back_populates="comments")
