from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
import uuid
import logging  # Add logging import
import os  # Add import for accessing environment variables
from database import get_db
from . import schema, model
from storage.model import StoredFile

# Configure logger
logger = logging.getLogger(__name__)  # Add logger definition

# Create router instances
news_router = APIRouter(prefix="/news", tags=["news"])
event_router = APIRouter(prefix="/events", tags=["events"])
category_router = APIRouter(prefix="/categories", tags=["categories"])
tag_router = APIRouter(prefix="/tags", tags=["tags"])
comment_router = APIRouter(prefix="/comments", tags=["comments"])

# Helper functions (moved from crud.py)
def get_category(db: Session, category_id: int) -> model.Category:
    """Get a category by ID"""
    category = db.query(model.Category).filter(model.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

def get_event(db: Session, event_id: int) -> model.Event:
    """Get an event by ID"""
    event = db.query(model.Event).options(
        joinedload(model.Event.featured_image)  # Eager load the featured image
    ).filter(model.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

# Event routes
@event_router.post("/", response_model=schema.EventResponse)
def create_event(
    event: schema.EventCreate,
    db: Session = Depends(get_db)
):
    """Create a new event"""
    # Generate slug if not provided
    if not event.slug:
        event.slug = f"{'-'.join(event.title.lower().split()[:5])}-{uuid.uuid4().hex[:8]}"
    
    # Handle category validation
    if event.category_id:
        category = db.query(model.Category).filter(model.Category.id == event.category_id).first()
        if not category:
            # Get available categories
            available_categories = db.query(
                model.Category.id,
                model.Category.name
            ).order_by(model.Category.id).all()
            
            # Format available categories list for error message
            category_list = []
            for cat in available_categories:
                category_list.append(f"ID: {cat.id} - {cat.name}")
            
            # Option 1: Return helpful error with suggestion
            # Find a suitable default category (first one or "Other" if exists)
            default_category = db.query(model.Category).filter(
                model.Category.name.ilike("other")
            ).first() or db.query(model.Category).first()
            
            if default_category:
                # Use default category and log warning
                logger.warning(
                    f"Invalid category ID {event.category_id} provided for event '{event.title}', "
                    f"using default category '{default_category.name}' (ID: {default_category.id})"
                )
                event.category_id = default_category.id
            else:
                # No categories exist, so raise error
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Category with ID {event.category_id} not found in database. "
                        "Please use an existing category ID.\n\n"
                        "Available categories:\n" + "\n".join(category_list)
                    )
                )
    
    # Validate featured_image_id exists in stored_files if provided
    if event.featured_image_id:
        # Check if featured_image_id exists
        image = db.query(StoredFile).filter(StoredFile.id == event.featured_image_id).first()
        if not image:
            # Get list of available images to help the user
            available_images = db.query(
                StoredFile.id, 
                StoredFile.filename, 
                StoredFile.file_type
            ).order_by(StoredFile.id).limit(10).all()
            
            # Format available images list
            image_list = []
            for img in available_images:
                image_list.append(f"ID: {img.id} - {img.filename} ({img.file_type})")
            
            # Get the highest ID
            max_id = db.query(func.max(StoredFile.id)).scalar() or 0
            
            # Check if we should use a default image instead (similar to category fallback)
            use_default_fallback = os.getenv("USE_DEFAULT_IMAGE_FALLBACK", "false").lower() == "true"
            if use_default_fallback and available_images:
                # Find suitable default image - prefer type that matches folder name or first image
                default_image = None
                
                # Try to find image of matching type first (e.g., NEWS_IMAGE for news content)
                if folder_type := event.file_type if hasattr(event, 'file_type') else None:
                    matching_images = [img for img in available_images if img.file_type.value == folder_type]
                    if matching_images:
                        default_image = matching_images[0]
                
                # If no matching type, use first available
                if not default_image and available_images:
                    default_image = available_images[0]
                
                if default_image:
                    logger.warning(
                        f"Invalid image ID {event.featured_image_id} provided for event '{event.title}', "
                        f"using default image '{default_image.filename}' (ID: {default_image.id})"
                    )
                    event.featured_image_id = default_image.id
                    # Continue with event creation
                else:
                    raise HTTPException(
                        status_code=400, 
                        detail=(
                            f"Featured image with ID {event.featured_image_id} not found in stored files. "
                            f"The highest available image ID is {max_id}. "
                            "Please upload the image first or use an existing image ID.\n\n"
                            "Available images (first 10):\n" + "\n".join(image_list)
                        )
                    )
            else:
                # No fallback, raise error as usual
                raise HTTPException(
                    status_code=400, 
                    detail=(
                        f"Featured image with ID {event.featured_image_id} not found in stored files. "
                        f"The highest available image ID is {max_id}. "
                        "Please upload the image first or use an existing image ID.\n\n"
                        "Available images (first 10):\n" + "\n".join(image_list)
                    )
                )
    
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

@event_router.get("/{event_id}", response_model=schema.EventResponse)
def read_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Get event by ID"""
    return get_event(db, event_id)

@event_router.get("/", response_model=schema.EventList)
def read_events(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get list of events with optional filtering"""
    query = db.query(model.Event)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            model.Event.title.ilike(search_term) | 
            model.Event.description.ilike(search_term)
        )
    
    if category_id:
        query = query.filter(model.Event.category_id == category_id)
    
    total = query.count()
    events = query.offset(skip).limit(limit).all()
    
    return {"items": events, "total": total}

# Category routes
@category_router.post("/", response_model=schema.CategoryResponse)
def create_category(category: schema.CategoryCreate, db: Session = Depends(get_db)):
    """Create a new category"""
    db_category = model.Category(
        name=category.name,
        description=category.description
    )
    
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@category_router.get("/", response_model=List[schema.CategoryResponse])
def read_categories(db: Session = Depends(get_db)):
    """Get all categories"""
    return db.query(model.Category).all()

@category_router.put("/{category_id}", response_model=schema.CategoryResponse)
def update_category(
    category_id: int,
    category: schema.CategoryCreate,
    db: Session = Depends(get_db)
):
    """Update a category"""
    db_category = get_category(db, category_id)
    
    # Update fields
    update_data = category.dict()
    for key, value in update_data.items():
        setattr(db_category, key, value)
    
    db.commit()
    db.refresh(db_category)
    return db_category

# Similar endpoints for tags and comments can be added
# ...
