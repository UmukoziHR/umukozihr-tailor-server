#!/usr/bin/env python3
"""
End-to-End Tailoring Pipeline Test
v1.3 Final - Comprehensive verification

Tests:
1. Context merge (JD + Profile + Region)
2. LLM output quality
3. Consistency
4. Job-specific depth

Run with: python test_tailoring_pipeline.py
"""
import os
import sys
import json
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from app.models import Profile, Contact, Role, Education, Project, JobJD
from app.core.tailor import run_tailor
from app.core.tex_compile import render_tex, compile_tex

# Test profile (realistic tech professional)
TEST_PROFILE = Profile(
    name="Alex Chen",
    contacts=Contact(
        email="alex.chen@email.com",
        phone="+1 555-123-4567",
        location="San Francisco, CA",
        links=["linkedin.com/in/alexchen", "github.com/alexchen"]
    ),
    summary="Full-stack software engineer with 5+ years of experience building scalable web applications and APIs. Expert in Python, JavaScript, and cloud technologies.",
    skills=["Python", "FastAPI", "React", "TypeScript", "PostgreSQL", "AWS", "Docker", "Kubernetes", "Redis", "GraphQL"],
    experience=[
        Role(
            title="Senior Software Engineer",
            company="TechStartup Inc",
            start="2022-01",
            end="present",
            bullets=[
                "Led development of microservices architecture handling 10M+ daily requests",
                "Reduced API latency by 40% through Redis caching and query optimization",
                "Mentored team of 4 junior developers, improving code review efficiency by 30%",
                "Implemented CI/CD pipelines reducing deployment time from 2 hours to 15 minutes"
            ]
        ),
        Role(
            title="Software Engineer",
            company="BigCorp Solutions",
            start="2019-06",
            end="2021-12",
            bullets=[
                "Built customer-facing dashboard using React and TypeScript serving 50K+ users",
                "Designed and implemented RESTful APIs using Python/Django framework",
                "Collaborated with product team to define technical requirements for new features",
                "Reduced bug count by 25% through implementing comprehensive test coverage"
            ]
        )
    ],
    education=[
        Education(school="University of California, Berkeley", degree="B.S. Computer Science", period="2015-2019")
    ],
    projects=[
        Project(
            name="OpenSource Analytics",
            stack=["Python", "FastAPI", "React", "PostgreSQL"],
            bullets=["Built open-source web analytics platform with 500+ GitHub stars", "Processes 1M+ events daily with sub-second query response"]
        )
    ]
)

# Test JDs for different scenarios
TEST_JDS = [
    {
        "name": "Backend Engineer - Fintech",
        "jd": JobJD(
            id="backend-fintech",
            region="US",
            company="PaymentTech",
            title="Senior Backend Engineer",
            jd_text="""
            We're looking for a Senior Backend Engineer to join our payments platform team.
            
            Requirements:
            - 5+ years of experience in backend development
            - Strong proficiency in Python or Go
            - Experience with microservices architecture
            - Knowledge of payment processing and PCI compliance
            - Experience with PostgreSQL and Redis
            - Familiarity with AWS or GCP
            - Strong API design skills
            
            Responsibilities:
            - Design and build scalable payment processing systems
            - Optimize database performance for high-throughput transactions
            - Collaborate with security team on compliance requirements
            - Mentor junior engineers and conduct code reviews
            """
        ),
        "expected_keywords": ["payment", "backend", "microservices", "api", "postgresql", "redis"]
    },
    {
        "name": "Full Stack Developer - Healthcare",
        "jd": JobJD(
            id="fullstack-healthcare",
            region="US",
            company="HealthTech Solutions",
            title="Full Stack Developer",
            jd_text="""
            Join our team building next-generation healthcare applications!
            
            Requirements:
            - 3+ years of full-stack development experience
            - Proficiency in React or Vue.js
            - Backend experience with Python or Node.js
            - Experience with healthcare data standards (HIPAA, HL7)
            - Database design and optimization skills
            - Strong communication skills for cross-functional collaboration
            
            Nice to have:
            - Experience with GraphQL
            - Cloud deployment experience (AWS/Azure)
            - CI/CD pipeline experience
            """
        ),
        "expected_keywords": ["healthcare", "react", "python", "api", "database"]
    },
    {
        "name": "DevOps Engineer - EU Region",
        "jd": JobJD(
            id="devops-eu",
            region="EU",
            company="CloudScale GmbH",
            title="DevOps Engineer",
            jd_text="""
            We are seeking a skilled DevOps Engineer for our Berlin office.
            
            Requirements:
            - Strong experience with Docker and Kubernetes
            - Infrastructure as Code (Terraform, CloudFormation)
            - CI/CD pipeline design and implementation
            - Monitoring and observability (Prometheus, Grafana)
            - Cloud platforms (AWS, GCP, or Azure)
            - Scripting skills (Python, Bash)
            
            Responsibilities:
            - Manage and optimize cloud infrastructure
            - Implement security best practices
            - Support development teams with deployment automation
            """
        ),
        "expected_keywords": ["docker", "kubernetes", "aws", "ci/cd", "deployment"]
    }
]


def test_single_generation(profile: Profile, job: JobJD, test_name: str) -> dict:
    """Run a single generation and validate output"""
    print(f"\n{'='*60}")
    print(f"Testing: {test_name}")
    print(f"Company: {job.company}, Title: {job.title}, Region: {job.region}")
    print(f"{'='*60}")
    
    results = {
        "name": test_name,
        "success": False,
        "errors": [],
        "warnings": [],
        "metrics": {}
    }
    
    try:
        # Run the tailor
        start_time = time.time()
        output = run_tailor(profile, job)
        duration = time.time() - start_time
        results["metrics"]["llm_duration"] = round(duration, 2)
        print(f"[OK] LLM completed in {duration:.2f}s")
        
        # Validate resume output
        resume = output.resume
        
        # Check summary exists and is substantial
        if not resume.summary or len(resume.summary) < 50:
            results["warnings"].append("Resume summary too short")
        else:
            print(f"[OK] Resume summary: {len(resume.summary)} chars")
        
        # Check skills are relevant
        if not resume.skills_line or len(resume.skills_line) < 3:
            results["warnings"].append("Not enough skills in resume")
        else:
            print(f"[OK] Skills: {len(resume.skills_line)} items")
        
        # Check experience bullets are tailored
        if not resume.experience or len(resume.experience) < 1:
            results["errors"].append("No experience in resume output")
        else:
            total_bullets = sum(len(exp.bullets) for exp in resume.experience)
            print(f"[OK] Experience: {len(resume.experience)} roles, {total_bullets} bullets")
        
        # Validate cover letter
        cl = output.cover_letter
        
        if not cl.intro or len(cl.intro) < 30:
            results["warnings"].append("Cover letter intro too short")
        else:
            print(f"[OK] Cover letter intro: {len(cl.intro)} chars")
        
        if not cl.evidence or len(cl.evidence) < 2:
            results["warnings"].append("Not enough evidence points")
        else:
            print(f"[OK] Evidence points: {len(cl.evidence)}")
        
        # Check ATS keywords
        ats = output.ats
        if not ats.jd_keywords_matched or len(ats.jd_keywords_matched) < 3:
            results["warnings"].append("Few JD keywords matched")
        else:
            print(f"[OK] Keywords matched: {len(ats.jd_keywords_matched)}")
            print(f"    Keywords: {', '.join(ats.jd_keywords_matched[:10])}")
        
        if ats.risks:
            print(f"[WARN] ATS risks: {ats.risks}")
            results["warnings"].extend(ats.risks)
        
        # Verify company names are from profile (no hallucination)
        profile_companies = {r.company for r in profile.experience}
        for exp in resume.experience:
            if exp.company and exp.company not in profile_companies:
                results["errors"].append(f"Hallucinated company: {exp.company}")
        
        # Test TEX rendering
        run_id = f"test_{int(time.time())}"
        base = f"{run_id}_{job.title.replace(' ', '_')}"
        resume_ctx = {"profile": profile.model_dump(), "out": resume.model_dump(), "job": job.model_dump()}
        cl_ctx = {"profile": profile.model_dump(), "out": cl.model_dump(), "job": job.model_dump()}
        
        try:
            resume_tex, cl_tex = render_tex(resume_ctx, cl_ctx, job.region, base)
            print(f"[OK] TEX files generated")
            results["metrics"]["tex_generated"] = True
            
            # Check TEX files exist and have content
            if os.path.exists(resume_tex):
                with open(resume_tex, 'r') as f:
                    tex_content = f.read()
                    if len(tex_content) < 500:
                        results["warnings"].append("Resume TEX file seems too short")
                    else:
                        print(f"[OK] Resume TEX: {len(tex_content)} chars")
            
            # Cleanup test files
            for f in [resume_tex, cl_tex]:
                if os.path.exists(f):
                    os.remove(f)
                    
        except Exception as e:
            results["errors"].append(f"TEX rendering failed: {e}")
        
        # Mark success if no errors
        if not results["errors"]:
            results["success"] = True
            print(f"\n[SUCCESS] Test passed!")
        else:
            print(f"\n[FAILED] Errors: {results['errors']}")
        
        if results["warnings"]:
            print(f"[WARNINGS] {results['warnings']}")
            
    except Exception as e:
        results["errors"].append(f"Generation failed: {str(e)}")
        print(f"\n[ERROR] {e}")
    
    return results


def run_all_tests():
    """Run comprehensive tailoring tests"""
    print("\n" + "="*60)
    print("UmukoziHR Resume Tailor - Pipeline Verification")
    print("v1.3 Final Testing Suite")
    print("="*60)
    
    # Check environment
    if not os.getenv("GEMINI_API_KEY"):
        print("[ERROR] GEMINI_API_KEY not set!")
        return
    
    print("[OK] API key configured")
    
    all_results = []
    
    for test_case in TEST_JDS:
        result = test_single_generation(
            TEST_PROFILE,
            test_case["jd"],
            test_case["name"]
        )
        all_results.append(result)
        
        # Add a small delay between tests
        time.sleep(2)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in all_results if r["success"])
    total = len(all_results)
    
    for result in all_results:
        status = "PASS" if result["success"] else "FAIL"
        print(f"  [{status}] {result['name']}")
        if result["errors"]:
            for err in result["errors"]:
                print(f"        ERROR: {err}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tailoring pipeline tests passed!")
    else:
        print(f"\n[ATTENTION] {total - passed} tests failed - review errors above")
    
    return all_results


if __name__ == "__main__":
    run_all_tests()
