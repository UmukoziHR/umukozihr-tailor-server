#!/usr/bin/env python3
"""
API Testing Script for UmukoziHR Resume Tailor v1.2
Tests all endpoints and core functionality
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("🔄 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_auth_signup():
    """Test user signup"""
    print("🔄 Testing user signup...")
    try:
        payload = {
            "email": "test@umukozihr.com",
            "password": "testpassword123",
            "full_name": "Test User"
        }
        response = requests.post(f"{BASE_URL}/api/v1/auth/signup", json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code in [200, 201]:
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Signup failed: {e}")
        return False

def test_auth_login():
    """Test user login"""
    print("🔄 Testing user login...")
    try:
        payload = {
            "email": "test@umukozihr.com",
            "password": "testpassword123"
        }
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Login successful: {data.get('access_token', 'No token')[:20]}...")
            return data.get('access_token')
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return None

def test_profile_save(token=None):
    """Test profile save endpoint"""
    print("🔄 Testing profile save...")
    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        profile_data = {
            "name": "Jason Quist",
            "contacts": {
                "email": "jason@umukozihr.com",
                "phone": "+1-555-123-4567",
                "location": "San Francisco, CA",
                "links": ["https://linkedin.com/in/jasonquist", "https://github.com/jasonquist"]
            },
            "summary": "Experienced AI/ML Engineer and Full-Stack Developer with 5+ years building scalable systems",
            "skills": ["Python", "FastAPI", "React", "PostgreSQL", "AWS", "Docker", "Machine Learning"],
            "experience": [
                {
                    "title": "Senior AI Engineer",
                    "company": "UmukoziHR",
                    "location": "San Francisco, CA",
                    "start_date": "2023-01",
                    "end_date": "Present",
                    "bullets": [
                        "Built AI-powered resume tailoring system using FastAPI and Gemini LLM",
                        "Implemented JWT authentication and PostgreSQL database integration",
                        "Designed scalable architecture with Docker and background job processing"
                    ]
                }
            ],
            "education": [
                {
                    "degree": "BS Computer Science",
                    "school": "Stanford University",
                    "location": "Stanford, CA",
                    "graduation_date": "2020-06",
                    "gpa": "3.8/4.0"
                }
            ],
            "projects": [
                {
                    "name": "UmukoziHR Resume Tailor",
                    "description": "AI-powered resume and cover letter generator",
                    "technologies": ["Python", "FastAPI", "React", "LaTeX", "Gemini"],
                    "bullets": [
                        "Processes 1000+ resumes with 95% success rate",
                        "Supports multiple regional formats (US/EU/Global)"
                    ]
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/v1/profile/save", json=profile_data, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code in [200, 201]:
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Profile save failed: {e}")
        return False

def test_generate_simple():
    """Test document generation without auth"""
    print("🔄 Testing document generation (no auth)...")
    try:
        payload = {
            "profile": {
                "name": "Jason Quist",
                "contacts": {
                    "email": "jason@umukozihr.com",
                    "phone": "+1-555-123-4567",
                    "location": "San Francisco, CA",
                    "links": ["https://linkedin.com/in/jasonquist"]
                },
                "summary": "Experienced AI/ML Engineer",
                "skills": ["Python", "FastAPI", "React"],
                "experience": [{
                    "title": "Senior AI Engineer",
                    "company": "UmukoziHR",
                    "location": "San Francisco, CA",
                    "start_date": "2023-01",
                    "end_date": "Present",
                    "bullets": ["Built AI-powered systems", "Implemented scalable architecture"]
                }],
                "education": [{
                    "degree": "BS Computer Science",
                    "school": "Stanford University",
                    "location": "Stanford, CA",
                    "graduation_date": "2020-06"
                }],
                "projects": []
            },
            "jobs": [{
                "id": "test-job-1",
                "region": "US",
                "company": "Google",
                "title": "Senior Software Engineer",
                "jd_text": "We are looking for a Senior Software Engineer to join our team. You will work on scalable systems using Python, FastAPI, and cloud technologies. Experience with AI/ML is a plus."
            }],
            "prefs": {}
        }
        
        response = requests.post(f"{BASE_URL}/api/v1/generate/generate", json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"Generation successful: {json.dumps(data, indent=2)[:500]}...")
            return data
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        return None

def main():
    """Run all tests"""
    print("=" * 50)
    print("UmukoziHR Resume Tailor v1.2 - API Testing")
    print("=" * 50)
    
    results = {}
    
    # Test 1: Health Check
    results['health'] = test_health()
    print()
    
    # Test 2: Auth Signup
    results['signup'] = test_auth_signup()
    print()
    
    # Test 3: Auth Login
    token = test_auth_login()
    results['login'] = token is not None
    print()
    
    # Test 4: Profile Save
    results['profile_save'] = test_profile_save(token)
    print()
    
    # Test 5: Document Generation
    generation_result = test_generate_simple()
    results['generation'] = generation_result is not None
    print()
    
    # Summary
    print("=" * 50)
    print("TEST RESULTS SUMMARY")
    print("=" * 50)
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name.upper()}: {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    print(f"\nPassed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! System is working correctly.")
    else:
        print("⚠️  Some tests failed. Check logs above for details.")

if __name__ == "__main__":
    main()