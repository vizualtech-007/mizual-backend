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
    """Ensures the S3 bucket exists and applies a public read policy."""
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            s3_client.create_bucket(Bucket=S3_BUCKET_NAME)
        else:
            raise

    # Set a public read policy on the bucket
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{S3_BUCKET_NAME}/*"]
            }
        ]
    }
    s3_client.put_bucket_policy(Bucket=S3_BUCKET_NAME, Policy=json.dumps(policy))

def upload_file_to_s3(file_bytes: bytes, file_name: str) -> str:
    """Uploads a file to S3 and returns its URL."""
    try:
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=file_name, Body=file_bytes)
        return f"{S3_PUBLIC_URL}/{S3_BUCKET_NAME}/{file_name}"
    except NoCredentialsError:
        raise Exception("AWS credentials not found. Please configure your environment.")
    except Exception as e:
        raise e
