from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import List, Optional, Dict, Any, Union
from datetime import date
from fastapi import HTTPException, status
from . import model, schema
import uuid

# ---------- News CRUD operations ---------- #

def create_news(db: Session, news: schema.NewsCreate) -> model.News:
    """Create a new news article"""
    # Generate slug if not provided
    if not news.slug:
        news.slug = f"{'-'.join(news.title.lower().split()[:5])}-{uuid.uuid4().hex[:8]}"
        
    db_news = model.News(
        title=news.title,
        slug=news.slug,
        subtitle=news.subtitle,
        content=news.content,
        source=news.source,
        source_url=news.source_url,
        publish_date=news.publish_date,
        is_published=news.is_published,
        category_id=news.category_id,
        featured_image_id=news.featured_image_id,
    )
    
    db.add(db_news)
    db.commit()
    db.refresh(db_news)
    
    # Add tags if provided
    if news.tag_ids:
        for tag_id in news.tag_ids:
            db_tag = db.query(model.Tag).filter(model.Tag.id == tag_id).first()
            if db_tag:
                db_news.tags.append(db_tag)
        
        db.commit()
        db.refresh(db_news)
    
    # Add related news if provided
    if news.related_news_ids:
        for related_id in news.related_news_ids:
            related_news = db.query(model.News).filter(model.News.id == related_id).first()
            if related_news:
                db_news.related_news.append(related_news)
        
        db.commit()
        db.refresh(db_news)
    
    return db_news

