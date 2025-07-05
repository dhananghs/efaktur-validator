#!/usr/bin/env python3
"""
Test script for E-Faktur Validation Service
Demonstrates how to use the API with sample data
"""

import requests
import json
import os

def test_health_check():
    """Test the health check endpoint"""
    try:
        response = requests.get("http://localhost:8000/")
        print("✅ Health check passed")
        print(f"Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_validation_with_sample_file():
    """Test validation with a sample file"""
    # Check if sample file exists
    sample_file = "files/mock-faktur-pajak.jpg"
    if not os.path.exists(sample_file):
        print(f"❌ Sample file not found: {sample_file}")
        print("Please ensure you have a sample e-Faktur file to test with")
        return False
    
    try:
        url = "http://localhost:8000/validate-efaktur"
        
        with open(sample_file, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Validation test passed")
            print("Response:")
            print(json.dumps(result, indent=2))
            return True
        else:
            print(f"❌ Validation test failed with status {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Validation test failed: {e}")
        return False

def test_invalid_file():
    """Test with invalid file type"""
    try:
        url = "http://localhost:8000/validate-efaktur"
        
        # Create a dummy text file
        files = {"file": ("test.txt", "This is not a PDF", "text/plain")}
        response = requests.post(url, files=files)
        
        if response.status_code == 400:
            print("✅ Invalid file test passed (correctly rejected)")
            return True
        else:
            print(f"❌ Invalid file test failed - expected 400, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Invalid file test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing E-Faktur Validation Service")
    print("=" * 50)
    
    # Check if service is running
    print("\n1. Testing health check...")
    if not test_health_check():
        print("\n❌ Service is not running. Please start the service first:")
        print("   python main.py")
        return
    
    # Test invalid file
    print("\n2. Testing invalid file rejection...")
    test_invalid_file()
    
    # Test validation
    print("\n3. Testing e-Faktur validation...")
    test_validation_with_sample_file()
    
    print("\n" + "=" * 50)
    print("🏁 Testing completed!")

if __name__ == "__main__":
    main() 