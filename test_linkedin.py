#!/usr/bin/env python3
"""
Test LinkedIn profile extraction for Jason's profile.
Run this to verify the Apify integration works correctly.

Usage:
    APIFY_API_TOKEN=your_token python test_linkedin.py
"""
import os
import sys
import json

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.linkedin_scraper import scrape_linkedin_profile, extract_linkedin_username

# Test profile
TEST_PROFILE_URL = "https://www.linkedin.com/in/jason-quist/"

def main():
    print("=" * 60)
    print("LinkedIn Profile Extraction Test")
    print("=" * 60)
    
    # Check API token
    token = os.getenv("APIFY_API_TOKEN", "")
    if not token:
        print("\n❌ ERROR: APIFY_API_TOKEN not set!")
        print("   Get your token at: https://console.apify.com/settings/integrations")
        print("   Then run: APIFY_API_TOKEN=your_token python test_linkedin.py")
        return
    
    print(f"\n✓ API Token found (ends with ...{token[-6:]})")
    
    # Test URL extraction
    username = extract_linkedin_username(TEST_PROFILE_URL)
    print(f"\n✓ Extracted username: {username}")
    
    # Scrape profile
    print(f"\n⏳ Scraping profile: {TEST_PROFILE_URL}")
    print("   (This may take 30-60 seconds...)")
    
    result = scrape_linkedin_profile(TEST_PROFILE_URL)
    
    if not result["success"]:
        print(f"\n❌ Extraction failed: {result['message']}")
        return
    
    print(f"\n✓ Extraction successful!")
    print(f"  Confidence: {result.get('extraction_confidence', 0) * 100}%")
    
    profile = result["profile"]
    
    # Display summary
    print("\n" + "=" * 60)
    print("PROFILE SUMMARY")
    print("=" * 60)
    
    basics = profile.get("basics", {})
    print(f"\nName: {basics.get('full_name', 'N/A')}")
    print(f"Headline: {basics.get('headline', 'N/A')[:80]}...")
    print(f"Location: {basics.get('location', 'N/A')}")
    
    print(f"\n📋 Experience: {len(profile.get('experience', []))} roles")
    for exp in profile.get("experience", [])[:3]:
        print(f"   - {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('start', '')} - {exp.get('end', '')})")
        print(f"     Bullets: {len(exp.get('bullets', []))}")
    
    print(f"\n🎓 Education: {len(profile.get('education', []))} entries")
    for edu in profile.get("education", []):
        print(f"   - {edu.get('degree', '')} at {edu.get('school', '')}")
    
    print(f"\n💡 Skills: {len(profile.get('skills', []))} skills")
    skill_names = [s.get('name', '') for s in profile.get("skills", [])[:5]]
    print(f"   Top: {', '.join(skill_names)}")
    
    print(f"\n📜 Certifications: {len(profile.get('certifications', []))}")
    for cert in profile.get("certifications", []):
        print(f"   - {cert.get('name', '')} ({cert.get('issuer', '')})")
    
    print(f"\n🏆 Awards: {len(profile.get('awards', []))}")
    for award in profile.get("awards", []):
        print(f"   - {award.get('name', '')} by {award.get('by', '')}")
    
    print(f"\n🌍 Languages: {len(profile.get('languages', []))}")
    for lang in profile.get("languages", []):
        print(f"   - {lang.get('name', '')} ({lang.get('level', '')})")
    
    print(f"\n🤝 Volunteering: {len(profile.get('volunteering', []))}")
    for vol in profile.get("volunteering", []):
        print(f"   - {vol.get('role', '')} at {vol.get('organization', '')}")
    
    print(f"\n📚 Publications: {len(profile.get('publications', []))}")
    print(f"📖 Courses: {len(profile.get('courses', []))}")
    
    # LinkedIn Meta
    meta = profile.get("linkedin_meta", {})
    if meta:
        print(f"\n" + "=" * 60)
        print("LINKEDIN META (Talent Intelligence)")
        print("=" * 60)
        print(f"Profile URL: {meta.get('linkedin_url', 'N/A')}")
        print(f"Photo URL: {meta.get('photo_url', 'N/A')[:50]}..." if meta.get('photo_url') else "Photo: N/A")
        print(f"Open to Work: {meta.get('open_to_work', False)}")
        print(f"Hiring: {meta.get('hiring', False)}")
        print(f"Premium: {meta.get('premium', False)}")
        print(f"Verified: {meta.get('verified', False)}")
        print(f"Connections: {meta.get('connections_count', 0)}")
        print(f"Followers: {meta.get('followers_count', 0)}")
        print(f"Current Company: {meta.get('current_company', 'N/A')}")
    
    # Save full output
    output_file = "test_linkedin_output.json"
    with open(output_file, "w") as f:
        json.dump(profile, f, indent=2)
    print(f"\n✓ Full profile saved to: {output_file}")
    
    print("\n" + "=" * 60)
    print("✅ TEST PASSED - LinkedIn extraction working correctly!")
    print("=" * 60)

if __name__ == "__main__":
    main()
