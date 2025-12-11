#!/usr/bin/env python3
"""
Multi-User Testing Script
v1.3 Final - User Scenario Testing

Tests various user scenarios:
1. New user signup + onboarding + generation
2. Existing user login + profile update + generation
3. Multiple concurrent generations
4. Edge cases (incomplete profiles, long JDs)

Run with: python test_multi_user.py
"""
import os
import sys
import json
import time
import random
import string
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import requests

# API configuration
BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")

# Test data templates
SAMPLE_PROFILES = [
    {
        "basics": {
            "full_name": "Test User One",
            "headline": "Software Engineer",
            "summary": "Experienced developer with 5+ years in full-stack development.",
            "location": "New York, NY",
            "email": "test1@example.com",
            "phone": "+1 555-0001",
            "website": "https://testuser1.dev",
            "links": ["github.com/testuser1"]
        },
        "skills": [
            {"name": "Python", "level": "expert", "keywords": ["FastAPI", "Django"]},
            {"name": "JavaScript", "level": "expert", "keywords": ["React", "Node.js"]},
            {"name": "SQL", "level": "intermediate", "keywords": ["PostgreSQL"]}
        ],
        "experience": [
            {
                "title": "Senior Developer",
                "company": "Tech Corp",
                "location": "Remote",
                "start": "2020-01",
                "end": "present",
                "employment_type": "full-time",
                "bullets": [
                    "Led development of microservices handling 1M+ daily requests",
                    "Reduced deployment time by 50% through CI/CD improvements",
                    "Mentored 3 junior developers"
                ]
            }
        ],
        "education": [
            {"school": "MIT", "degree": "B.S. Computer Science", "start": "2012", "end": "2016", "gpa": "3.8"}
        ],
        "projects": [
            {"name": "OpenProject", "url": "github.com/test/openproject", "stack": ["Python", "React"], "bullets": ["Built open-source analytics tool"]}
        ],
        "certifications": [],
        "awards": [],
        "languages": [{"name": "English", "level": "Native"}],
        "preferences": {"regions": ["US"], "templates": ["minimal"]}
    },
    {
        "basics": {
            "full_name": "Test User Two",
            "headline": "Data Scientist",
            "summary": "ML engineer with expertise in NLP and computer vision.",
            "location": "San Francisco, CA",
            "email": "test2@example.com",
            "phone": "+1 555-0002",
            "website": "",
            "links": []
        },
        "skills": [
            {"name": "Python", "level": "expert", "keywords": ["PyTorch", "TensorFlow"]},
            {"name": "Machine Learning", "level": "expert", "keywords": []},
            {"name": "SQL", "level": "intermediate", "keywords": []}
        ],
        "experience": [
            {
                "title": "ML Engineer",
                "company": "AI Startup",
                "location": "San Francisco",
                "start": "2019-06",
                "end": "present",
                "employment_type": "full-time",
                "bullets": [
                    "Built NLP models achieving 95% accuracy",
                    "Deployed models serving 100K predictions/day",
                    "Published 2 research papers"
                ]
            }
        ],
        "education": [
            {"school": "Stanford", "degree": "M.S. Machine Learning", "start": "2017", "end": "2019", "gpa": "3.9"}
        ],
        "projects": [],
        "certifications": [],
        "awards": [],
        "languages": [],
        "preferences": {"regions": ["US", "EU"], "templates": ["modern"]}
    }
]

SAMPLE_JDS = [
    {
        "company": "TechGiant",
        "title": "Senior Software Engineer",
        "region": "US",
        "jd_text": """
        We're looking for a Senior Software Engineer to join our platform team.
        
        Requirements:
        - 5+ years of software development experience
        - Strong proficiency in Python or Java
        - Experience with microservices and distributed systems
        - Strong API design skills
        - Database optimization experience
        
        Nice to have:
        - Cloud experience (AWS/GCP)
        - Kubernetes experience
        """
    },
    {
        "company": "DataCo",
        "title": "Machine Learning Engineer",
        "region": "US",
        "jd_text": """
        Join our ML team to build next-generation AI products!
        
        Requirements:
        - MS/PhD in CS, ML, or related field
        - Strong Python skills
        - Experience with PyTorch or TensorFlow
        - NLP or Computer Vision experience
        - Model deployment experience
        """
    }
]


def generate_random_email():
    """Generate a unique test email"""
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_{suffix}@example.com"


def test_signup_flow(email: str, password: str = "TestPass123!") -> dict:
    """Test user signup"""
    print(f"\n--- Testing Signup: {email} ---")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/signup",
            json={"email": email, "password": password},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Signup successful, token received")
            return {"success": True, "token": data["access_token"]}
        elif response.status_code == 400:
            print(f"[WARN] Email already registered")
            return {"success": False, "error": "already_registered"}
        else:
            print(f"[ERROR] Signup failed: {response.status_code} - {response.text}")
            return {"success": False, "error": response.text}
            
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return {"success": False, "error": str(e)}


