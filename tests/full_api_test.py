#!/usr/bin/env python3
"""
Comprehensive API Testing Script for UmukoziHR Resume Tailor v1.2
Tests authentication, profile management, and document generation
"""
import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000"

def print_test(name):
    print(f"\n{'='*50}")
    print(f"Testing: {name}")
    print('='*50)

def test_health():
    print_test("Health Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
            print("✅ Health check passed!")
            return True
        else:
            print(f"❌ Health check failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_auth():
    print_test("Authentication System")
    
    # Test signup
    try:
        signup_data = {
            "email": "cto@umukozihr.com",
            "password": "secure123password"
        }
        
        print("Testing signup...")
        response = requests.post(f"{BASE_URL}/api/v1/auth/signup", json=signup_data, timeout=10)
        print(f"Signup Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            access_token = data.get("access_token")
            print(f"✅ Signup successful! Token: {access_token[:20]}...")
            
            # Test login
            print("\\nTesting login...")
            login_data = {
                "email": "cto@umukozihr.com", 
                "password": "secure123password"
            }
            
            response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data, timeout=10)
            print(f"Login Status: {response.status_code}")
            
            if response.status_code == 200:
                login_data = response.json()
                login_token = login_data.get("access_token")
                print(f"✅ Login successful! Token: {login_token[:20]}...")
                return login_token
            else:
                print(f"❌ Login failed: {response.text}")
                return None
        else:
            print(f"❌ Signup failed: {response.text}")
            # Try login anyway in case user exists
            login_data = {"email": "cto@umukozihr.com", "password": "secure123password"}
            response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
            return None
            
    except Exception as e:
        print(f"❌ Auth test error: {e}")
        return None

def test_profile(token=None):
    print_test("Profile Management")
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
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
        "summary": "Experienced AI/ML Engineer and CTO with 8+ years building scalable HR tech systems",
        "skills": [
            "Python", "FastAPI", "React", "Next.js", "PostgreSQL", "Docker", 
            "AWS", "Machine Learning", "System Architecture", "Team Leadership"
        ],
        "experience": [
            {
                "title": "CTO & VP Engineering",
                "company": "UmukoziHR",
                "location": "San Francisco, CA", 
                "start_date": "2024-01",
                "end_date": "Present",
                "bullets": [
                    "Leading technical vision and product development for AI-powered HR solutions",
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
                    "Supports multiple regional formats (US/EU/Global) with LaTeX compilation",
                    "Features JWT authentication, background job processing with Celery/Redis"
                ]
            }
        ]
    }
    
    try:
        print("Testing profile save...")
        response = requests.post(f"{BASE_URL}/api/v1/profile/profile", json=profile_data, headers=headers, timeout=15)
        print(f"Profile Save Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"✅ Profile saved successfully!")
            print(f"Response: {data}")
            return True
        else:
            print(f"❌ Profile save failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Profile test error: {e}")
        return False

def test_generation(token=None):
    print_test("Document Generation")
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    generation_request = {
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
            "experience": [{
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
            }],
            "education": [{
                "degree": "MS Computer Science",
                "school": "Stanford University", 
                "location": "Stanford, CA",
                "graduation_date": "2019-06"
            }],
            "projects": []
        },
        "jobs": [{
            "id": "senior-eng-test",
            "region": "US",
            "company": "Google",
            "title": "Senior Software Engineer - AI/ML",
            "jd_text": "We are looking for a Senior Software Engineer to join our AI/ML team. You will work on large-scale systems using Python, develop APIs with modern frameworks, and lead technical initiatives. Experience with machine learning, system architecture, and team leadership is highly valued. Join us to build the future of AI-powered applications."
        }],
        "prefs": {}
    }
    
    try:
        print("Testing document generation...")
        print("This may take 30-60 seconds due to LLM processing...")
        
        response = requests.post(
            f"{BASE_URL}/api/v1/generate/generate", 
            json=generation_request, 
            headers=headers, 
            timeout=90
        )
        print(f"Generation Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"✅ Document generation successful!")
            print(f"Run ID: {data.get('run')}")
            print(f"Artifacts: {len(data.get('artifacts', []))} generated")
            print(f"ZIP Bundle: {data.get('zip')}")
            
            # Show artifact details
            for artifact in data.get('artifacts', []):
                print(f"  - Job: {artifact.get('job_id')}")
                print(f"    Resume TEX: {artifact.get('resume_tex')}")
                print(f"    Cover Letter TEX: {artifact.get('cover_letter_tex')}")
                if artifact.get('resume_pdf'):
                    print(f"    Resume PDF: {artifact.get('resume_pdf')}")
                if artifact.get('cover_letter_pdf'):
                    print(f"    Cover Letter PDF: {artifact.get('cover_letter_pdf')}")
            
            return True
        else:
            print(f"❌ Generation failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Generation test error: {e}")
        return False

def main():
    print("🚀 UmukoziHR Resume Tailor v1.2 - Comprehensive API Testing")
    print("=" * 70)
    
    results = {}
    
    # Test 1: Health Check
    results['health'] = test_health()
    
    # Test 2: Authentication
    token = test_auth()
    results['auth'] = token is not None
    
    # Test 3: Profile Management  
    results['profile'] = test_profile(token)
    
    # Test 4: Document Generation
    results['generation'] = test_generation(token)
    
    # Final Summary
    print(f"\\n{'='*70}")
    print("FINAL TEST RESULTS")
    print('='*70)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name.upper():20} {status}")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\\n🎉 ALL TESTS PASSED! System is fully operational.")
        print("✅ Backend is ready for production deployment.")
    else:
        print(f"\\n⚠️  {total-passed} test(s) failed. System needs attention.")
        
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)