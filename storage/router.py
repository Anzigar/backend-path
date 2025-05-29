from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError
import os
import uuid
import logging
from database import get_db
from . import model, schema
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/storage",
    tags=["storage"]
)

# Configure AWS
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("AWS_REGION", "us-east-1")

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=S3_REGION
)

def get_unique_filename(original_filename):
    """Generate a unique filename to avoid overwriting files in S3"""
    ext = os.path.splitext(original_filename)[1]
    return f"{uuid.uuid4().hex}{ext}"

@router.post("/upload", response_model=schema.FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    file_type: schema.FileType = Form(schema.FileType.OTHER),
    related_entity_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a file to S3 and store its metadata in the database"""
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed"
        )
    
    try:
        # Generate unique filename
        unique_filename = get_unique_filename(file.filename)
        
        # Set folder based on file type
        folder = file_type.value
        file_path = f"{folder}/{unique_filename}"
        
        # Upload to S3
        content = await file.read()
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=file_path,
            Body=content,
            ContentType=file.content_type,
        )
        
        # Generate public URL
        public_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{file_path}"
        
        # Store metadata in database
        db_file = model.StoredFile(
            filename=unique_filename,
            original_filename=file.filename,
            file_path=file_path,
            file_type=file_type,
            content_type=file.content_type,
            size_bytes=len(content),
            bucket_name=S3_BUCKET,
            public_url=public_url,
            related_entity_id=related_entity_id
        )
        
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        return db_file
        
    except ClientError as e:
        logging.error(f"AWS S3 error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to S3: {str(e)}"
        )
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error occurred: {str(e)}"
        )

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
