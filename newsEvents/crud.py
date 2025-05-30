from sqlalchemy.orm import Session
from . import model, schema

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