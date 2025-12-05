#!/usr/bin/env python3
"""
Individual Component Testing for UmukoziHR Resume Tailor v1.2
Tests each core module independently without full API calls
"""
import sys
import os
import json

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_models():
    """Test Pydantic models"""
    print("🔄 Testing Models...")
    try:
        from app.models import Profile, Contact, Role, JobJD, GenerateRequest
        
        # Create test profile
        profile = Profile(
            name="Test User",
            contacts=Contact(
                email="test@example.com",
                phone="+1-555-0123",
                location="San Francisco, CA"
            ),
            summary="Test engineer",
            skills=["Python", "FastAPI"],
            experience=[
                Role(
                    title="Software Engineer",
                    company="Test Corp",
                    start="2023-01",
                    end="Present",
                    bullets=["Built scalable systems", "Improved performance by 40%"]
                )
            ]
        )
        
        # Create test job
        job = JobJD(
            id="test-job",
            region="US",
            company="Google",
            title="Senior Engineer",
            jd_text="We need a Python expert with FastAPI experience"
        )
        
        print(f"✅ Models working! Profile: {profile.name}, Job: {job.title}")
        return True
        
    except Exception as e:
        print(f"❌ Models test failed: {e}")
        return False

def test_auth_components():
    """Test authentication components"""
    print("🔄 Testing Auth Components...")
    try:
        from app.auth.auth import hash_password, verify_password, create_access_token, verify_token
        
        # Test password hashing
        password = "testpass123"
        hashed = hash_password(password)
        verified = verify_password(password, hashed)
        
        # Test JWT
        token = create_access_token({"sub": "test-user-id"})
        payload = verify_token(token)
        
        if verified and payload and payload.get("sub") == "test-user-id":
            print("✅ Auth components working!")
            return True
        else:
            print("❌ Auth verification failed")
            return False
            
    except Exception as e:
        print(f"❌ Auth test failed: {e}")
        return False

def test_tailor_components():
    """Test core tailoring logic (without LLM call)"""
    print("🔄 Testing Tailor Components...")
    try:
        from app.core.tailor import select_topk_bullets, region_rules, norm_tokens, score_bullet
        from app.models import Profile, Role
        
        # Create test profile
        profile = Profile(
            name="Test User",
            experience=[
                Role(
                    title="Software Engineer",
                    company="TechCorp",
                    bullets=[
                        "Built Python APIs using FastAPI framework",
                        "Implemented database optimization with PostgreSQL",
                        "Developed machine learning models for data analysis"
                    ]
                )
            ]
        )
        
        jd_text = "We need a Python developer with FastAPI and PostgreSQL experience for ML projects"
        
        # Test bullet selection
        selected = select_topk_bullets(profile, jd_text, k=3)
        
        # Test region rules
        us_rules = region_rules("US")
        eu_rules = region_rules("EU")
        
        print(f"✅ Tailor components working! Selected {len(selected)} bullets")
        print(f"   US Rules: {us_rules}")
        print(f"   EU Rules: {eu_rules}")
        return True
        
    except Exception as e:
        print(f"❌ Tailor test failed: {e}")
        return False

def test_validation():
    """Test validation components"""
    print("🔄 Testing Validation...")
    try:
        from app.core.validate import validate_or_error
        
        # Test valid JSON
        test_data = {
            "resume": {
                "summary": "Test summary",
                "skills_line": ["Python", "FastAPI"],
                "experience": [{
                    "title": "Engineer",
                    "company": "TechCorp",
                    "bullets": ["Built systems"]
                }],
                "projects": [],
                "education": []
            },
            "cover_letter": {
                "address": "Test address",
                "intro": "Test intro",
                "why_you": "Test why you",
                "evidence": ["Test evidence"],
                "why_them": "Test why them",
                "close": "Test close"
            },
            "ats": {
                "jd_keywords_matched": ["Python"],
                "risks": []
            }
        }
        
        # Test validation
        validated = validate_or_error(json.dumps(test_data))
        
        print("✅ Validation working!")
        return True
        
    except Exception as e:
        print(f"❌ Validation test failed: {e}")
        return False

def test_tex_compilation():
    """Test LaTeX template rendering (without compilation)"""
    print("🔄 Testing LaTeX Templates...")
    try:
        from app.core.tex_compile import render_tex
        
        # Test context data
        resume_ctx = {
            "profile": {
                "name": "Test User",
                "contacts": {
                    "email": "test@example.com",
                    "phone": "+1-555-0123",
                    "location": "San Francisco, CA",
                    "links": ["https://linkedin.com/in/testuser"]
                }
            },
            "out": {
                "summary": "Experienced software engineer",
                "skills_line": ["Python", "FastAPI", "PostgreSQL"],
                "experience": [{
                    "title": "Software Engineer",
                    "company": "TechCorp",
                    "start": "2023-01",
                    "end": "Present",
                    "bullets": ["Built scalable APIs", "Improved system performance"]
                }],
                "projects": [],
                "education": [{
                    "school": "University",
                    "degree": "BS Computer Science",
                    "period": "2019-2023"
                }]
            },
            "job": {
                "company": "Google",
                "title": "Senior Engineer"
            }
        }
        
        cover_ctx = {
            "profile": resume_ctx["profile"],
            "out": {
                "address": "Google Inc.\nMountain View, CA",
                "intro": "I am writing to express my interest in...",
                "why_you": "I am a qualified candidate because...",
                "evidence": ["Built scalable systems", "Led technical teams"],
                "why_them": "I want to work at Google because...",
                "close": "Thank you for your consideration."
            },
            "job": resume_ctx["job"]
        }
        
        # Test rendering
        resume_path, cover_path = render_tex(resume_ctx, cover_ctx, "US", "test_render")
        
        # Check if files were created
        if os.path.exists(resume_path) and os.path.exists(cover_path):
            print(f"✅ LaTeX templates working!")
            print(f"   Resume: {os.path.basename(resume_path)}")
            print(f"   Cover Letter: {os.path.basename(cover_path)}")
            
            # Clean up test files
            try:
                os.remove(resume_path)
                os.remove(cover_path)
            except:
                pass
                
            return True
        else:
            print("❌ LaTeX files not created")
            return False
        
    except Exception as e:
        print(f"❌ LaTeX test failed: {e}")
        return False

def main():
    """Run all component tests"""
    print("=" * 60)
    print("UmukoziHR Resume Tailor v1.2 - Component Testing")
    print("=" * 60)
    
    results = {}
    
    # Test each component
    results['models'] = test_models()
    print()
    
    results['auth'] = test_auth_components()
    print()
    
    results['tailor'] = test_tailor_components()
    print()
    
    results['validation'] = test_validation()
    print()
    
    results['latex'] = test_tex_compilation()
    print()
    
    # Summary
    print("=" * 60)
    print("COMPONENT TEST RESULTS")
    print("=" * 60)
    
    for component, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{component.upper():15} {status}")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nComponent Tests: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All core components are working!")
        return True
    else:
        print(f"⚠️  {total-passed} component(s) need attention")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)