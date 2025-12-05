#!/usr/bin/env python3
"""
UmukoziHR Resume Tailor v1.2 - Comprehensive curl-like API Testing
Uses Python requests to simulate curl commands for thorough API testing
"""
import requests
import json
import time
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_header(test_name):
    """Print test section header"""
    print(f"\n{'='*60}")
    print(f"🔬 TESTING: {test_name}")
    print('='*60)

def print_curl_equivalent(method, url, headers=None, data=None):
    """Show the equivalent curl command"""
    curl_cmd = f"curl -X {method} {url}"
    
    if headers:
        for key, value in headers.items():
            curl_cmd += f" -H '{key}: {value}'"
    
    if data:
        if isinstance(data, dict):
            data_str = json.dumps(data, indent=2)
            curl_cmd += f" -d '{data_str}'"
        else:
            curl_cmd += f" -d '{data}'"
    
    print(f"📋 Curl equivalent:")
    print(f"   {curl_cmd}")
    print()

def make_request(method, endpoint, headers=None, data=None, description=""):
    """Make HTTP request and display results like curl would"""
    url = f"{BASE_URL}{endpoint}"
    
    print_curl_equivalent(method, url, headers, data)
    
    try:
        # Make the request
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=90)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=30)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            print(f"❌ Unsupported method: {method}")
            return None
        
        # Display results
        print(f"📡 Status Code: {response.status_code}")
        print(f"📡 Response Headers:")
        for key, value in response.headers.items():
            print(f"   {key}: {value}")
        
        print(f"📡 Response Body:")
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
        except:
            print(response.text[:1000] + ("..." if len(response.text) > 1000 else ""))
        
        # Status assessment
        if 200 <= response.status_code < 300:
            print(f"✅ {description} - SUCCESS")
        elif 400 <= response.status_code < 500:
            print(f"⚠️  {description} - CLIENT ERROR")
        elif 500 <= response.status_code < 600:
            print(f"❌ {description} - SERVER ERROR")
        else:
            print(f"❓ {description} - UNKNOWN STATUS")
        
        return response
        
    except requests.exceptions.Timeout:
        print(f"❌ {description} - TIMEOUT")
        return None
    except requests.exceptions.ConnectionError:
        print(f"❌ {description} - CONNECTION ERROR")
        return None
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return None

def test_health():
    """Test health endpoint"""
    print_header("Health Check")
    return make_request("GET", "/health", description="Health Check")

def test_signup():
    """Test user signup"""
    print_header("User Signup")
    signup_data = {
        "email": "curltest@umukozihr.com",
        "password": "securepass123"
    }
    return make_request("POST", "/api/v1/auth/signup", data=signup_data, description="User Signup")

def test_login():
    """Test user login"""
    print_header("User Login")
    login_data = {
        "email": "curltest@umukozihr.com",
        "password": "securepass123"
    }
    return make_request("POST", "/api/v1/auth/login", data=login_data, description="User Login")

def test_profile_save(token=None):
    """Test profile save endpoint"""
    print_header("Profile Save")
    
    profile_data = {
        "name": "Jason Quist",
        "contacts": {
            "email": "jason@umukozihr.com",
            "phone": "+1-555-0123",
            "location": "San Francisco, CA",
            "links": [
                "https://linkedin.com/in/jasonquist",
                "https://github.com/jasonquist"
            ]
        },
        "summary": "Experienced CTO and AI Engineer with 8+ years building scalable HR tech systems",
        "skills": [
            "Python", "FastAPI", "React", "Next.js", "PostgreSQL", 
            "Docker", "AWS", "Machine Learning", "System Architecture"
        ],
        "experience": [
            {
                "title": "CTO & VP Engineering",
                "company": "UmukoziHR",
                "location": "San Francisco, CA",
                "start_date": "2024-01",
                "end_date": "Present",
                "bullets": [
                    "Leading technical vision for AI-powered HR solutions serving 10,000+ users",
                    "Built scalable resume tailoring system processing 1000+ documents daily",
                    "Architected microservices infrastructure with FastAPI, PostgreSQL, and Redis",
                    "Implemented JWT authentication and multi-tenant database architecture"
                ]
            },
            {
                "title": "Senior AI Engineer",
                "company": "OpenAI",
                "location": "San Francisco, CA",
                "start_date": "2022-06",
                "end_date": "2023-12",
                "bullets": [
                    "Developed LLM integration patterns for enterprise applications",
                    "Optimized model performance achieving 40% latency reduction",
                    "Led cross-functional team of 12 engineers on AI infrastructure"
                ]
            }
        ],
        "education": [
            {
                "degree": "MS Computer Science",
                "school": "Stanford University",
                "location": "Stanford, CA",
                "graduation_date": "2019-06",
                "gpa": "3.9/4.0"
            }
        ],
        "projects": [
            {
                "name": "UmukoziHR Resume Tailor v1.2",
                "description": "AI-powered resume and cover letter generation platform",
                "technologies": ["Python", "FastAPI", "React", "PostgreSQL", "Gemini", "LaTeX"],
                "bullets": [
                    "Processes resumes with 95% success rate and ATS optimization",
                    "Supports multiple regional formats with LaTeX compilation",
                    "Features JWT authentication and background job processing"
                ]
            }
        ]
    }
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        description = "Profile Save (Authenticated)"
    else:
        description = "Profile Save (No Auth)"
    
    return make_request("POST", "/api/v1/profile/profile", headers=headers, data=profile_data, description=description)

