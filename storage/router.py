from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import os
import uuid
import logging
import traceback
from database import get_db
from . import model, schema
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/storage",
    tags=["storage"]
)

# Configure AWS with fallback to local storage
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("AWS_REGION", "us-east-2")
USE_LOCAL_STORAGE = os.getenv("USE_LOCAL_STORAGE", "false").lower() == "true"
LOCAL_STORAGE_PATH = os.getenv("LOCAL_STORAGE_PATH", "local_uploads")

# Ensure local storage directory exists
if USE_LOCAL_STORAGE or not all([AWS_ACCESS_KEY, AWS_SECRET_KEY, S3_BUCKET]):
    os.makedirs(LOCAL_STORAGE_PATH, exist_ok=True)
    logger.info(f"Local storage configured at: {LOCAL_STORAGE_PATH}")

# Check required configuration
if not all([AWS_ACCESS_KEY, AWS_SECRET_KEY, S3_BUCKET]) and not USE_LOCAL_STORAGE:
    logger.warning("Missing AWS credentials or S3 bucket name. Using local storage as fallback.")
    USE_LOCAL_STORAGE = True

# Initialize S3 client with error handling
s3_client = None
if not USE_LOCAL_STORAGE:
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=S3_REGION
        )
        # Validate S3 bucket exists and is accessible
        if S3_BUCKET:
            s3_client.head_bucket(Bucket=S3_BUCKET)
            logger.info(f"Successfully connected to S3 bucket: {S3_BUCKET}")
        else:
            logger.error("S3 bucket name is not configured")
            s3_client = None
            USE_LOCAL_STORAGE = True
    except (ClientError, NoCredentialsError) as e:
        logger.error(f"Failed to initialize S3 client: {str(e)}")
        s3_client = None
        USE_LOCAL_STORAGE = True

# Rest of helpers and functions
def get_unique_filename(original_filename):
    """Generate a unique filename to avoid overwriting files in S3"""
    if original_filename is None:
        original_filename = "unnamed_file"
    ext = os.path.splitext(original_filename)[1]
    return f"{uuid.uuid4().hex}{ext}"

def save_to_local_storage(contents, file_path, content_type):
    """Save file to local storage instead of S3"""
    try:
        full_path = os.path.join(LOCAL_STORAGE_PATH, file_path)
        # Create directories if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, "wb") as f:
            f.write(contents)
            
        # Generate a local URL
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        public_url = f"{base_url}/local-files/{file_path}"
        
        return full_path, public_url
    except Exception as e:
        logger.error(f"Error saving to local storage: {str(e)}")
        raise

@router.post("/upload", response_model=schema.FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    file_type: schema.FileType = Form(schema.FileType.OTHER),
    related_entity_id: Optional[int] = Form(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Upload a file to S3 or local storage and store its metadata in the database"""
    try:
        # Check if the file exists and has content
        if not file:
            logger.error("No file provided")
            raise HTTPException(status_code=400, detail="No file provided")
        
        if file.filename is None:
            file.filename = "unnamed_file"
            logger.warning("File has no filename, using default")
            
        logger.info(f"Processing upload for file: {file.filename}")
        
        # Get file content safely
        try:
            contents = await file.read()
        except Exception as e:
            logger.error(f"Error reading file contents: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
        
        if not contents:
            logger.error("File content is empty")
            raise HTTPException(status_code=400, detail="File content is empty")
        
        # Generate unique filename
        unique_filename = get_unique_filename(file.filename)
        
        # Set folder based on file type
        folder = file_type.value
        file_path = f"{folder}/{unique_filename}"
        
        # Set content type with fallback
        content_type = file.content_type or "application/octet-stream"
        
        # Determine storage method (S3 or local)
        using_s3 = s3_client is not None and not USE_LOCAL_STORAGE and S3_BUCKET
        
        if using_s3:
            logger.info(f"Uploading to S3 path: {file_path}")
            
            # Upload to S3
            try:
                if S3_BUCKET is None:
                    raise ValueError("S3 bucket name is None. Check your environment variables.")
                    
                s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=file_path,
                    Body=contents,
                    ContentType=content_type,
                )
                # Generate public URL
                public_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{file_path}"
                storage_path = file_path
                bucket_name = S3_BUCKET
                
            except (ClientError, ValueError) as e:
                logger.error(f"S3 upload error: {str(e)}")
                # Fall back to local storage
                logger.info("Falling back to local storage")
                storage_path, public_url = save_to_local_storage(contents, file_path, content_type)
                bucket_name = "local_storage"
        else:
            logger.info(f"Using local storage: {file_path}")
            storage_path, public_url = save_to_local_storage(contents, file_path, content_type)
            bucket_name = "local_storage"
        
        # Store metadata in database
        db_file = model.StoredFile(
            filename=unique_filename,
            original_filename=file.filename,
            file_path=storage_path,
            file_type=file_type,
            content_type=content_type,
            size_bytes=len(contents),
            bucket_name=bucket_name,
            public_url=public_url,
            related_entity_id=related_entity_id
        )
        
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        logger.info(f"File upload successful: {unique_filename}")
        return db_file
        
    except HTTPException as e:
        # Re-raise HTTP exceptions as they're already properly formatted
        raise
    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error occurred: {str(e)}"
        )
    finally:
        # Reset the file cursor position for potential reuse
        try:
            await file.seek(0)
        except:
            pass

@router.get("/files", response_model=schema.FileList)
def get_files(
    file_type: Optional[schema.FileType] = None,
    related_entity_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get list of files with optional filtering"""
    query = db.query(model.StoredFile)
    
    if file_type:
        query = query.filter(model.StoredFile.file_type == file_type)
        
    if related_entity_id:
        query = query.filter(model.StoredFile.related_entity_id == related_entity_id)
    
    total_count = query.count()
    files = query.offset(skip).limit(limit).all()
    
    return {
        "files": files,
        "count": total_count
    }

@router.get("/files/{file_id}", response_model=schema.FileUploadResponse)
def get_file(file_id: int, db: Session = Depends(get_db)):
    """Get a specific file by ID"""
    db_file = db.query(model.StoredFile).filter(model.StoredFile.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file

@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: int, db: Session = Depends(get_db)):
    """Delete file from S3 and database"""
    db_file = db.query(model.StoredFile).filter(model.StoredFile.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        # Delete from S3
        s3_client.delete_object(
            Bucket=db_file.bucket_name,
            Key=db_file.file_path
        )
        
        # Delete from database
        db.delete(db_file)
        db.commit()
        
    except ClientError as e:
        logging.error(f"AWS S3 error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file from S3: {str(e)}"
        )
