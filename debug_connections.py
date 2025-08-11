#!/usr/bin/env python3
"""
Debug script to test all service connections on Render
Run this to identify connection issues before starting the main app
"""

import os
import sys
import psycopg2
import redis
import boto3
from botocore.exceptions import ClientError
import httpx

def print_header(title):
    print(f"\n{'='*50}")
    print(f"🔍 {title}")
    print(f"{'='*50}")

def print_success(message):
    print(f"✅ {message}")

def print_error(message):
    print(f"❌ {message}")

def print_info(message):
    print(f"ℹ️  {message}")

def test_environment_variables():
    print_header("ENVIRONMENT VARIABLES")
    
    required_vars = [
        'DATABASE_URL',
        'CELERY_BROKER_URL', 
        'CELERY_RESULT_BACKEND',
        'BFL_API_KEY',
        'S3_BUCKET_NAME',
        'S3_ENDPOINT_URL',
        'S3_ACCESS_KEY_ID',
        'S3_SECRET_ACCESS_KEY'
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'KEY' in var or 'URL' in var or 'PASSWORD' in var:
                masked = value[:10] + '...' + value[-5:] if len(value) > 15 else '***'
                print_success(f"{var}: {masked}")
            else:
                print_success(f"{var}: {value}")
        else:
            print_error(f"{var}: NOT SET")

def test_database_connection():
    print_header("DATABASE CONNECTION (PostgreSQL)")
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print_error("DATABASE_URL not set")
        return False
    
    print_info(f"Connecting to: {database_url[:50]}...")
    
    try:
        # Test connection with SSL settings for Supabase
        conn = psycopg2.connect(database_url, sslmode='require')
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print_success(f"Connected successfully!")
        print_info(f"PostgreSQL version: {version[:50]}...")
        
        # Test basic operations
        cursor.execute("SELECT 1 as test;")
        result = cursor.fetchone()[0]
        print_success(f"Query test passed: {result}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print_error(f"Database connection failed: {str(e)}")
        
        # If direct connection fails, suggest pooled connection
        if "Network is unreachable" in str(e) and "db." in database_url:
            print_info("💡 Try using pooled connection instead of direct connection")
            print_info("   Change: db.PROJECT.supabase.co:5432")
            print_info("   To: aws-0-us-east-2.pooler.supabase.com:6543")
        
        return False

def test_redis_connection():
    print_header("REDIS CONNECTION")
    
    broker_url = os.getenv('CELERY_BROKER_URL')
    if not broker_url:
        print_error("CELERY_BROKER_URL not set")
        return False
    
    print_info(f"Connecting to: {broker_url[:50]}...")
    
    try:
        # Parse Redis URL (support both redis:// and rediss://)
        if broker_url.startswith('redis://') or broker_url.startswith('rediss://'):
            r = redis.from_url(broker_url, ssl_cert_reqs=None)
        else:
            print_error("Invalid Redis URL format")
            return False
        
        # Test connection
        r.ping()
        print_success("Redis connection successful!")
        
        # Test basic operations
        r.set('test_key', 'test_value')
        value = r.get('test_key')
        print_success(f"Redis read/write test passed: {value.decode()}")
        r.delete('test_key')
        
        return True
        
    except Exception as e:
        print_error(f"Redis connection failed: {str(e)}")
        return False

def test_s3_connection():
    print_header("S3/BACKBLAZE B2 CONNECTION")
    
    bucket_name = os.getenv('S3_BUCKET_NAME')
    endpoint_url = os.getenv('S3_ENDPOINT_URL')
    access_key = os.getenv('S3_ACCESS_KEY_ID')
    secret_key = os.getenv('S3_SECRET_ACCESS_KEY')
    
    if not all([bucket_name, endpoint_url, access_key, secret_key]):
        print_error("S3 environment variables not complete")
        return False
    
    print_info(f"Bucket: {bucket_name}")
    print_info(f"Endpoint: {endpoint_url}")
    print_info(f"Access Key: {access_key}")
    
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='us-east-1'  # B2 doesn't care about region
        )
        
        # Test bucket access
        s3_client.head_bucket(Bucket=bucket_name)
        print_success("S3 bucket access successful!")
        
        # Test list objects
        response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        print_success("S3 list objects successful!")
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print_error(f"S3 connection failed: {error_code} - {str(e)}")
        return False
    except Exception as e:
        print_error(f"S3 connection failed: {str(e)}")
        return False

def test_bfl_api():
    print_header("BFL API CONNECTION")
    
    api_key = os.getenv('BFL_API_KEY')
    if not api_key:
        print_error("BFL_API_KEY not set")
        return False
    
    print_info(f"API Key: {api_key[:10]}...")
    
    try:
        # Test BFL API endpoint
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # Simple API test (adjust URL as needed)
        with httpx.Client() as client:
            response = client.get(
                'https://api.bfl.ai/v1/models',  # or appropriate test endpoint
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                print_success("BFL API connection successful!")
                return True
            else:
                print_error(f"BFL API returned status: {response.status_code}")
                return False
                
    except Exception as e:
        print_error(f"BFL API connection failed: {str(e)}")
        return False

def main():
    print_header("MIZUAL BACKEND CONNECTION DEBUG")
    print_info("Testing all service connections...")
    
    results = {
        'Environment Variables': True,  # Always run this
        'Database': test_database_connection(),
        'Redis': test_redis_connection(),
        'S3/B2 Storage': test_s3_connection(),
        'BFL API': test_bfl_api()
    }
    
    # Test environment variables
    test_environment_variables()
    
    print_header("SUMMARY")
    all_passed = True
    for service, passed in results.items():
        if passed:
            print_success(f"{service}: PASSED")
        else:
            print_error(f"{service}: FAILED")
            all_passed = False
    
    if all_passed:
        print_success("\n🎉 All connections successful! Your app should start normally.")
        sys.exit(0)
    else:
        print_error("\n💥 Some connections failed. Fix these issues before starting the app.")
        sys.exit(1)

if __name__ == "__main__":
    main()