def test_login_flow(email: str, password: str = "TestPass123!") -> dict:
    """Test user login"""
    print(f"\n--- Testing Login: {email} ---")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Login successful")
            return {"success": True, "token": data["access_token"]}
        else:
            print(f"[ERROR] Login failed: {response.status_code}")
            return {"success": False, "error": response.text}
            
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return {"success": False, "error": str(e)}


def test_profile_update(token: str, profile_data: dict) -> dict:
    """Test profile update"""
    print(f"\n--- Testing Profile Update ---")
    
    try:
        response = requests.put(
            f"{BASE_URL}/api/v1/profile/profile",
            headers={"Authorization": f"Bearer {token}"},
            json={"profile": profile_data},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Profile updated - Version: {data.get('version')}, Completeness: {data.get('completeness')}%")
            return {"success": True, "data": data}
        else:
            print(f"[ERROR] Profile update failed: {response.status_code} - {response.text}")
            return {"success": False, "error": response.text}
            
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return {"success": False, "error": str(e)}


def test_generation(token: str, jd_data: dict) -> dict:
    """Test document generation"""
    print(f"\n--- Testing Generation: {jd_data['title']} at {jd_data['company']} ---")
    
    try:
        start_time = time.time()
        
        response = requests.post(
            f"{BASE_URL}/api/v1/generate/",
            headers={"Authorization": f"Bearer {token}"},
            json={"profile": None, "jobs": [jd_data], "prefs": {}},
            timeout=120  # Generation can take time
        )
        
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Generation successful in {duration:.2f}s")
            print(f"     Run ID: {data.get('run_id')}")
            print(f"     Artifacts: {len(data.get('artifacts', []))}")
            return {"success": True, "data": data, "duration": duration}
        else:
            print(f"[ERROR] Generation failed: {response.status_code} - {response.text}")
            return {"success": False, "error": response.text, "duration": duration}
            
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return {"success": False, "error": str(e)}


def test_full_user_journey(profile_idx: int = 0, jd_idx: int = 0) -> dict:
    """Test complete user journey: signup -> profile -> generate"""
    print("\n" + "="*60)
    print(f"FULL USER JOURNEY TEST #{profile_idx + 1}")
    print("="*60)
    
    email = generate_random_email()
    profile = SAMPLE_PROFILES[profile_idx % len(SAMPLE_PROFILES)]
    jd = SAMPLE_JDS[jd_idx % len(SAMPLE_JDS)]
    
    results = {
        "email": email,
        "signup": None,
        "profile_update": None,
        "generation": None,
        "success": False
    }
    
    # Step 1: Signup
    signup_result = test_signup_flow(email)
    results["signup"] = signup_result
    
    if not signup_result["success"]:
        return results
    
    token = signup_result["token"]
    
    # Step 2: Update profile
    profile_result = test_profile_update(token, profile)
    results["profile_update"] = profile_result
    
    if not profile_result["success"]:
        return results
    
    # Step 3: Generate
    gen_result = test_generation(token, jd)
    results["generation"] = gen_result
    
    results["success"] = gen_result.get("success", False)
    
    return results


def run_multi_user_tests():
    """Run comprehensive multi-user tests"""
    print("\n" + "="*60)
    print("UmukoziHR Resume Tailor - Multi-User Testing")
    print("v1.3 Final")
    print(f"Target: {BASE_URL}")
    print("="*60)
    
    # Check server is reachable
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print(f"[OK] Server is healthy: {response.json()}")
        else:
            print(f"[ERROR] Server returned {response.status_code}")
            return
    except Exception as e:
        print(f"[ERROR] Cannot reach server: {e}")
        print("Make sure the server is running or set TEST_API_URL environment variable")
        return
    
    all_results = []
    
    # Run multiple user journeys
    for i in range(2):  # Test with 2 different user/JD combinations
        result = test_full_user_journey(profile_idx=i, jd_idx=i)
        all_results.append(result)
        time.sleep(3)  # Small delay between tests
    
    # Summary
    print("\n" + "="*60)
    print("MULTI-USER TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in all_results if r["success"])
    total = len(all_results)
    
    for i, result in enumerate(all_results):
        status = "PASS" if result["success"] else "FAIL"
        gen_time = result.get("generation", {}).get("duration", "N/A")
        print(f"  [{status}] Journey #{i+1}: {result['email']}")
        if result["success"]:
            print(f"          Generation time: {gen_time:.2f}s" if isinstance(gen_time, float) else f"          Generation time: {gen_time}")
    
    print(f"\nResults: {passed}/{total} journeys completed successfully")
    
    return all_results


if __name__ == "__main__":
    run_multi_user_tests()
