from fastapi import APIRouter, Depends, HTTPException, Query, status, Form, Body
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from database import get_db
from . import model, schema
from newsEvents.model import Comment, ContentType, Tag
from storage.model import StoredFile
import datetime
from slugify import slugify
from sqlalchemy import func, or_, desc
import re

# Create routers
blog_router = APIRouter(
    prefix="/blogs",
    tags=["blogs"]
)

blog_category_router = APIRouter(
    prefix="/blog-categories",
    tags=["blog-categories"]
)

newsletter_router = APIRouter(
    prefix="/newsletter",
    tags=["newsletter"]
)

# Helper functions
def generate_slug(title, db, id=None):
    base_slug = slugify(title)
    slug = base_slug
    counter = 1
    
    # Check if slug exists while excluding the current item if updating
    query = db.query(model.Blog).filter(model.Blog.slug == slug)
    if id:
        query = query.filter(model.Blog.id != id)
    
    while query.first() is not None:
        slug = f"{base_slug}-{counter}"
        query = db.query(model.Blog).filter(model.Blog.slug == slug)
        if id:
            query = query.filter(model.Blog.id != id)
        counter += 1
    
    return slug

def calculate_reading_time(content):
    if not content:
        return 1
        
    # Remove HTML tags if present
    clean_text = re.sub(r'<.*?>', '', content)
    
    # Estimate reading time: avg 200-250 words per minute
    word_count = len(clean_text.split())
    minutes = round(word_count / 225)
    
    # Minimum 1 minute
    return max(1, minutes)

# Blog category endpoints
@blog_category_router.post("/", response_model=schema.BlogCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_blog_category(category: schema.BlogCategoryCreate, db: Session = Depends(get_db)):
    # Check if category with same name exists
    existing_category = db.query(model.BlogCategory).filter(model.BlogCategory.name == category.name).first()
    if existing_category:
        return existing_category  # Return the existing category instead of creating a duplicate
        
    # Generate slug if not provided
    if not category.slug:
        category.slug = slugify(category.name)
    
    db_category = model.BlogCategory(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@blog_category_router.get("/", response_model=List[schema.BlogCategoryResponse])
def read_blog_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    categories = db.query(model.BlogCategory).offset(skip).limit(limit).all()
    return categories

@blog_category_router.get("/{category_id}", response_model=schema.BlogCategoryResponse)
def read_blog_category(category_id: int, db: Session = Depends(get_db)):
    db_category = db.query(model.BlogCategory).filter(model.BlogCategory.id == category_id).first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category

# Blog endpoints
@blog_router.post("/", response_model=schema.BlogResponse, status_code=status.HTTP_201_CREATED)
def create_blog(blog: schema.BlogCreate, db: Session = Depends(get_db)):
    # Check if slug already exists and handle it properly
    if blog.slug:
        existing_blog = db.query(model.Blog).filter(model.Blog.slug == blog.slug).first()
        if existing_blog:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Blog post with slug '{blog.slug}' already exists. Please choose a different slug."
            )
    else:
        # Generate slug if not provided
        blog.slug = generate_slug(blog.title, db)
    
    # Set publish date if not provided
    if not blog.publish_date:
        blog.publish_date = datetime.datetime.now()
    
    # Validate foreign key references before proceeding
    blog_data = blog.dict(exclude={"tag_ids", "related_blog_ids"})
    
    # Check if category_id exists
    if blog_data.get("category_id"):
        category = db.query(model.BlogCategory).filter(model.BlogCategory.id == blog_data["category_id"]).first()
        if not category:
            # If category doesn't exist, set to None to avoid FK constraint error
            blog_data["category_id"] = None
    
    # Check if author_id exists in users table
    if blog_data.get("author_id"):
        from users.model import User
        user = db.query(User).filter(User.id == blog_data["author_id"]).first()
        if not user:
            # If user doesn't exist, set author_id to None and rely on author_name
            blog_data["author_id"] = None
    
    # Check if featured_image_id exists
    if blog_data.get("featured_image_id"):
        stored_file = db.query(StoredFile).filter(
            StoredFile.id == blog_data["featured_image_id"]
        ).first()
        if not stored_file:
            # If file doesn't exist, set to None to avoid FK constraint error
            blog_data["featured_image_id"] = None
    
    # Check if og_image_id exists
    if blog_data.get("og_image_id"):
        stored_file = db.query(model.StoredFile).filter(
            model.StoredFile.id == blog_data["og_image_id"]
        ).first()
        if not stored_file:
            # If file doesn't exist, set to None to avoid FK constraint error
            blog_data["og_image_id"] = None
            
    # Extract tags and related items for later processing
    tag_ids = blog.tag_ids if blog.tag_ids is not None else []
    related_blog_ids = blog.related_blog_ids if blog.related_blog_ids is not None else []
    
    # Calculate reading time
    reading_time = calculate_reading_time(blog.content)
    blog_data["reading_time_minutes"] = reading_time
    
    # Create blog with validated data
    db_blog = model.Blog(**blog_data)
    db.add(db_blog)
    db.commit()
    db.refresh(db_blog)
    
    # Add tags - only if we have tag IDs and they exist
    if tag_ids:
        tags = db.query(model.Tag).filter(model.Tag.id.in_(tag_ids)).all()
        if tags:
            db_blog.tags = tags
    
    # Add related blogs - only if we have IDs and they exist
    if related_blog_ids:
        related_blogs = db.query(model.Blog).filter(model.Blog.id.in_(related_blog_ids)).all()
        if related_blogs:
            db_blog.related_blogs = related_blogs
    
    db.commit()
    db.refresh(db_blog)
    return db_blog

@blog_router.get("/", response_model=schema.BlogListResponse)
def read_blogs(
    params: schema.BlogPaginationParams = Depends(),
    db: Session = Depends(get_db)
):
    query = db.query(model.Blog)
    
    # Apply filters
    if params.search:
        search = f"%{params.search}%"
        query = query.filter(or_(
            model.Blog.title.ilike(search),
            model.Blog.content.ilike(search),
            model.Blog.introduction.ilike(search),
            model.Blog.author_name.ilike(search)
        ))
    
    if params.category_id:
        query = query.filter(model.Blog.category_id == params.category_id)
    
    if params.author_id:
        query = query.filter(model.Blog.author_id == params.author_id)
    
    if params.tag_ids:
        query = query.join(model.Blog.tags).filter(model.Tag.id.in_(params.tag_ids)).group_by(model.Blog.id)
    
    if params.start_date:
        query = query.filter(func.date(model.Blog.publish_date) >= params.start_date)
    
    if params.end_date:
        query = query.filter(func.date(model.Blog.publish_date) <= params.end_date)
    
    if params.is_published is not None:
        query = query.filter(model.Blog.is_published == params.is_published)
    
    # Count total before pagination
    total = query.count()
    
    # Apply pagination and eager loading
    items = query.order_by(desc(model.Blog.publish_date))\
        .options(
            joinedload(model.Blog.category),
            joinedload(model.Blog.tags),
            joinedload(model.Blog.featured_image),
            joinedload(model.Blog.og_image)
        )\
        .offset(params.skip)\
        .limit(params.limit)\
        .all()
    
    return {"items": items, "total": total}

@blog_router.get("/{slug}", response_model=schema.BlogDetailResponse)
def read_blog_by_slug(slug: str, db: Session = Depends(get_db)):
    db_blog = db.query(model.Blog)\
        .filter(model.Blog.slug == slug)\
        .options(
            joinedload(model.Blog.category),
            joinedload(model.Blog.tags),
            joinedload(model.Blog.featured_image),
            joinedload(model.Blog.og_image),
            joinedload(model.Blog.comments).filter(Comment.is_approved == True),
            joinedload(model.Blog.related_blogs)
        )\
        .first()
    
    if db_blog is None:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Increment view count
    db_blog.view_count += 1
    db.commit()
    
    return db_blog

@blog_router.patch("/{blog_id}", response_model=schema.BlogResponse)
def update_blog(blog_id: int, blog: schema.BlogUpdate, db: Session = Depends(get_db)):
    db_blog = db.query(model.Blog).filter(model.Blog.id == blog_id).first()
    if db_blog is None:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Update slug if title is changed
    if blog.title and blog.title != db_blog.title:
        if not blog.slug:
            blog.slug = generate_slug(blog.title, db, blog_id)
    
    # Extract relationship fields
    tag_ids = blog.tag_ids
    related_blog_ids = blog.related_blog_ids
    
    # Update fields
    update_data = blog.dict(exclude_unset=True, exclude={"tag_ids", "related_blog_ids"})
    
    # Validate category_id if it's being updated
    if "category_id" in update_data and update_data["category_id"] is not None:
        category = db.query(model.BlogCategory).filter(model.BlogCategory.id == update_data["category_id"]).first()
        if not category:
            # If category doesn't exist, set to None
            update_data["category_id"] = None
    
    # Validate author_id if it's being updated
    if "author_id" in update_data and update_data["author_id"] is not None:
        from users.model import User
        user = db.query(User).filter(User.id == update_data["author_id"]).first()
        if not user:
            # If user doesn't exist, set author_id to None
            update_data["author_id"] = None
    
    # Validate featured_image_id if it's being updated
    if "featured_image_id" in update_data and update_data["featured_image_id"] is not None:
        stored_file = db.query(model.StoredFile).filter(
            model.StoredFile.id == update_data["featured_image_id"]
        ).first()
        if not stored_file:
            # If file doesn't exist, set to None to avoid FK constraint error
            update_data["featured_image_id"] = None
    
    # Validate og_image_id if it's being updated
    if "og_image_id" in update_data and update_data["og_image_id"] is not None:
        stored_file = db.query(model.StoredFile).filter(
            model.StoredFile.id == update_data["og_image_id"]
        ).first()
        if not stored_file:
            # If file doesn't exist, set to None to avoid FK constraint error
            update_data["og_image_id"] = None
    
    # Calculate reading time if content changes
    if blog.content:
        update_data["reading_time_minutes"] = calculate_reading_time(blog.content)
    
    for key, value in update_data.items():
        setattr(db_blog, key, value)
    
    # Update tags if provided
    if tag_ids is not None:
        tags = db.query(model.Tag).filter(model.Tag.id.in_(tag_ids)).all()
        db_blog.tags = tags
    
    # Update related blogs if provided
    if related_blog_ids is not None:
        related_blogs = db.query(model.Blog).filter(model.Blog.id.in_(related_blog_ids)).all()
        db_blog.related_blogs = related_blogs
    
    db.commit()
    db.refresh(db_blog)
    return db_blog

@blog_router.delete("/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blog(blog_id: int, db: Session = Depends(get_db)):
    db_blog = db.query(model.Blog).filter(model.Blog.id == blog_id).first()
    if db_blog is None:
        raise HTTPException(status_code=404, detail="Blog post not found")
    db.delete(db_blog)
    db.commit()
    return None

# Blog comments
@blog_router.post("/{blog_id}/comments", response_model=schema.CommentResponse)
def create_blog_comment(
    blog_id: int,
    comment: schema.BlogCommentCreate,
    db: Session = Depends(get_db)
):
    # Check if blog exists
    blog = db.query(model.Blog).filter(model.Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Create comment
    new_comment = Comment(
        content=comment.content,
        author_name=comment.author_name,
        author_email=comment.author_email,
        blog_id=blog_id,
        user_id=comment.user_id,
        content_type=ContentType.NEWS  # Reusing ContentType.NEWS for blog
    )
    
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment

@blog_router.get("/{blog_id}/comments", response_model=List[schema.CommentResponse])
def read_blog_comments(blog_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    blog = db.query(model.Blog).filter(model.Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    comments = db.query(Comment)\
        .filter(Comment.blog_id == blog_id, Comment.is_approved == True)\
        .order_by(Comment.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return comments

# Newsletter subscription endpoints
@newsletter_router.post("/subscribe", response_model=schema.SubscriptionResponse)
def create_subscription(subscription: schema.SubscriptionCreate, db: Session = Depends(get_db)):
    # Check if email already exists
    db_subscription = db.query(model.NewsletterSubscription)\
        .filter(model.NewsletterSubscription.email == subscription.email)\
        .first()
    
    if db_subscription:
        if db_subscription.is_active:
            # Return status message instead of error
            db_subscription.message = "This email is already subscribed to our newsletter."
            return db_subscription
        else:
            # Reactivate subscription
            db_subscription.is_active = True
            db_subscription.unsubscribed_at = None
            db_subscription.message = "Your subscription has been reactivated."
            db.commit()
            db.refresh(db_subscription)
            return db_subscription
    
    # Create new subscription
    import uuid
    new_subscription = model.NewsletterSubscription(
        email=subscription.email,
        name=subscription.name,
        source=subscription.source,
        confirmation_token=str(uuid.uuid4())
    )
    
    db.add(new_subscription)
    db.commit()
    db.refresh(new_subscription)
    
    # Here you would typically send a confirmation email
    # with the confirmation_token
    
    return new_subscription

@newsletter_router.get("/confirm/{token}")
def confirm_subscription(token: str, db: Session = Depends(get_db)):
    subscription = db.query(model.NewsletterSubscription)\
        .filter(model.NewsletterSubscription.confirmation_token == token)\
        .first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    
    subscription.is_confirmed = True
    subscription.confirmed_at = datetime.datetime.now()
    subscription.confirmation_token = None  # Clear token for security
    
    db.commit()
    
    return {"message": "Subscription confirmed successfully"}

@newsletter_router.post("/unsubscribe")
def unsubscribe(email: str = Form(...), db: Session = Depends(get_db)):
    subscription = db.query(model.NewsletterSubscription)\
        .filter(model.NewsletterSubscription.email == email)\
        .first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Email not found in our subscription list")
    
    subscription.is_active = False
    subscription.unsubscribed_at = datetime.datetime.now()
    
    db.commit()
    
    return {"message": "Successfully unsubscribed"}
