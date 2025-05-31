import os
import logging
import base64
import io
from sqlalchemy.orm import Session
from database import get_db
from .model import StoredFile, FileType
from .s3 import storage
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Sample image types and descriptions
SAMPLE_IMAGES = [
    {"type": FileType.BLOG_IMAGE, "name": "Sample Blog Image 1", "color": "#3498db", "text": "Blog 1"},
    {"type": FileType.BLOG_IMAGE, "name": "Sample Blog Image 2", "color": "#e74c3c", "text": "Blog 2"},
    {"type": FileType.NEWS_IMAGE, "name": "Sample News Image 1", "color": "#2ecc71", "text": "News 1"},
    {"type": FileType.NEWS_IMAGE, "name": "Sample News Image 2", "color": "#f39c12", "text": "News 2"},
    {"type": FileType.OTHER, "name": "Sample Image", "color": "#9b59b6", "text": "Other"}
]

def initialize_sample_images():
    """
    Initialize sample images in the database for development purposes.
    This function checks if there are any images in the database, and if not,
    creates some sample placeholder images for testing.
    """
    db: Session = next(get_db())
    
    # Check if we already have images
    image_count = db.query(StoredFile).count()
    if image_count > 0:
        logger.info(f"Database already has {image_count} images, skipping sample data creation")
        return
        
    logger.info("No images found in database, creating sample images for development")
    
    # Create sample images
    for idx, sample in enumerate(SAMPLE_IMAGES, 1):
        try:
            # Create a simple colored image with text
            img_bytes = create_sample_image(
                sample["color"], 
                sample["text"], 
                width=800, 
                height=600
            )
            
            # Generate a unique filename
            filename = f"sample_{sample['type'].value}_{idx}.png"
            file_type = sample["type"]
            
            # Save to S3 (use a mock file object)
            file_obj = MockUploadFile(
                filename=filename, 
                content_type="image/png", 
                file=io.BytesIO(img_bytes)
            )
            
            # Upload directly to S3
            folder = file_type.value
            file_path = f"{folder}/{filename}"
            
            # Use the S3 client directly
            storage.s3_client.put_object(
                Bucket=storage.bucket_name,
                Key=file_path,
                Body=img_bytes,
                ContentType="image/png"
            )
            
            # Generate URL for the uploaded file
            file_url = f"https://{storage.bucket_name}.s3.{storage.region_name}.amazonaws.com/{file_path}"
            
            # Save metadata in database
            db_file = StoredFile(
                filename=filename,
                original_filename=filename,
                file_path=file_path,
                file_type=file_type,
                content_type="image/png",
                size_bytes=len(img_bytes),
                bucket_name=storage.bucket_name,
                public_url=file_url
            )
            
            db.add(db_file)
            logger.info(f"Created sample image: {filename}")
            
        except Exception as e:
            logger.error(f"Error creating sample image: {str(e)}")
    
    # Commit all changes
    try:
        db.commit()
        logger.info(f"Successfully created {len(SAMPLE_IMAGES)} sample images")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit sample images: {str(e)}")

def create_sample_image(color: str, text: str, width: int = 800, height: int = 600) -> bytes:
    """Create a simple colored image with text."""
    # Create a new image with the specified color
    image = Image.new('RGB', (width, height), color)
    draw = ImageDraw.Draw(image)
    
    # Add text
    try:
        # Try to use a system font, but don't fail if not available
        font = ImageFont.truetype("Arial", 60)
    except IOError:
        font = ImageFont.load_default()
    
    # Calculate text position to center it
    text_width, text_height = draw.textsize(text, font=font) if hasattr(draw, 'textsize') else (200, 60)
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    # Draw text in white
    draw.text(position, text, fill="white", font=font)
    
    # Save to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

class MockUploadFile:
    """Mock UploadFile for testing purposes."""
    def __init__(self, filename, content_type, file):
        self.filename = filename
        self.content_type = content_type
        self.file = file
        
    async def read(self):
        return self.file.getvalue()
        
    async def seek(self, position):
        self.file.seek(position)
