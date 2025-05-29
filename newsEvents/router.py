from fastapi import APIRouter, Depends, HTTPException, Query, status, Form, Body
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from database import get_db
from . import model, schema
from storage.model import StoredFile
import datetime
from slugify import slugify
from sqlalchemy import func, or_, desc
from pydantic import HttpUrl  # Add this import

# Create routers
news_router = APIRouter(
    prefix="/news",
    tags=["news"]
)

event_router = APIRouter(
    prefix="/events",
    tags=["events"]
)

category_router = APIRouter(
    prefix="/categories",
    tags=["categories"]
)

tag_router = APIRouter(
    prefix="/tags",
    tags=["tags"]
)

comment_router = APIRouter(
    prefix="/comments",
    tags=["comments"]
)

# Helper functions
def generate_slug(title, db, model_class, id=None):
    base_slug = slugify(title)
    slug = base_slug
    counter = 1
    
    # Check if slug exists while excluding the current item if updating
    query = db.query(model_class).filter(model_class.slug == slug)
    if id:
        query = query.filter(model_class.id != id)
    
    while query.first() is not None:
        slug = f"{base_slug}-{counter}"
        query = db.query(model_class).filter(model_class.slug == slug)
        if id:
            query = query.filter(model_class.id != id)
        counter += 1
    
    return slug

