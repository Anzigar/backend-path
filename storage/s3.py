import os
import uuid
from typing import Optional, BinaryIO, Dict, Any, Tuple, List
import logging
import boto3
import io
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException, UploadFile
from dotenv import load_dotenv
from PIL import Image  # Add Pillow for image compression

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Image compression settings
DEFAULT_JPEG_QUALITY = int(os.getenv("JPEG_COMPRESSION_QUALITY", "85"))
DEFAULT_PNG_COMPRESSION = int(os.getenv("PNG_COMPRESSION_LEVEL", "6"))
MAX_IMAGE_DIMENSION = int(os.getenv("MAX_IMAGE_DIMENSION", "2000"))
COMPRESS_IMAGES = os.getenv("COMPRESS_IMAGES", "true").lower() == "true"

# Image content types
IMAGE_CONTENT_TYPES = [
    "image/jpeg", 
    "image/jpg", 
    "image/png", 
    "image/webp"
]

class S3Storage:
    """S3 storage utility for managing file uploads to AWS S3."""
    
    def __init__(self):
        """Initialize S3 client using environment variables."""
        # Log environment variable status
        logger.info("Checking S3 storage configuration...")
        
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region_name = os.getenv("AWS_REGION", "us-east-2")
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        
        # Force S3 usage only - no local storage fallback
        self.use_local_storage = False
        
        # Log environment variable presence (not values for security)
        logger.info(f"AWS_ACCESS_KEY_ID: {'Set' if self.aws_access_key else 'Not set'}")
        logger.info(f"AWS_SECRET_ACCESS_KEY: {'Set' if self.aws_secret_key else 'Not set'}")
        logger.info(f"AWS_REGION: {self.region_name}")
        logger.info(f"S3_BUCKET_NAME: {self.bucket_name or 'Not set'}")
        
        # Validate required S3 configuration
        if not all([self.aws_access_key, self.aws_secret_key, self.bucket_name]):
            missing = []
            if not self.aws_access_key: missing.append("AWS_ACCESS_KEY_ID")
            if not self.aws_secret_key: missing.append("AWS_SECRET_ACCESS_KEY")
            if not self.bucket_name: missing.append("S3_BUCKET_NAME")
            
            error_msg = f"Missing required S3 configuration: {', '.join(missing)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        logger.info("Storage mode: AWS S3 only (no local fallback)")
        self.s3_client = self._get_s3_client()
        
    def _get_s3_client(self):
        """Create and return an S3 client."""
        try:
            client = boto3.client(
                "s3",
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.region_name
            )
            
            # Validate bucket exists and is accessible
            client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Successfully connected to S3 bucket: {self.bucket_name}")
            return client
        except (ClientError, NoCredentialsError) as e:
            error_msg = f"Failed to create S3 client: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    async def upload_file(
        self, 
        file: UploadFile, 
        folder: str = "uploads",
        custom_filename: Optional[str] = None,
        compress_image: bool = COMPRESS_IMAGES
    ) -> Tuple[bool, str, Optional[str], Dict[str, Any]]:
        """
        Upload a file to S3 bucket with optional image compression.
        
        Args:
            file: The file to upload
            folder: The folder within the bucket to store the file
            custom_filename: Optional custom filename, if not provided a UUID will be generated
            compress_image: Whether to compress images before upload
            
        Returns:
            Tuple of (success status, message, url if successful, metadata)
        """
        try:
            # Generate unique filename if not provided
            if file.filename is None:
                file.filename = "unnamed_file"
                logger.warning("File has no filename, using default")
                
            file_extension = os.path.splitext(file.filename)[1].lower() if '.' in file.filename else ""
            filename = custom_filename or f"{uuid.uuid4().hex}{file_extension}"
            
            # Construct path
            file_path = f"{folder}/{filename}"
            
            # Read file content
            file_content = await file.read()
            if not file_content:
                logger.error("File content is empty")
                return False, "File content is empty", None, {}
            
            content_type = file.content_type or "application/octet-stream"
            
            # Apply image compression if enabled and file is an image
            original_size = len(file_content)
            compressed = False
            
            if compress_image and content_type in IMAGE_CONTENT_TYPES:
                try:
                    logger.info(f"Compressing image: {file.filename}")
                    file_content, content_type = self._compress_image(file_content, content_type, file_extension)
                    compressed = True
                    logger.info(f"Image compression: Original size: {original_size} bytes, "
                                f"Compressed size: {len(file_content)} bytes, "
                                f"Reduction: {(original_size - len(file_content)) / original_size * 100:.1f}%")
                except Exception as e:
                    logger.warning(f"Image compression failed: {str(e)}. Using original image.")
            
            # Upload to S3
            success, message, file_url, metadata = self._upload_to_s3(
                file_content, file_path, content_type, file.filename
            )
            
            # Add compression info to metadata
            if compressed:
                metadata["compressed"] = True
                metadata["original_size"] = original_size
                metadata["compression_ratio"] = f"{original_size / len(file_content):.2f}x"
            
            return success, message, file_url, metadata
                
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            return False, f"Error uploading file: {str(e)}", None, {}
        finally:
            # Reset file position for potential reuse
            try:
                await file.seek(0)
            except:
                pass
    
    def _compress_image(self, image_data: bytes, content_type: str, file_extension: str) -> Tuple[bytes, str]:
        """Compress image data while preserving format."""
        # Open the image using PIL
        img = Image.open(io.BytesIO(image_data))
        
        # Resize if the image is too large
        if max(img.size) > MAX_IMAGE_DIMENSION:
            # Calculate new dimensions while preserving aspect ratio
            ratio = min(MAX_IMAGE_DIMENSION / max(img.size[0], img.size[1]), 1.0)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # Determine output format based on content type
        if content_type in ["image/jpeg", "image/jpg"]:
            output_format = "JPEG"
            output_ext = ".jpg"
            output_content_type = "image/jpeg"
            quality = DEFAULT_JPEG_QUALITY
            output_params = {"quality": quality, "optimize": True}
        elif content_type == "image/png":
            output_format = "PNG"
            output_ext = ".png"
            output_content_type = "image/png"
            quality = DEFAULT_PNG_COMPRESSION
            output_params = {"optimize": True, "compress_level": quality}
        elif content_type == "image/webp":
            output_format = "WEBP"
            output_ext = ".webp"
            output_content_type = "image/webp"
            quality = DEFAULT_JPEG_QUALITY
            output_params = {"quality": quality}
        else:
            # Not a supported format for compression, return original
            return image_data, content_type
        
        # Create a BytesIO object to store the compressed image
        output = io.BytesIO()
        
        # Save the image with compression
        img.save(output, format=output_format, **output_params)
        
        # Get the compressed image data
        output.seek(0)
        compressed_data = output.getvalue()
        
        return compressed_data, output_content_type

    def _upload_to_s3(self, content, file_path, content_type, original_filename):
        """Upload file to S3 bucket."""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=content_type
            )
            
            # Generate URL for the uploaded file
            file_url = f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{file_path}"
            
            metadata = {
                "filename": os.path.basename(file_path),
                "original_filename": original_filename,
                "file_path": file_path,
                "content_type": content_type,
                "size_bytes": len(content),
                "bucket_name": self.bucket_name,
                "public_url": file_url
            }
            
            logger.info(f"File uploaded to S3: {file_path}")
            return True, "File uploaded successfully", file_url, metadata
        except ClientError as e:
            logger.error(f"S3 client error: {str(e)}")
            return False, f"S3 client error: {str(e)}", None, {}
    
    def delete_file(self, file_key: str, bucket_name: str = None) -> Tuple[bool, str]:
        """
        Delete a file from S3 bucket.
        
        Args:
            file_key: The key/path of the file
            bucket_name: The bucket name (defaults to the configured bucket)
            
        Returns:
            Tuple of (success status, message)
        """
        bucket_name = bucket_name or self.bucket_name
        
        try:
            # Delete from S3
            response = self.s3_client.delete_object(
                Bucket=bucket_name,
                Key=file_key
            )
            
            return True, "File deleted successfully"
                
        except ClientError as e:
            logger.error(f"S3 client error: {str(e)}")
            return False, f"S3 client error: {str(e)}"
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False, f"Error deleting file: {str(e)}"
    
    def get_file_url(self, key: str, expires_in: int = 3600) -> Tuple[bool, str, Optional[str]]:
        """
        Generate a pre-signed URL for a file in S3.
        
        Args:
            key: The key (path) of the file in S3
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Tuple of (success status, message, url if successful)
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=expires_in
            )
            return True, "URL generated successfully", url
        except Exception as e:
            logger.error(f"Error generating pre-signed URL: {str(e)}")
            return False, f"Error generating pre-signed URL: {str(e)}", None
    
    def list_files(self, prefix: str = "", max_items: int = 1000) -> Tuple[bool, str, Optional[List[Dict[str, Any]]]]:
        """
        List files in a folder/prefix in the S3 bucket.
        
        Args:
            prefix: The prefix/folder to list files from
            max_items: Maximum number of items to return
            
        Returns:
            Tuple of (success status, message, list of file data if successful)
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_items
            )
            
            if 'Contents' not in response:
                return True, "No files found", []
                
            files = []
            for item in response['Contents']:
                files.append({
                    'key': item['Key'],
                    'size': item['Size'],
                    'last_modified': item['LastModified'],
                    'url': f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{item['Key']}"
                })
                
            return True, f"Found {len(files)} files", files
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            return False, f"Error listing files: {str(e)}", None

# Create a singleton instance
storage = S3Storage()
