from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import traceback
from database import get_db
from . import model, schema
from .s3 import storage  # Import the S3Storage singleton

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/storage",
    tags=["storage"]
)

@router.post("/upload", response_model=schema.FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    file_type: schema.FileType = Form(schema.FileType.OTHER),
    related_entity_id: Optional[int] = Form(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Upload a file directly to S3 and store its metadata in the database"""
    try:
        # Check if the file exists
        if not file:
            logger.error("No file provided")
            raise HTTPException(status_code=400, detail="No file provided")
        
        logger.info(f"Processing S3 upload for file: {file.filename or 'unnamed_file'}")
        
        # Use the S3Storage class to upload the file
        success, message, file_url, metadata = await storage.upload_file(
            file=file,
            folder=file_type.value,  # Use file type as folder name
            custom_filename=None  # Let S3Storage generate a unique name
        )
        
        if not success:
            logger.error(f"S3 upload failed: {message}")
            raise HTTPException(status_code=500, detail=message)
        
        # Store metadata in database
        db_file = model.StoredFile(
            filename=metadata["filename"],
            original_filename=metadata["original_filename"],
            file_path=metadata["file_path"],
            file_type=file_type,
            content_type=metadata["content_type"],
            size_bytes=metadata["size_bytes"],
            bucket_name=metadata["bucket_name"],
            public_url=metadata["public_url"],
            related_entity_id=related_entity_id
        )
        
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        logger.info(f"File uploaded to S3 successful: {db_file.filename}")
        return db_file
        
    except HTTPException:
        # Re-raise HTTP exceptions as they're already properly formatted
        raise
    except ValueError as e:
        # Handle S3 configuration errors
        logger.error(f"S3 configuration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"S3 storage not properly configured: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 upload error: {str(e)}"
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
        # Use S3Storage to delete the file
        success, message = storage.delete_file(
            file_key=db_file.file_path,
            bucket_name=db_file.bucket_name
        )
        
        if not success:
            logger.error(message)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )
        
        # Delete from database
        db.delete(db_file)
        db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )
