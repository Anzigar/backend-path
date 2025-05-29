from fastapi import APIRouter, Depends, HTTPException, Query, status, Form, Body
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from database import get_db
from . import model, schema
import datetime
from slugify import slugify
from sqlalchemy import func, or_, desc

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
    
    # Validate featured_image_id if provided
    if news_data.get("featured_image_id"):
        stored_file = db.query(model.StoredFile).filter(
            model.StoredFile.id == news_data["featured_image_id"]
        ).first()
        if not stored_file:
            # Set to None if the file doesn't exist
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
    # Generate slug if not provided
    if not event.slug:
        event.slug = generate_slug(event.title, db, model.Event)
    
    # Extract tags and related items for later processing - handle None values
    tag_ids = event.tag_ids if event.tag_ids is not None else []
    related_news_ids = event.related_news_ids if event.related_news_ids is not None else []
    related_event_ids = event.related_event_ids if event.related_event_ids is not None else []
    
    # Remove relationship fields from the dict
    event_data = event.dict(exclude={"tag_ids", "related_news_ids", "related_event_ids"})
    
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

@event_router.get("/", response_model=schema.EventListResponse)
def read_events(
    params: schema.ContentPaginationParams = Depends(),
    include_past: bool = False,
    db: Session = Depends(get_db)
):
    query = db.query(model.Event)
    
    # Apply filters
    if params.search:
        search = f"%{params.search}%"
        query = query.filter(or_(
            model.Event.title.ilike(search),
            model.Event.description.ilike(search),
            model.Event.summary.ilike(search),
            model.Event.venue.ilike(search),
            model.Event.location_address.ilike(search)
        ))
    
    if params.category_id:
        query = query.filter(model.Event.category_id == params.category_id)
    
    if params.tag_ids:
        query = query.join(model.Event.tags).filter(model.Tag.id.in_(params.tag_ids)).group_by(model.Event.id)
    
    if params.start_date:
        query = query.filter(model.Event.start_date >= params.start_date)
    
    if params.end_date:
        query = query.filter(model.Event.start_date <= params.end_date)
    
    if params.is_published is not None:
        query = query.filter(model.Event.is_published == params.is_published)
    
    # Exclude past events unless specifically requested
    if not include_past:
        query = query.filter(model.Event.start_date >= datetime.datetime.now())
    
    # Count total before pagination
    total = query.count()
    
    # Apply pagination and eager loading
    items = query.order_by(model.Event.start_date)\
        .options(
            joinedload(model.Event.category),
            joinedload(model.Event.tags),
            joinedload(model.Event.featured_image)
        )\
        .offset(params.skip)\
        .limit(params.limit)\
        .all()
    
    return {"items": items, "total": total}

@event_router.get("/{slug}", response_model=schema.EventDetailResponse)
def read_event_by_slug(slug: str, db: Session = Depends(get_db)):
    db_event = db.query(model.Event)\
        .filter(model.Event.slug == slug)\
        .options(
            joinedload(model.Event.category),
            joinedload(model.Event.tags),
            joinedload(model.Event.featured_image),
            joinedload(model.Event.comments).filter(model.Comment.is_approved == True),
            joinedload(model.Event.related_news),
            joinedload(model.Event.related_events)
        )\
        .first()
    
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Increment view count
    db_event.view_count += 1
    db.commit()
    
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
    
    # Update event fields
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

# Comment endpoints
# Make comment creation more robust
@comment_router.post("/", response_model=schema.CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(comment: schema.CommentCreate, db: Session = Depends(get_db)):
    # Validate content exists based on content type
    if comment.content_type == schema.ContentType.NEWS:
        if comment.news_id is None:
            raise HTTPException(status_code=400, detail="News ID is required for news comments")
        news = db.query(model.News).filter(model.News.id == comment.news_id).first()
        if not news:
            raise HTTPException(status_code=404, detail="News article not found")
    elif comment.content_type == schema.ContentType.EVENT:
        if comment.event_id is None:
            raise HTTPException(status_code=400, detail="Event ID is required for event comments")
        event = db.query(model.Event).filter(model.Event.id == comment.event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
    
    # Create comment with only the provided data
    comment_data = {k: v for k, v in comment.dict().items() if v is not None}
    db_comment = model.Comment(**comment_data)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

@comment_router.get("/", response_model=List[schema.CommentResponse])
def read_comments(
    content_type: Optional[schema.ContentType] = None,
    news_id: Optional[int] = None,
    event_id: Optional[int] = None,
    approved_only: bool = True,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    query = db.query(model.Comment)
    
    # Apply filters only if they're provided
    if content_type is not None:
        query = query.filter(model.Comment.content_type == content_type)
    
    if news_id is not None:
        query = query.filter(model.Comment.news_id == news_id)
    
    if event_id is not None:
        query = query.filter(model.Comment.event_id == event_id)
    
    if approved_only:
        query = query.filter(model.Comment.is_approved == True)
    
    return query.order_by(model.Comment.created_at.desc()).offset(skip).limit(limit).all()

@comment_router.patch("/{comment_id}/approve", response_model=schema.CommentResponse)
def approve_comment(comment_id: int, db: Session = Depends(get_db)):
    db_comment = db.query(model.Comment).filter(model.Comment.id == comment_id).first()
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    db_comment.is_approved = True
    db.commit()
    db.refresh(db_comment)
    return db_comment

@comment_router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    db_comment = db.query(model.Comment).filter(model.Comment.id == comment_id).first()
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    db.delete(db_comment)
    db.commit()
    return None
