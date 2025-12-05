#!/usr/bin/env python3
"""
Test the new TEX content feature
"""
import requests
import json

def test_tex_content():
    url = "http://localhost:8001/api/v1/generate/generate"
    
    data = {
        "profile": {
            "name": "Jason Quist",
            "contacts": {
                "email": "jason@umukozihr.com",
                "phone": "+1-555-0123",
                "location": "San Francisco, CA"
            },
            "summary": "Experienced CTO and AI Engineer",
            "skills": ["Python", "FastAPI", "React"],
            "experience": [{
                "title": "CTO",
                "company": "UmukoziHR",
                "start_date": "2025-05",
                "end_date": "Present",
                "bullets": ["Built scalable systems", "Led technical team"]
            }],
            "education": [{
                "degree": "MS Computer Science",
                "school": "Stanford University",
                "graduation_date": "2019-06"
            }],
            "projects": []
        },
        "jobs": [{
            "id": "test-tex",
            "region": "US",
            "company": "Google",
            "title": "Senior Engineer",
            "jd_text": "We need a Python expert with FastAPI experience"
        }],
        "prefs": {}
    }
    
    print("🧪 Testing TEX content generation...")
    print("⚠️  This may take 30-60 seconds due to LLM processing...")
    
    try:
        response = requests.post(url, json=data, timeout=90)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Generation successful!")
            
            # Check if artifacts contain TEX content
            if "artifacts" in result and len(result["artifacts"]) > 0:
                artifact = result["artifacts"][0]
                
                print("\n📋 Available fields in artifact:")
                for key in artifact.keys():
                    print(f"  - {key}")
                
                # Test TEX content
                if "resume_tex_content" in artifact:
                    tex_content = artifact["resume_tex_content"]
                    print(f"\n📄 Resume TEX Content (first 500 chars):")
                    print("="*60)
                    print(tex_content[:500] + "..." if len(tex_content) > 500 else tex_content)
                    print("="*60)
                    print(f"✅ Resume TEX content available ({len(tex_content)} characters)")
                else:
                    print("❌ No resume_tex_content found in response")
                
                if "cover_letter_tex_content" in artifact:
                    tex_content = artifact["cover_letter_tex_content"]
                    print(f"\n📄 Cover Letter TEX Content (first 500 chars):")
                    print("="*60)
                    print(tex_content[:500] + "..." if len(tex_content) > 500 else tex_content)
                    print("="*60)
                    print(f"✅ Cover letter TEX content available ({len(tex_content)} characters)")
                else:
                    print("❌ No cover_letter_tex_content found in response")
            else:
                print("❌ No artifacts found in response")
        else:
            print(f"❌ Generation failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_tex_content()