# Category endpoints
@category_router.post("/", response_model=schema.CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(category: schema.CategoryCreate, db: Session = Depends(get_db)):
    # Check if category with same name exists
    existing_category = db.query(model.Category).filter(model.Category.name == category.name).first()
    if existing_category:
        return existing_category  # Return the existing category instead of creating a duplicate
    
    db_category = model.Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@category_router.get("/", response_model=List[schema.CategoryResponse])
def read_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    categories = db.query(model.Category).offset(skip).limit(limit).all()
    return categories

@category_router.get("/{category_id}", response_model=schema.CategoryResponse)
def read_category(category_id: int, db: Session = Depends(get_db)):
    db_category = db.query(model.Category).filter(model.Category.id == category_id).first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category

# Tag endpoints
@tag_router.post("/", response_model=schema.TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(tag: schema.TagCreate, db: Session = Depends(get_db)):
    # Check if tag with same name exists
    existing_tag = db.query(model.Tag).filter(model.Tag.name == tag.name).first()
    if existing_tag:
        return existing_tag  # Return the existing tag instead of creating a duplicate
    
    db_tag = model.Tag(**tag.dict())
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

@tag_router.get("/", response_model=List[schema.TagResponse])
def read_tags(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tags = db.query(model.Tag).offset(skip).limit(limit).all()
    return tags

@tag_router.get("/{tag_id}", response_model=schema.TagResponse)
def read_tag(tag_id: int, db: Session = Depends(get_db)):
    db_tag = db.query(model.Tag).filter(model.Tag.id == tag_id).first()
    if db_tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return db_tag

# News endpoints
# Modify create_news function for better handling of missing data
@news_router.post("/", response_model=schema.NewsResponse, status_code=status.HTTP_201_CREATED)
def create_news(news: schema.NewsCreate, db: Session = Depends(get_db)):
    # Generate slug if not provided
    if not news.slug:
        news.slug = generate_slug(news.title, db, model.News)
    
    # Set publish date if not provided
    if not news.publish_date:
        news.publish_date = datetime.datetime.now()
    
    # Extract tags and related items for later processing
    tag_ids = news.tag_ids if news.tag_ids is not None else []
    related_news_ids = news.related_news_ids if news.related_news_ids is not None else []
    related_event_ids = news.related_event_ids if news.related_event_ids is not None else []
    
    # Remove relationship fields from the dict
    news_data = news.dict(exclude={"tag_ids", "related_news_ids", "related_event_ids"})
    
    # Validate category_id if provided
    if news_data.get("category_id"):
        category = db.query(model.Category).filter(model.Category.id == news_data["category_id"]).first()
        if not category:
            # If category doesn't exist, set to None to avoid FK constraint error
            news_data["category_id"] = None
    
    # Validate featured_image_id if provided
    if news_data.get("featured_image_id"):
        from storage.model import StoredFile
        stored_file = db.query(StoredFile).filter(StoredFile.id == news_data["featured_image_id"]).first()
        if not stored_file:
            # If file doesn't exist, set to None to avoid FK constraint error
            news_data["featured_image_id"] = None
    
    # Create news item
    db_news = model.News(**news_data)
    db.add(db_news)
    db.commit()
    db.refresh(db_news)
    
    # Add tags - only if we have tag IDs and they're valid
    if tag_ids:
        tags = db.query(model.Tag).filter(model.Tag.id.in_(tag_ids)).all()
        if tags:  # Only assign if we found valid tags
            db_news.tags = tags
    
    # Add related news - only proceed if we have IDs and they exist
    if related_news_ids:
        related_news = db.query(model.News).filter(model.News.id.in_(related_news_ids)).all()
        if related_news:  # Only assign if we found valid related news
            db_news.related_news = related_news
    
    # Add related events - only proceed if we have IDs and they exist
    if related_event_ids:
        related_events = db.query(model.Event).filter(model.Event.id.in_(related_event_ids)).all()
        if related_events:  # Only assign if we found valid related events
            db_news.related_events = related_events
    
    db.commit()
    db.refresh(db_news)
    return db_news

@news_router.get("/", response_model=schema.NewsListResponse)
def read_news(
    params: schema.ContentPaginationParams = Depends(),
    db: Session = Depends(get_db)
):
    query = db.query(model.News)
    
    # Apply filters
    if params.search:
        search = f"%{params.search}%"
        query = query.filter(or_(
            model.News.title.ilike(search),
            model.News.content.ilike(search),
            model.News.summary.ilike(search)
        ))
    
    if params.category_id:
        query = query.filter(model.News.category_id == params.category_id)
    
    if params.tag_ids:
        query = query.join(model.News.tags).filter(model.Tag.id.in_(params.tag_ids)).group_by(model.News.id)
    
    if params.start_date:
        query = query.filter(func.date(model.News.publish_date) >= params.start_date)
    
    if params.end_date:
        query = query.filter(func.date(model.News.publish_date) <= params.end_date)
    
    if params.is_published is not None:
        query = query.filter(model.News.is_published == params.is_published)
    
    # Count total before pagination
    total = query.count()
    
    # Apply pagination and eager loading
    items = query.order_by(desc(model.News.publish_date))\
        .options(
            joinedload(model.News.category),
            joinedload(model.News.tags),
            joinedload(model.News.featured_image)
        )\
        .offset(params.skip)\
        .limit(params.limit)\
        .all()
    
    return {"items": items, "total": total}

@news_router.get("/{slug}", response_model=schema.NewsDetailResponse)
def read_news_by_slug(slug: str, db: Session = Depends(get_db)):
    db_news = db.query(model.News)\
        .filter(model.News.slug == slug)\
        .options(
            joinedload(model.News.category),
            joinedload(model.News.tags),
            joinedload(model.News.featured_image),
            joinedload(model.News.comments).filter(model.Comment.is_approved == True),
            joinedload(model.News.related_news),
            joinedload(model.News.related_events)
        )\
        .first()
    
    if db_news is None:
        raise HTTPException(status_code=404, detail="News article not found")
    
    # Increment view count
    db_news.view_count += 1
    db.commit()
    
    return db_news

@news_router.patch("/{news_id}", response_model=schema.NewsResponse)
def update_news(news_id: int, news: schema.NewsUpdate, db: Session = Depends(get_db)):
    db_news = db.query(model.News).filter(model.News.id == news_id).first()
    if db_news is None:
        raise HTTPException(status_code=404, detail="News article not found")
    
    # Update slug if title is changed
    if news.title and news.title != db_news.title:
        if not news.slug:  # Only auto-generate slug if not explicitly provided
            news.slug = generate_slug(news.title, db, model.News, news_id)
    
    # Extract relationship fields
    tag_ids = news.tag_ids
    related_news_ids = news.related_news_ids
    related_event_ids = news.related_event_ids
    
    # Update fields
    update_data = news.dict(exclude_unset=True, exclude={"tag_ids", "related_news_ids", "related_event_ids"})
    
    # Validate category_id if it's being updated
    if "category_id" in update_data and update_data["category_id"] is not None:
        category = db.query(model.Category).filter(model.Category.id == update_data["category_id"]).first()
        if not category:
            # If category doesn't exist, set to None
            update_data["category_id"] = None
    
    # Validate featured_image_id if it's being updated
    if "featured_image_id" in update_data and update_data["featured_image_id"] is not None:
        from storage.model import StoredFile
        stored_file = db.query(StoredFile).filter(StoredFile.id == update_data["featured_image_id"]).first()
        if not stored_file:
            # If file doesn't exist, set to None to avoid FK constraint error
            update_data["featured_image_id"] = None
    
    for key, value in update_data.items():
        setattr(db_news, key, value)
    
    # Update tags if provided
    if tag_ids is not None:
        tags = db.query(model.Tag).filter(model.Tag.id.in_(tag_ids)).all()
        db_news.tags = tags
    
    # Update related news if provided
    if related_news_ids is not None:
        related_news = db.query(model.News).filter(model.News.id.in_(related_news_ids)).all()
        db_news.related_news = related_news
    
    # Update related events if provided
    if related_event_ids is not None:
        related_events = db.query(model.Event).filter(model.Event.id.in_(related_event_ids)).all()
        db_news.related_events = related_events
    
    db.commit()
    db.refresh(db_news)
    return db_news

@news_router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_news(news_id: int, db: Session = Depends(get_db)):
    db_news = db.query(model.News).filter(model.News.id == news_id).first()
    if db_news is None:
        raise HTTPException(status_code=404, detail="News article not found")
    db.delete(db_news)
    db.commit()
    return None

# Event endpoints
@event_router.post("/", response_model=schema.EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(event: schema.EventCreate, db: Session = Depends(get_db)):
    # Check if slug already exists and handle it properly
    if event.slug:
        existing_event = db.query(model.Event).filter(model.Event.slug == event.slug).first()
        if existing_event:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Event with slug '{event.slug}' already exists. Please choose a different slug."
            )
    else:
        # Generate slug if not provided
        event.slug = generate_slug(event.title, db, model.Event)
    
    # Extract tags and related items for later processing - handle None values
    tag_ids = event.tag_ids if event.tag_ids is not None else []
    related_news_ids = event.related_news_ids if event.related_news_ids is not None else []
    related_event_ids = event.related_event_ids if event.related_event_ids is not None else []
    
    # Remove relationship fields from the dict
    event_data = event.dict(exclude={"tag_ids", "related_news_ids", "related_event_ids"})
    
    # Ensure registration_link is a string, not HttpUrl object
    if isinstance(event_data.get("registration_link"), HttpUrl):
        event_data["registration_link"] = str(event_data["registration_link"])
    
    # Validate category_id if provided
    if event_data.get("category_id"):
        category = db.query(model.Category).filter(model.Category.id == event_data["category_id"]).first()
        if not category:
            # If category doesn't exist, set to None to avoid FK constraint error
            event_data["category_id"] = None
    
    # Validate featured_image_id if provided
    if event_data.get("featured_image_id"):
        from storage.model import StoredFile
        stored_file = db.query(StoredFile).filter(StoredFile.id == event_data["featured_image_id"]).first()
        if not stored_file:
            # If file doesn't exist, set to None to avoid FK constraint error
            event_data["featured_image_id"] = None
    
    # Create event
    db_event = model.Event(**event_data)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    # Add tags - only if we have tag IDs and they're valid
    if tag_ids:
        tags = db.query(model.Tag).filter(model.Tag.id.in_(tag_ids)).all()
        if tags:  # Only assign if we found valid tags
            db_event.tags = tags
    
    # Add related news - only proceed if we have IDs and they exist
    if related_news_ids:
        related_news = db.query(model.News).filter(model.News.id.in_(related_news_ids)).all()
        if related_news:  # Only assign if we found valid related news
            db_event.related_news = related_news
    
    # Add related events - only proceed if we have IDs and they exist
    if related_event_ids:
        related_events = db.query(model.Event).filter(model.Event.id.in_(related_event_ids)).all()
        if related_events:  # Only assign if we found valid related events
            db_event.related_events = related_events
    
    db.commit()
    db.refresh(db_event)
    return db_event

@event_router.get("/", response_model=List[schema.EventResponse])
def read_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    events = db.query(model.Event).offset(skip).limit(limit).all()
    return events

@event_router.get("/{event_id}", response_model=schema.EventResponse)
def read_event(event_id: int, db: Session = Depends(get_db)):
    db_event = db.query(model.Event).filter(model.Event.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return db_event

@event_router.patch("/{event_id}", response_model=schema.EventResponse)
def update_event(event_id: int, event: schema.EventUpdate, db: Session = Depends(get_db)):
    db_event = db.query(model.Event).filter(model.Event.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Update slug if title is changed
    if event.title and event.title != db_event.title:
        if not event.slug:  # Only auto-generate slug if not explicitly provided
            event.slug = generate_slug(event.title, db, model.Event, event_id)
    
    # Extract relationship fields
    tag_ids = event.tag_ids
    related_news_ids = event.related_news_ids
    related_event_ids = event.related_event_ids
    
    # Update fields
    update_data = event.dict(exclude_unset=True, exclude={"tag_ids", "related_news_ids", "related_event_ids"})
    
    # Validate category_id if it's being updated
    if "category_id" in update_data and update_data["category_id"] is not None:
        category = db.query(model.Category).filter(model.Category.id == update_data["category_id"]).first()
        if not category:
            # If category doesn't exist, set to None
            update_data["category_id"] = None
    
    # Validate featured_image_id if it's being updated
    if "featured_image_id" in update_data and update_data["featured_image_id"] is not None:
        from storage.model import StoredFile
        stored_file = db.query(StoredFile).filter(StoredFile.id == update_data["featured_image_id"]).first()
        if not stored_file:
            # If file doesn't exist, set to None to avoid FK constraint error
            update_data["featured_image_id"] = None
    
    for key, value in update_data.items():
        setattr(db_event, key, value)
    
    # Update tags if provided
    if tag_ids is not None:
        tags = db.query(model.Tag).filter(model.Tag.id.in_(tag_ids)).all()
        db_event.tags = tags
    
    # Update related news if provided
    if related_news_ids is not None:
        related_news = db.query(model.News).filter(model.News.id.in_(related_news_ids)).all()
        db_event.related_news = related_news
    
    # Update related events if provided
    if related_event_ids is not None:
        related_events = db.query(model.Event).filter(model.Event.id.in_(related_event_ids)).all()
        db_event.related_events = related_events
    
    db.commit()
    db.refresh(db_event)
    return db_event

@event_router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    db_event = db.query(model.Event).filter(model.Event.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(db_event)
    db.commit()
    return None
