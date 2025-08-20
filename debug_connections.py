#!/usr/bin/env python3
"""
Debug script to test service connections with category support
Run this to identify connection issues before starting the main app

Usage:
  python debug_connections.py                    # Test all connections
  python debug_connections.py <category>         # Test specific category
  python debug_connections.py --help             # Show help

Categories: env, database, redis, storage, api
"""

import os
from src.logger import logger
import sys
import asyncio
import psycopg
import redis
import boto3
from botocore.exceptions import ClientError
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def print_header(title):
    logger.info(f"\n{'='*50}")
    logger.info(f"🔍 {title}")
    logger.info(f"{'='*50}")

def print_success(message):
    logger.info(f"✅ {message}")

def print_error(message):
    logger.info(f"❌ {message}")

def print_info(message):
    logger.info(f"ℹ️  {message}")

def test_environment_variables():
    """Test environment variables"""
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
    
    all_present = True
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
            all_present = False
    
    return all_present

def test_database_connection():
    """Test PostgreSQL connection"""
    print_header("DATABASE CONNECTION (PostgreSQL)")
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print_error("DATABASE_URL not set")
        return False
    
    # Convert postgresql:// to postgresql+psycopg:// to use psycopg driver instead of psycopg2
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    
    print_info(f"Connecting to: {database_url[:50]}...")
    
    try:
        # Test connection with SSL settings for Supabase
        conn = psycopg.connect(database_url, autocommit=True)
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
    """Test Redis connection"""
    print_header("REDIS CONNECTION")
    
    broker_url = os.getenv('CELERY_BROKER_URL')
    if not broker_url:
        print_error("CELERY_BROKER_URL not set")
        return False
    
    print_info(f"Connecting to: {broker_url[:50]}...")
    
    try:
        # Apply the same SSL handling as in tasks.py
        test_broker_url = broker_url
        if test_broker_url.startswith('rediss://'):
            # Only add ssl_cert_reqs=none if it's not already present
            if 'ssl_cert_reqs' not in test_broker_url:
                test_broker_url = test_broker_url + ('&' if '?' in test_broker_url else '?') + 'ssl_cert_reqs=none'
            else:
                # Replace CERT_NONE with none (the format redis-py expects)
                test_broker_url = test_broker_url.replace('ssl_cert_reqs=CERT_NONE', 'ssl_cert_reqs=none')
        
        print_info(f"Modified URL: {test_broker_url[:50]}...")
        
        # Parse Redis URL (support both redis:// and rediss://)
        if test_broker_url.startswith('redis://') or test_broker_url.startswith('rediss://'):
            r = redis.from_url(test_broker_url)
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
    """Test S3 connection"""
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

async def test_bfl_api():
    """Test BFL API connection"""
    print_header("BFL API CONNECTION")
    
    api_key = os.getenv('BFL_API_KEY')
    flux_api_url = os.getenv('FLUX_API_URL', 'https://api.bfl.ai/v1/flux-kontext-pro')
    
    if not api_key:
        print_error("BFL_API_KEY not set")
        return False
    
    print_info(f"API Key: {api_key[:10]}...")
    print_info(f"API URL: {flux_api_url}")
    
    try:
        # Use the same headers as in flux_api.py
        headers = {
            "accept": "application/json",
            "x-key": api_key,
            "Content-Type": "application/json"
        }
        
        # Create a minimal test payload (similar to actual usage)
        test_data = {
            "prompt": "test connection",
            "input_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",  # 1x1 transparent PNG
            "safety_tolerance": 2
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                flux_api_url,
                headers=headers,
                json=test_data
            )
            
            if response.status_code == 200:
                print_success("BFL API connection successful!")
                response_data = response.json()
                if response_data.get("id"):
                    print_success(f"Got request ID: {response_data.get('id')}")
                return True
            elif response.status_code == 401:
                print_error("BFL API authentication failed - check your API key")
                return False
            elif response.status_code == 400:
                print_error("BFL API request format issue - but connection works")
                print_info("This might be due to test data format, but API is reachable")
                return True  # Connection works, just test data issue
            else:
                print_error(f"BFL API returned status: {response.status_code}")
                print_info(f"Response: {response.text[:200]}...")
                return False
                
    except Exception as e:
        print_error(f"BFL API connection failed: {str(e)}")
        return False

# Test categories
CATEGORIES = {
    "env": {
        "name": "Environment Variables",
        "test": test_environment_variables,
        "async": False
    },
    "database": {
        "name": "Database (PostgreSQL)",
        "test": test_database_connection,
        "async": False
    },
    "redis": {
        "name": "Redis/Celery",
        "test": test_redis_connection,
        "async": False
    },
    "storage": {
        "name": "S3/Backblaze B2 Storage",
        "test": test_s3_connection,
        "async": False
    },
    "api": {
        "name": "BFL API",
        "test": test_bfl_api,
        "async": True
    }
}

async def run_category(category_key):
    """Run tests for a specific category"""
    if category_key not in CATEGORIES:
        print_error(f"Unknown category: {category_key}")
        print_info(f"Available categories: {', '.join(CATEGORIES.keys())}")
        return False
    
    category = CATEGORIES[category_key]
    print_info(f"Testing {category['name']}...\n")
    
    if category['async']:
        result = await category['test']()
    else:
        result = category['test']()
    
    if result:
        print_success(f"🎉 {category['name']} test passed!")
    else:
        print_error(f"⚠️  {category['name']} test failed!")
    
    return result

async def run_all_tests():
    """Run all connection tests"""
    print_header("MIZUAL BACKEND CONNECTION DEBUG")
    print_info("Testing all service connections...")
    
    results = {}
    for key, category in CATEGORIES.items():
        print_info(f"Testing {category['name']}...")
        if category['async']:
            result = await category['test']()
        else:
            result = category['test']()
        results[category['name']] = result
        logger.info()  # Add spacing between tests
    
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
        return True
    else:
        print_error("\n💥 Some connections failed. Fix these issues before starting the app.")
        return False

def show_usage():
    """Show usage instructions"""
    logger.info("Usage:")
    logger.info("  python debug_connections.py                    # Test all connections")
    logger.info("  python debug_connections.py <category>         # Test specific category")
    logger.info("  python debug_connections.py --help             # Show this help")
    logger.info()
    logger.info("Available categories:")
    for key, category in CATEGORIES.items():
        logger.info(f"  {key:<10} - {category['name']}")
    logger.info()
    logger.info("Examples:")
    logger.info("  python debug_connections.py env               # Test only environment variables")
    logger.info("  python debug_connections.py database          # Test only database")
    logger.info("  python debug_connections.py storage           # Test only S3 storage")
    logger.info("  python debug_connections.py api               # Test only BFL API")

async def main():
    """Main function with category support"""
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["-h", "--help", "help"]:
            show_usage()
            return
        
        # Run specific category
        success = await run_category(arg)
        sys.exit(0 if success else 1)
    else:
        # Run all tests
        success = await run_all_tests()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())