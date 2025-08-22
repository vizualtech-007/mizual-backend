import os
from botocore.exceptions import NoCredentialsError, ClientError
import json
from .logger import logger
import io
from typing import Union, BinaryIO

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "image-edit-bucket")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL") # For local development with MinIO
S3_PUBLIC_URL = os.environ.get("S3_PUBLIC_URL", S3_ENDPOINT_URL)
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY")

# Environment-based folder structure
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")
S3_FOLDER_PREFIX = f"{ENVIRONMENT}/"

# Global variable to hold the client, initialized to None
s3_client = None

def get_s3_client():
    """Creates and caches the S3 client to be loaded lazily with optimized configuration."""
    global s3_client
    if s3_client is None:
        import boto3
        from botocore.config import Config
        
        # Optimize S3 client configuration for better performance
        config = Config(
            max_pool_connections=10,  # Connection pooling
            retries={'max_attempts': 3, 'mode': 'adaptive'},  # Retry configuration
            tcp_keepalive=True  # Keep connections alive
        )
        
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY_ID,
            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
            config=config
        )
    return s3_client

def create_bucket_if_not_exists():
    """Ensures the S3 bucket exists. For Backblaze B2, bucket policy is set via dashboard."""
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=S3_BUCKET_NAME)
        logger.info(f"S3 bucket '{S3_BUCKET_NAME}' exists and is accessible")
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.error(f"Bucket '{S3_BUCKET_NAME}' not found")
            raise Exception(f"Bucket '{S3_BUCKET_NAME}' does not exist. Please create it in Backblaze B2 dashboard.")
        else:
            raise
    
    # Note: Backblaze B2 doesn't support put_bucket_policy
    # Bucket permissions are managed via B2 dashboard (already set to public)

def upload_file_to_s3(file_data: Union[bytes, BinaryIO], file_name: str) -> str:
    """Uploads a file to S3 and returns its URL. Supports both bytes and stream inputs for memory efficiency."""
    client = get_s3_client()
    try:
        # Add environment prefix to file path
        full_key = S3_FOLDER_PREFIX + file_name
        
        # Support both bytes and stream uploads for memory efficiency
        if isinstance(file_data, bytes):
            # For small files or when we already have bytes in memory
            body = file_data
        else:
            # For large files, use stream to avoid loading entire file in memory
            body = file_data
            
        client.put_object(
            Bucket=S3_BUCKET_NAME, 
            Key=full_key, 
            Body=body,
            ContentType='image/png'  # Optimize with proper content type
        )
        return f"{S3_PUBLIC_URL}/{S3_BUCKET_NAME}/{full_key}"
    except NoCredentialsError:
        raise Exception("AWS credentials not found. Please configure your environment.")
    except Exception as e:
        raise e

def upload_stream_to_s3(stream: BinaryIO, file_name: str) -> str:
    """Upload from stream directly to S3 without loading into memory."""
    return upload_file_to_s3(stream, file_name)