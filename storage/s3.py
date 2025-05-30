import os
import uuid
from typing import Optional, BinaryIO, Dict, Any, Tuple, List
import logging
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException, UploadFile
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

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
        self.use_local_storage = os.getenv("USE_LOCAL_STORAGE", "false").lower() == "true"
        self.local_storage_path = os.getenv("LOCAL_STORAGE_PATH", "local_uploads")
        
        # Log environment variable presence (not values for security)
        logger.info(f"AWS_ACCESS_KEY_ID: {'Set' if self.aws_access_key else 'Not set'}")
        logger.info(f"AWS_SECRET_ACCESS_KEY: {'Set' if self.aws_secret_key else 'Not set'}")
        logger.info(f"AWS_REGION: {self.region_name}")
        logger.info(f"S3_BUCKET_NAME: {self.bucket_name or 'Not set'}")
        logger.info(f"USE_LOCAL_STORAGE: {self.use_local_storage}")
        logger.info(f"LOCAL_STORAGE_PATH: {self.local_storage_path}")
        
        # Ensure local storage directory exists
        if self.use_local_storage or not all([self.aws_access_key, self.aws_secret_key, self.bucket_name]):
            os.makedirs(self.local_storage_path, exist_ok=True)
            logger.info(f"Local storage configured at: {self.local_storage_path}")
            self.use_local_storage = True
            
            # Log missing environment variables
            if not self.aws_access_key:
                logger.warning("AWS_ACCESS_KEY_ID is missing")
            if not self.aws_secret_key:
                logger.warning("AWS_SECRET_ACCESS_KEY is missing")
            if not self.bucket_name:
                logger.warning("S3_BUCKET_NAME is missing")
        
        logger.info(f"Storage mode: {'Local Storage' if self.use_local_storage else 'AWS S3'}")
        self.s3_client = None if self.use_local_storage else self._get_s3_client()
        
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
            if self.bucket_name:
                client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"Successfully connected to S3 bucket: {self.bucket_name}")
                return client
            else:
                logger.error("S3 bucket name is not configured")
                self.use_local_storage = True
                return None
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Failed to create S3 client: {str(e)}")
            self.use_local_storage = True
            return None
    
    async def upload_file(
        self, 
        file: UploadFile, 
        folder: str = "uploads",
        custom_filename: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str], Dict[str, Any]]:
        """
        Upload a file to S3 bucket or local storage.
        
        Args:
            file: The file to upload
            folder: The folder within the bucket to store the file
            custom_filename: Optional custom filename, if not provided a UUID will be generated
            
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
            
            # Use local storage if configured or S3 client initialization failed
            if self.use_local_storage:
                success, message, file_url, metadata = await self._save_to_local_storage(
                    file_content, file_path, content_type, file.filename
                )
            else:
                success, message, file_url, metadata = self._upload_to_s3(
                    file_content, file_path, content_type, file.filename
                )
            
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

    async def _save_to_local_storage(self, content, file_path, content_type, original_filename):
        """Save file to local storage instead of S3."""
        try:
            full_path = os.path.join(self.local_storage_path, file_path)
            # Create directories if needed
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Write file
            with open(full_path, "wb") as f:
                f.write(content)
                
            # Generate a local URL
            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            file_url = f"{base_url}/local-files/{file_path}"
            
            metadata = {
                "filename": os.path.basename(file_path),
                "original_filename": original_filename,
                "file_path": file_path,
                "content_type": content_type,
                "size_bytes": len(content),
                "bucket_name": "local_storage",
                "public_url": file_url
            }
            
            logger.info(f"File saved locally: {file_path}")
            return True, "File saved to local storage", file_url, metadata
        except Exception as e:
            logger.error(f"Error saving to local storage: {str(e)}")
            return False, f"Error saving to local storage: {str(e)}", None, {}

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
        Delete a file from S3 bucket or local storage.
        
        Args:
            file_key: The key/path of the file
            bucket_name: The bucket name (defaults to the configured bucket)
            
        Returns:
            Tuple of (success status, message)
        """
        bucket_name = bucket_name or self.bucket_name
        
        # If using local storage or the bucket is 'local_storage'
        if self.use_local_storage or bucket_name == "local_storage":
            return self._delete_local_file(file_key)
        
        if not self.s3_client:
            return False, "S3 client not initialized"
            
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
    
    def _delete_local_file(self, file_path):
        """Delete a file from local storage."""
        try:
            full_path = os.path.join(self.local_storage_path, file_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                return True, "File deleted successfully"
            else:
                return False, "File not found"
        except Exception as e:
            logger.error(f"Error deleting local file: {str(e)}")
            return False, f"Error deleting local file: {str(e)}"
    
    def get_file_url(self, key: str, expires_in: int = 3600) -> Tuple[bool, str, Optional[str]]:
        """
        Generate a pre-signed URL for a file in S3.
        
        Args:
            key: The key (path) of the file in S3
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Tuple of (success status, message, url if successful)
        """
        if self.use_local_storage:
            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            return True, "URL generated for local file", f"{base_url}/local-files/{key}"
        
        if not self.s3_client:
            return False, "S3 client not initialized", None
            
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
        List files in a folder/prefix in the S3 bucket or local storage.
        
        Args:
            prefix: The prefix/folder to list files from
            max_items: Maximum number of items to return
            
        Returns:
            Tuple of (success status, message, list of file data if successful)
        """
        if self.use_local_storage:
            return self._list_local_files(prefix, max_items)
        
        if not self.s3_client:
            return False, "S3 client not initialized", None
            
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
    
    def _list_local_files(self, prefix: str, max_items: int):
        """List files in local storage."""
        try:
            prefix_path = os.path.join(self.local_storage_path, prefix)
            
            if not os.path.exists(prefix_path):
                return True, "No files found", []
                
            files = []
            count = 0
            
            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            
            # Walk through directories
            for root, _, filenames in os.walk(prefix_path):
                for filename in filenames:
                    if count >= max_items:
                        break
                        
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, self.local_storage_path)
                    
                    files.append({
                        'key': rel_path,
                        'size': os.path.getsize(file_path),
                        'last_modified': os.path.getmtime(file_path),
                        'url': f"{base_url}/local-files/{rel_path}"
                    })
                    count += 1
            
            return True, f"Found {len(files)} files", files
        except Exception as e:
            logger.error(f"Error listing local files: {str(e)}")
            return False, f"Error listing local files: {str(e)}", None

# Create a singleton instance
storage = S3Storage()
