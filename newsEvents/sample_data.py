import logging
from sqlalchemy.orm import Session
from database import get_db
from .model import Category, ContentType, Tag

logger = logging.getLogger(__name__)

# Sample categories for events and news
SAMPLE_CATEGORIES = [
    {"name": "Technology", "description": "Tech news and events", "content_type": ContentType.BOTH},
    {"name": "Business", "description": "Business updates and conferences", "content_type": ContentType.BOTH},
    {"name": "Health", "description": "Health-related topics and events", "content_type": ContentType.BOTH},
    {"name": "Education", "description": "Educational news and workshops", "content_type": ContentType.BOTH},
    {"name": "Entertainment", "description": "Entertainment news and events", "content_type": ContentType.BOTH},
]

# Sample tags
SAMPLE_TAGS = [
    {"name": "Innovation", "description": "Cutting-edge developments"},
    {"name": "Startup", "description": "Startup companies and founders"},
    {"name": "AI", "description": "Artificial Intelligence"},
    {"name": "Sustainability", "description": "Environmental sustainability"},
    {"name": "Community", "description": "Community-focused initiatives"},
]

def initialize_sample_categories():
    """
    Initialize sample categories in the database for development purposes.
    This function checks if there are any categories in the database, and if not,
    creates sample categories for testing.
    """
    db: Session = next(get_db())
    
    # Check if we already have categories
    category_count = db.query(Category).count()
    if category_count > 0:
        logger.info(f"Database already has {category_count} categories, skipping sample data creation")
        return
        
    logger.info("No categories found in database, creating sample categories for development")
    
    # Create sample categories
    for sample in SAMPLE_CATEGORIES:
        try:
            category = Category(
                name=sample["name"],
                description=sample["description"],
                content_type=sample["content_type"]
            )
            db.add(category)
            logger.info(f"Created sample category: {sample['name']}")
        except Exception as e:
            logger.error(f"Error creating sample category '{sample['name']}': {str(e)}")
    
    # Commit all changes
    try:
        db.commit()
        logger.info(f"Successfully created {len(SAMPLE_CATEGORIES)} sample categories")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit sample categories: {str(e)}")

def initialize_sample_tags():
    """
    Initialize sample tags in the database for development purposes.
    """
    db: Session = next(get_db())
    
    # Check if we already have tags
    tag_count = db.query(Tag).count()
    if tag_count > 0:
        logger.info(f"Database already has {tag_count} tags, skipping sample data creation")
        return
        
    logger.info("No tags found in database, creating sample tags for development")
    
    # Create sample tags
    for sample in SAMPLE_TAGS:
        try:
            tag = Tag(
                name=sample["name"],
                description=sample["description"]
            )
            db.add(tag)
            logger.info(f"Created sample tag: {sample['name']}")
        except Exception as e:
            logger.error(f"Error creating sample tag '{sample['name']}': {str(e)}")
    
    # Commit all changes
    try:
        db.commit()
        logger.info(f"Successfully created {len(SAMPLE_TAGS)} sample tags")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit sample tags: {str(e)}")

def initialize_sample_data():
    """Initialize all sample data for news and events module"""
    try:
        initialize_sample_categories()
        initialize_sample_tags()
    except Exception as e:
        logger.error(f"Error initializing sample data: {str(e)}")
