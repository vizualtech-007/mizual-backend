#!/usr/bin/env python3
"""
Test script for Feature 2: User Feedback System
This script tests the feedback API endpoints
"""

import requests
import json

# Configuration
BASE_URL = "https://mizual-backend-dev.onrender.com"  # Your dev environment
# BASE_URL = "http://localhost:10000"  # For local testing

def test_feedback_system():
    """Test the feedback system end-to-end"""
    print("🧪 Testing Feature 2: User Feedback System")
    print("=" * 50)
    
    # Test data - you'll need a real edit UUID from your system
    test_edit_uuid = "test-uuid-12345"  # Replace with actual edit UUID
    
    # Test 1: Submit feedback
    print("1. Testing feedback submission...")
    feedback_data = {
        "edit_uuid": test_edit_uuid,
        "rating": 5,
        "feedback_text": "Great result! The AI edit looks amazing."
    }
    
    try:
        response = requests.post(f"{BASE_URL}/feedback/", json=feedback_data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Feedback submission successful!")
        elif response.status_code == 404:
            print("⚠️  Edit not found (expected if using test UUID)")
        elif response.status_code == 409:
            print("⚠️  Feedback already exists for this edit")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    
    print()
    
    # Test 2: Try to submit duplicate feedback
    print("2. Testing duplicate feedback prevention...")
    try:
        response = requests.post(f"{BASE_URL}/feedback/", json=feedback_data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 409:
            print("✅ Duplicate prevention working!")
        else:
            print(f"⚠️  Expected 409, got {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    
    print()
    
    # Test 3: Get feedback for edit
    print("3. Testing feedback retrieval...")
    try:
        response = requests.get(f"{BASE_URL}/feedback/{test_edit_uuid}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Feedback retrieval successful!")
        elif response.status_code == 404:
            print("⚠️  No feedback found (expected if using test UUID)")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    
    print()
    
    # Test 4: Test validation
    print("4. Testing input validation...")
    invalid_feedback = {
        "edit_uuid": test_edit_uuid,
        "rating": 6,  # Invalid rating (should be 1-5)
        "feedback_text": "Test"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/feedback/", json=invalid_feedback)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 422:
            print("✅ Input validation working!")
        else:
            print(f"⚠️  Expected 422, got {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    
    print()
    print("🎉 Feedback system testing completed!")
    print("\nTo test with real data:")
    print("1. Create an edit through /edit-image/ endpoint")
    print("2. Wait for it to complete")
    print("3. Use the edit UUID to test feedback submission")

if __name__ == "__main__":
    test_feedback_system()