def test_document_generation(token=None):
    """Test document generation endpoint"""
    print_header("Document Generation")
    
    generation_data = {
        "profile": {
            "name": "Jason Quist",
            "contacts": {
                "email": "jason@umukozihr.com",
                "phone": "+1-555-0123",
                "location": "San Francisco, CA",
                "links": ["https://linkedin.com/in/jasonquist"]
            },
            "summary": "Experienced CTO and AI Engineer with 8+ years in tech leadership",
            "skills": ["Python", "FastAPI", "React", "AI/ML", "System Architecture"],
            "experience": [
                {
                    "title": "CTO & VP Engineering",
                    "company": "UmukoziHR",
                    "location": "San Francisco, CA",
                    "start_date": "2024-01",
                    "end_date": "Present",
                    "bullets": [
                        "Leading technical vision for AI-powered HR solutions",
                        "Built scalable resume tailoring system processing 1000+ documents",
                        "Architected microservices infrastructure with modern tech stack"
                    ]
                }
            ],
            "education": [
                {
                    "degree": "MS Computer Science",
                    "school": "Stanford University",
                    "location": "Stanford, CA",
                    "graduation_date": "2019-06"
                }
            ],
            "projects": []
        },
        "jobs": [
            {
                "id": "test-senior-eng",
                "region": "US",
                "company": "Google",
                "title": "Senior Software Engineer - AI/ML",
                "jd_text": "We are looking for a Senior Software Engineer to join our AI/ML team. You will work on large-scale systems using Python, develop APIs with modern frameworks like FastAPI, and lead technical initiatives. Experience with machine learning, system architecture, and team leadership is highly valued. Join us to build the future of AI-powered applications."
            }
        ],
        "prefs": {}
    }
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        description = "Document Generation (Authenticated)"
    else:
        description = "Document Generation (No Auth)"
    
    print("⚠️  Note: This test may take 30-60 seconds due to LLM processing...")
    return make_request("POST", "/api/v1/generate/generate", headers=headers, data=generation_data, description=description)

def test_invalid_auth():
    """Test invalid authentication"""
    print_header("Invalid Authentication Test")
    invalid_data = {
        "email": "invalid@test.com",
        "password": "wrongpassword"
    }
    return make_request("POST", "/api/v1/auth/login", data=invalid_data, description="Invalid Authentication")

def test_api_docs():
    """Test API documentation endpoint"""
    print_header("API Documentation")
    return make_request("GET", "/docs", description="API Documentation")

def main():
    """Run comprehensive curl-like tests"""
    print("🚀 UmukoziHR Resume Tailor v1.2 - Comprehensive curl-like API Testing")
    print("=" * 80)
    print(f"🕒 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Base URL: {BASE_URL}")
    
    # Wait a moment for server to be ready
    print("\\n⏳ Waiting for server to be ready...")
    time.sleep(2)
    
    results = {}
    
    # Test 1: Health Check
    response = test_health()
    results['health'] = response and response.status_code == 200
    
    # Test 2: User Signup
    response = test_signup()
    signup_success = response and response.status_code in [200, 201]
    results['signup'] = signup_success
    
    # Extract token from signup
    access_token = None
    if signup_success:
        try:
            signup_data = response.json()
            access_token = signup_data.get('access_token')
        except:
            pass
    
    # Test 3: User Login
    response = test_login()
    login_success = response and response.status_code == 200
    results['login'] = login_success
    
    # Use login token if available
    if login_success:
        try:
            login_data = response.json()
            login_token = login_data.get('access_token')
            if login_token:
                access_token = login_token
        except:
            pass
    
    # Test 4: Profile Save (Authenticated)
    if access_token:
        response = test_profile_save(access_token)
        results['profile_auth'] = response and response.status_code in [200, 201]
    else:
        results['profile_auth'] = False
        print("⚠️  Skipping authenticated profile save - no token")
    
    # Test 5: Profile Save (No Auth)
    response = test_profile_save()
    results['profile_noauth'] = response and response.status_code in [200, 201]
    
    # Test 6: Document Generation (Authenticated)
    if access_token:
        response = test_document_generation(access_token)
        results['generation_auth'] = response and response.status_code in [200, 201]
    else:
        results['generation_auth'] = False
        print("⚠️  Skipping authenticated generation - no token")
    
    # Test 7: Document Generation (No Auth)
    response = test_document_generation()
    results['generation_noauth'] = response and response.status_code in [200, 201]
    
    # Test 8: Invalid Authentication
    response = test_invalid_auth()
    results['invalid_auth'] = response and response.status_code == 401
    
    # Test 9: API Documentation
    response = test_api_docs()
    results['api_docs'] = response and response.status_code == 200
    
    # Final Summary
    print("\\n" + "=" * 80)
    print("📊 CURL-LIKE TEST SUMMARY")
    print("=" * 80)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name.upper().replace('_', ' '):30} {status}")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\\nOverall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("\\n🎉 ALL CURL-LIKE TESTS PASSED! API is fully functional.")
    else:
        print(f"\\n⚠️  {total-passed} test(s) failed. Check individual results above.")
    
    print(f"\\n🕒 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)