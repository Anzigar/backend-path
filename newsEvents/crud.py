from sqlalchemy.orm import Session
from . import model, schema
import uuid

def update_category(db: Session, category_id: int, category_update: schema.CategoryCreate) -> model.Category:
    """Update a category"""
    db_category = get_category(db, category_id)
    
    # Update fields
    update_data = category_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)
    
    db.commit()
    db.refresh(db_category)
    return db_category

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