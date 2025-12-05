#!/usr/bin/env python3
"""
Test PDF generation and download functionality
"""
import requests
import json
import time
import os

def test_pdf_generation():
    url = "http://localhost:8001/api/v1/generate/generate"
    
    data = {
        "profile": {
            "name": "Jason Quist",
            "contacts": {
                "email": "jason@umukozihr.com",
                "phone": "+1-555-0123",
                "location": "San Francisco, CA",
                "links": ["https://linkedin.com/in/jasonquist"]
            },
            "summary": "Experienced CTO and AI Engineer with 8+ years building scalable HR tech systems",
            "skills": ["Python", "FastAPI", "React", "PostgreSQL", "Docker", "AWS"],
            "experience": [{
                "title": "CTO & VP Engineering",
                "company": "UmukoziHR",
                "location": "San Francisco, CA",
                "start_date": "2024-01",
                "end_date": "Present",
                "bullets": [
                    "Leading technical vision for AI-powered HR solutions serving 10,000+ users",
                    "Built scalable resume tailoring system processing 1000+ documents daily",
                    "Architected microservices infrastructure with FastAPI, PostgreSQL, and Redis"
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
            "id": "pdf-test",
            "region": "US",
            "company": "Google",
            "title": "Senior Software Engineer - AI/ML",
            "jd_text": "We are looking for a Senior Software Engineer to join our AI/ML team. You will work on large-scale systems using Python, develop APIs with modern frameworks like FastAPI, and lead technical initiatives. Experience with machine learning, system architecture, and team leadership is highly valued."
        }],
        "prefs": {}
    }
    
    print("🧪 Testing PDF Generation and Download")
    print("=" * 50)
    print("⚠️  This may take 30-90 seconds due to LLM processing and PDF compilation...")
    
    try:
        # Generate documents
        response = requests.post(url, json=data, timeout=120)
        print(f"📡 Generation Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Generation successful!")
            
            # Check artifacts
            if "artifacts" in result and len(result["artifacts"]) > 0:
                artifact = result["artifacts"][0]
                
                print(f"\n📋 Artifact Details:")
                print(f"  Job ID: {artifact.get('job_id')}")
                print(f"  Region: {artifact.get('region')}")
                
                # Check PDF compilation status
                if "pdf_compilation" in artifact:
                    pdf_status = artifact["pdf_compilation"]
                    print(f"\n📄 PDF Compilation Status:")
                    print(f"  Resume PDF: {'✅ Success' if pdf_status.get('resume_success') else '❌ Failed'}")
                    print(f"  Cover Letter PDF: {'✅ Success' if pdf_status.get('cover_letter_success') else '❌ Failed'}")
                
                # Test PDF downloads
                download_base = "http://localhost:8001"
                
                if "resume_pdf" in artifact:
                    pdf_url = download_base + artifact["resume_pdf"]
                    print(f"\n📥 Testing Resume PDF Download:")
                    print(f"  URL: {pdf_url}")
                    
                    pdf_response = requests.get(pdf_url, timeout=30)
                    if pdf_response.status_code == 200 and pdf_response.headers.get('content-type') == 'application/pdf':
                        print(f"  ✅ Resume PDF downloaded successfully ({len(pdf_response.content)} bytes)")
                        
                        # Save for inspection
                        with open("test_resume.pdf", "wb") as f:
                            f.write(pdf_response.content)
                        print(f"  💾 Saved as test_resume.pdf")
                    else:
                        print(f"  ❌ Resume PDF download failed: {pdf_response.status_code}")
                else:
                    print(f"\n❌ No resume PDF URL in response")
                
                if "cover_letter_pdf" in artifact:
                    pdf_url = download_base + artifact["cover_letter_pdf"]
                    print(f"\n📥 Testing Cover Letter PDF Download:")
                    print(f"  URL: {pdf_url}")
                    
                    pdf_response = requests.get(pdf_url, timeout=30)
                    if pdf_response.status_code == 200 and pdf_response.headers.get('content-type') == 'application/pdf':
                        print(f"  ✅ Cover letter PDF downloaded successfully ({len(pdf_response.content)} bytes)")
                        
                        # Save for inspection
                        with open("test_cover_letter.pdf", "wb") as f:
                            f.write(pdf_response.content)
                        print(f"  💾 Saved as test_cover_letter.pdf")
                    else:
                        print(f"  ❌ Cover letter PDF download failed: {pdf_response.status_code}")
                else:
                    print(f"\n❌ No cover letter PDF URL in response")
                
                # Test ZIP bundle download
                if "zip" in result:
                    zip_url = download_base + result["zip"]
                    print(f"\n📦 Testing ZIP Bundle Download:")
                    print(f"  URL: {zip_url}")
                    
                    zip_response = requests.get(zip_url, timeout=30)
                    if zip_response.status_code == 200:
                        print(f"  ✅ ZIP bundle downloaded successfully ({len(zip_response.content)} bytes)")
                        
                        # Save for inspection
                        with open("test_bundle.zip", "wb") as f:
                            f.write(zip_response.content)
                        print(f"  💾 Saved as test_bundle.zip")
                    else:
                        print(f"  ❌ ZIP bundle download failed: {zip_response.status_code}")
                
                print(f"\n🎯 Summary:")
                pdf_count = sum([1 for key in artifact.keys() if key.endswith('_pdf')])
                print(f"  📄 PDFs generated: {pdf_count}")
                print(f"  📦 ZIP bundle: {'✅ Available' if 'zip' in result else '❌ Missing'}")
                print(f"  🔗 Download links: {len([k for k in artifact.keys() if k.endswith('_pdf')])}")
                
            else:
                print("❌ No artifacts found in response")
        else:
            print(f"❌ Generation failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_pdf_generation()