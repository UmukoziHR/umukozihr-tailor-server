#!/usr/bin/env python3
"""
Database and Core System Tests for UmukoziHR Resume Tailor v1.2
"""
import os
import sys
import time
import requests
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_database_connection():
    """Test database connection and tables"""
    print("🔄 Testing database connection...")
    try:
        from app.db.database import engine, DATABASE_URL
        print(f"Database URL: {DATABASE_URL}")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful!")
        
        # Check tables
        from app.db.models import User, Profile, Job, Run
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"📊 Tables found: {tables}")
        
        required_tables = ['users', 'profiles', 'jobs', 'runs']
        missing_tables = [t for t in required_tables if t not in tables]
        
        if not missing_tables:
            print("✅ All required tables exist!")
            return True
        else:
            print(f"❌ Missing tables: {missing_tables}")
            return False
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_models():
    """Test database models"""
    print("🔄 Testing database models...")
    try:
        from app.db.database import SessionLocal
        from app.db.models import User
        from app.auth.auth import hash_password
        
        db = SessionLocal()
        
        # Try to create a test user
        test_email = "testmodel@example.com"
        
        # Clean up any existing test user
        existing = db.query(User).filter(User.email == test_email).first()
        if existing:
            db.delete(existing)
            db.commit()
        
        # Create new test user
        user = User(
            email=test_email,
            password_hash=hash_password("testpassword")
        )
        db.add(user)
        db.commit()
        
        # Verify user was created
        created_user = db.query(User).filter(User.email == test_email).first()
        if created_user:
            print(f"✅ User model works! ID: {created_user.id}")
            
            # Clean up
            db.delete(created_user)
            db.commit()
            db.close()
            return True
        else:
            print("❌ Failed to create user")
            db.close()
            return False
            
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False

def test_auth_system():
    """Test authentication functions"""
    print("🔄 Testing authentication system...")
    try:
        from app.auth.auth import hash_password, verify_password, create_access_token, verify_token
        
        # Test password hashing
        password = "testpassword123"
        hashed = hash_password(password)
        
        if verify_password(password, hashed):
            print("✅ Password hashing/verification works!")
        else:
            print("❌ Password verification failed")
            return False
        
        # Test JWT tokens
        data = {"sub": "test-user-id", "email": "test@example.com"}
        token = create_access_token(data)
        
        payload = verify_token(token)
        if payload and payload.get("sub") == "test-user-id":
            print("✅ JWT token creation/verification works!")
            return True
        else:
            print("❌ JWT token verification failed")
            return False
            
    except Exception as e:
        print(f"❌ Auth system test failed: {e}")
        return False

def wait_for_server(max_retries=10):
    """Wait for server to be ready"""
    print("🔄 Waiting for server to be ready...")
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("✅ Server is ready!")
                return True
        except:
            pass
        
        print(f"   Retry {i+1}/{max_retries}...")
        time.sleep(2)
    
    print("❌ Server not ready after waiting")
    return False

def test_api_endpoints():
    """Test basic API endpoints"""
    print("🔄 Testing API endpoints...")
    
    if not wait_for_server():
        return False
    
    try:
        # Test health endpoint
        response = requests.get("http://localhost:8000/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health endpoint works!")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
        
        # Test signup
        signup_data = {
            "email": "testapi@example.com",
            "password": "testpassword123"
        }
        
        response = requests.post("http://localhost:8000/api/v1/auth/signup", json=signup_data, timeout=10)
        if response.status_code in [200, 201]:
            print("✅ Signup endpoint works!")
            token_data = response.json()
            access_token = token_data.get("access_token")
            
            # Test login
            login_data = {
                "email": "testapi@example.com",
                "password": "testpassword123"
            }
            
            response = requests.post("http://localhost:8000/api/v1/auth/login", json=login_data, timeout=10)
            if response.status_code == 200:
                print("✅ Login endpoint works!")
                return True
            else:
                print(f"❌ Login failed: {response.status_code} - {response.text}")
                return False
        else:
            print(f"❌ Signup failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ API endpoint test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("UmukoziHR Resume Tailor v1.2 - Core System Tests")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Database Connection
    results['database'] = test_database_connection()
    print()
    
    # Test 2: Database Models
    results['models'] = test_models()
    print()
    
    # Test 3: Authentication System
    results['auth_system'] = test_auth_system()
    print()
    
    # Test 4: API Endpoints
    results['api_endpoints'] = test_api_endpoints()
    print()
    
    # Summary
    print("=" * 60)
    print("CORE SYSTEM TEST RESULTS")
    print("=" * 60)
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name.upper().replace('_', ' ')}: {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    print(f"\nPassed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("🎉 All core system tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. System needs attention.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)