def get_news(db: Session, news_id: int) -> model.News:
    """Get a news article by ID"""
    news = db.query(model.News).filter(model.News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")
    return news

def get_news_by_slug(db: Session, slug: str) -> model.News:
    """Get a news article by slug"""
    news = db.query(model.News).filter(model.News.slug == slug).first()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")
    return news

def get_news_list(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    tag_ids: List[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    is_published: Optional[bool] = True
) -> Dict[str, Any]:
    """Get list of news articles with filtering"""
    query = db.query(model.News)
    
    # Apply filters if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(model.News.title.ilike(search_term) | model.News.content.ilike(search_term))
    
    if category_id:
        query = query.filter(model.News.category_id == category_id)
    
    if tag_ids:
        for tag_id in tag_ids:
            query = query.filter(model.News.tags.any(model.Tag.id == tag_id))
    
    if start_date:
        query = query.filter(model.News.publish_date >= start_date)
    
    if end_date:
        query = query.filter(model.News.publish_date <= end_date)
    
    if is_published is not None:
        query = query.filter(model.News.is_published == is_published)
    
    # Sort by publish date descending
    query = query.order_by(desc(model.News.publish_date))
    
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    
    return {
        "items": items,
        "total": total
    }

def update_news(db: Session, news_id: int, news_update: schema.NewsUpdate) -> model.News:
    """Update a news article"""
    db_news = get_news(db, news_id)
    
    # Update basic fields
    update_data = news_update.dict(exclude_unset=True)
    
    # Remove tag_ids and related_news_ids from update_data as they need special handling
    tag_ids = update_data.pop("tag_ids", None)
    related_news_ids = update_data.pop("related_news_ids", None)
    
    # Update the news object
    for key, value in update_data.items():
        setattr(db_news, key, value)
    
    # Update tags if provided
    if tag_ids is not None:
        # Clear existing tags
        db_news.tags = []
        
        # Add new tags
        for tag_id in tag_ids:
            db_tag = db.query(model.Tag).filter(model.Tag.id == tag_id).first()
            if db_tag:
                db_news.tags.append(db_tag)
    
    # Update related news if provided
    if related_news_ids is not None:
        # Clear existing related news
        db_news.related_news = []
        
        # Add new related news
        for related_id in related_news_ids:
            related_news = db.query(model.News).filter(model.News.id == related_id).first()
            if related_news:
                db_news.related_news.append(related_news)
    
    db.commit()
    db.refresh(db_news)
    return db_news

def delete_news(db: Session, news_id: int) -> Dict[str, str]:
    """Delete a news article"""
    db_news = get_news(db, news_id)
    db.delete(db_news)
    db.commit()
    return {"message": "News deleted successfully"}

def increment_news_view_count(db: Session, news_id: int) -> model.News:
    """Increment view count for a news article"""
    db_news = get_news(db, news_id)
    db_news.view_count = db_news.view_count + 1
    db.commit()
    db.refresh(db_news)
    return db_news

# ---------- Event CRUD operations ---------- #

def create_event(db: Session, event: schema.EventCreate) -> model.Event:
    """Create a new event"""
    # Generate slug if not provided
    if not event.slug:
        event.slug = f"{'-'.join(event.title.lower().split()[:5])}-{uuid.uuid4().hex[:8]}"
        
    db_event = model.Event(
        title=event.title,
        slug=event.slug,
        summary=event.summary,
        description=event.description,
        start_date=event.start_date,
        end_date=event.end_date,
        organizer=event.organizer,
        category_id=event.category_id,
        venue=event.venue,
        location_address=event.location_address,
        location_coordinates=event.location_coordinates,
        registration_link=event.registration_link,
        has_registration_form=event.has_registration_form,
        ticket_price=event.ticket_price,
        is_free=event.is_free,
        contact_info=event.contact_info,
        is_published=event.is_published,
        featured_image_id=event.featured_image_id
    )
    
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    # Add tags if provided
    if event.tag_ids:
        for tag_id in event.tag_ids:
            db_tag = db.query(model.Tag).filter(model.Tag.id == tag_id).first()
            if db_tag:
                db_event.tags.append(db_tag)
        
        db.commit()
        db.refresh(db_event)
    
    # Add related news and events if provided
    if event.related_news_ids:
        for related_id in event.related_news_ids:
            related_news = db.query(model.News).filter(model.News.id == related_id).first()
            if related_news:
                db_event.related_news.append(related_news)
    
    if event.related_event_ids:
        for related_id in event.related_event_ids:
            related_event = db.query(model.Event).filter(model.Event.id == related_id).first()
            if related_event and related_event.id != db_event.id:
                db_event.related_events.append(related_event)
    
    if event.related_news_ids or event.related_event_ids:
        db.commit()
        db.refresh(db_event)
    
    return db_event

def get_event(db: Session, event_id: int) -> model.Event:
    """Get an event by ID"""
    event = db.query(model.Event).filter(model.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

def get_event_by_slug(db: Session, slug: str) -> model.Event:
    """Get an event by slug"""
    event = db.query(model.Event).filter(model.Event.slug == slug).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

def get_event_list(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    tag_ids: List[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    is_published: Optional[bool] = True
) -> Dict[str, Any]:
    """Get list of events with filtering"""
    query = db.query(model.Event)
    
    # Apply filters if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            model.Event.title.ilike(search_term) | 
            model.Event.description.ilike(search_term) |
            model.Event.organizer.ilike(search_term)
        )
    
    if category_id:
        query = query.filter(model.Event.category_id == category_id)
    
    if tag_ids:
        for tag_id in tag_ids:
            query = query.filter(model.Event.tags.any(model.Tag.id == tag_id))
    
    if start_date:
        query = query.filter(model.Event.start_date >= start_date)
    
    if end_date:
        query = query.filter(model.Event.end_date <= end_date)
    
    if is_published is not None:
        query = query.filter(model.Event.is_published == is_published)
    
    # Sort by start_date ascending to show upcoming events first
    query = query.order_by(model.Event.start_date.asc())
    
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    
    return {
        "items": items,
        "total": total
    }

def update_event(db: Session, event_id: int, event_update: schema.EventUpdate) -> model.Event:
    """Update an event"""
    db_event = get_event(db, event_id)
    
    # Update basic fields
    update_data = event_update.dict(exclude_unset=True)
    
    # Remove tag_ids and related_ids from update_data as they need special handling
    tag_ids = update_data.pop("tag_ids", None)
    related_news_ids = update_data.pop("related_news_ids", None)
    related_event_ids = update_data.pop("related_event_ids", None)
    
    # Update the event object
    for key, value in update_data.items():
        setattr(db_event, key, value)
    
    # Update tags if provided
    if tag_ids is not None:
        # Clear existing tags
        db_event.tags = []
        
        # Add new tags
        for tag_id in tag_ids:
            db_tag = db.query(model.Tag).filter(model.Tag.id == tag_id).first()
            if db_tag:
                db_event.tags.append(db_tag)
    
    # Update related news if provided
    if related_news_ids is not None:
        # Clear existing related news
        db_event.related_news = []
        
        # Add new related news
        for related_id in related_news_ids:
            related_news = db.query(model.News).filter(model.News.id == related_id).first()
            if related_news:
                db_event.related_news.append(related_news)
    
    # Update related events if provided
    if related_event_ids is not None:
        # Clear existing related events
        db_event.related_events = []
        
        # Add new related events
        for related_id in related_event_ids:
            related_event = db.query(model.Event).filter(model.Event.id == related_id).first()
            if related_event and related_event.id != db_event.id:
                db_event.related_events.append(related_event)
    
    db.commit()
    db.refresh(db_event)
    return db_event

def delete_event(db: Session, event_id: int) -> Dict[str, str]:
    """Delete an event"""
    db_event = get_event(db, event_id)
    db.delete(db_event)
    db.commit()
    return {"message": "Event deleted successfully"}

def increment_event_view_count(db: Session, event_id: int) -> model.Event:
    """Increment view count for an event"""
    db_event = get_event(db, event_id)
    db_event.view_count = db_event.view_count + 1
    db.commit()
    db.refresh(db_event)
    return db_event

# ---------- Category CRUD operations ---------- #

def create_category(db: Session, category: schema.CategoryCreate) -> model.Category:
    """Create a new category"""
    db_category = model.Category(
        name=category.name,
        description=category.description,
        content_type=category.content_type
    )
    
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def get_category(db: Session, category_id: int) -> model.Category:
    """Get a category by ID"""
    category = db.query(model.Category).filter(model.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

def get_categories(
    db: Session, 
    content_type: Optional[schema.ContentType] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[model.Category]:
    """Get all categories with optional content type filter"""
    query = db.query(model.Category)
    
    if content_type:
        query = query.filter(model.Category.content_type == content_type)
    
    return query.offset(skip).limit(limit).all()

def update_category(db: Session, category_id: int, category_update: schema.CategoryUpdate) -> model.Category:
    """Update a category"""
    db_category = get_category(db, category_id)
    
    # Update fields
    update_data = category_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)
    
    db.commit()
    db.refresh(db_category)
    return db_category

def delete_category(db: Session, category_id: int) -> Dict[str, str]:
    """Delete a category"""
    db_category = get_category(db, category_id)
    db.delete(db_category)
    db.commit()
    return {"message": "Category deleted successfully"}

# ---------- Tag CRUD operations ---------- #

def create_tag(db: Session, tag: schema.TagCreate) -> model.Tag:
    """Create a new tag"""
    db_tag = model.Tag(
        name=tag.name,
        description=tag.description
    )
    
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

def get_tag(db: Session, tag_id: int) -> model.Tag:
    """Get a tag by ID"""
    tag = db.query(model.Tag).filter(model.Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag

def get_tags(db: Session, skip: int = 0, limit: int = 100) -> List[model.Tag]:
    """Get all tags"""
    return db.query(model.Tag).offset(skip).limit(limit).all()

def update_tag(db: Session, tag_id: int, tag_update: schema.TagUpdate) -> model.Tag:
    """Update a tag"""
    db_tag = get_tag(db, tag_id)
    
    # Update fields
    update_data = tag_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tag, key, value)
    
    db.commit()
    db.refresh(db_tag)
    return db_tag

def delete_tag(db: Session, tag_id: int) -> Dict[str, str]:
    """Delete a tag"""
    db_tag = get_tag(db, tag_id)
    db.delete(db_tag)
    db.commit()
    return {"message": "Tag deleted successfully"}

# ---------- Comment CRUD operations ---------- #

def create_comment(db: Session, comment: schema.CommentCreate) -> model.Comment:
    """Create a new comment"""
    db_comment = model.Comment(
        content=comment.content,
        author_name=comment.author_name,
        author_email=comment.author_email,
        user_id=comment.user_id,
        content_id=comment.content_id,
        content_type=comment.content_type,
        parent_id=comment.parent_id
    )
    
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

def get_comment(db: Session, comment_id: int) -> model.Comment:
    """Get a comment by ID"""
    comment = db.query(model.Comment).filter(model.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment

def get_comments(
    db: Session, 
    content_id: int,
    content_type: schema.ContentType,
    skip: int = 0, 
    limit: int = 100
) -> List[model.Comment]:
    """Get comments for a specific content"""
    return db.query(model.Comment).filter(
        model.Comment.content_id == content_id,
        model.Comment.content_type == content_type,
        model.Comment.parent_id == None  # Only get top-level comments
    ).order_by(desc(model.Comment.created_at)).offset(skip).limit(limit).all()

def update_comment(db: Session, comment_id: int, comment_update: schema.CommentUpdate) -> model.Comment:
    """Update a comment"""
    db_comment = get_comment(db, comment_id)
    
    # Update fields
    update_data = comment_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_comment, key, value)
    
    db.commit()
    db.refresh(db_comment)
    return db_comment

def delete_comment(db: Session, comment_id: int) -> Dict[str, str]:
    """Delete a comment"""
    db_comment = get_comment(db, comment_id)
    db.delete(db_comment)
    db.commit()
    return {"message": "Comment deleted successfully"}
