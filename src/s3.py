import boto3
import os
from botocore.exceptions import NoCredentialsError, ClientError
import json

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "image-edit-bucket")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL") # For local development with MinIO
S3_PUBLIC_URL = os.environ.get("S3_PUBLIC_URL", S3_ENDPOINT_URL)
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY")

s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=S3_ACCESS_KEY_ID,
    aws_secret_access_key=S3_SECRET_ACCESS_KEY
)

def create_bucket_if_not_exists():
    """Ensures the S3 bucket exists. For Backblaze B2, bucket policy is set via dashboard."""
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
        print(f"✅ S3 bucket '{S3_BUCKET_NAME}' exists and is accessible")
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            print(f"❌ Bucket '{S3_BUCKET_NAME}' not found")
            raise Exception(f"Bucket '{S3_BUCKET_NAME}' does not exist. Please create it in Backblaze B2 dashboard.")
        else:
            raise
    
    # Note: Backblaze B2 doesn't support put_bucket_policy
    # Bucket permissions are managed via B2 dashboard (already set to public)

def upload_file_to_s3(file_bytes: bytes, file_name: str) -> str:
    """Uploads a file to S3 and returns its URL."""
    try:
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=file_name, Body=file_bytes)
        return f"{S3_PUBLIC_URL}/{S3_BUCKET_NAME}/{file_name}"
    except NoCredentialsError:
        raise Exception("AWS credentials not found. Please configure your environment.")
    except Exception as e:
        raise e
