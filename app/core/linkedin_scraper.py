"""
LinkedIn Profile Scraper using Apify HarvestAPI
Extracts full profile data from LinkedIn URL - no cookies/auth needed.

Cost: $0.004 per profile ($4 per 1000)
Docs: https://apify.com/harvestapi/linkedin-profile-scraper
"""

import os
import re
import logging
import httpx
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_ACTOR_ID = "LpVuK3Zozwuipa5bp"  # harvestapi/linkedin-profile-scraper
APIFY_API_URL = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/run-sync-get-dataset-items"


def extract_linkedin_username(url_or_username: str) -> Optional[str]:
    """
    Extract LinkedIn public identifier from URL or validate username.
    
    Examples:
    - https://www.linkedin.com/in/williamhgates -> williamhgates
    - https://linkedin.com/in/john-doe-123 -> john-doe-123
    - williamhgates -> williamhgates (already a username)
    """
    url_or_username = url_or_username.strip()
    
    # Check if it's a full URL
    linkedin_patterns = [
        r'linkedin\.com/in/([a-zA-Z0-9\-]+)',
        r'linkedin\.com/in/([a-zA-Z0-9\-]+)/',
    ]
    
    for pattern in linkedin_patterns:
        match = re.search(pattern, url_or_username, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # Check if it's already a valid username (alphanumeric + hyphens)
    if re.match(r'^[a-zA-Z0-9\-]+$', url_or_username):
        return url_or_username
    
    return None


def scrape_linkedin_profile(url_or_username: str) -> Dict[str, Any]:
    """
    Scrape a LinkedIn profile and return structured data.
    
    Args:
        url_or_username: LinkedIn profile URL or username
        
    Returns:
        Dict with success status and profile data or error message
    """
    # Validate API token
    if not APIFY_TOKEN:
        logger.error("APIFY_API_TOKEN not configured")
        return {
            "success": False,
            "message": "LinkedIn scraping not configured. Please contact support.",
            "profile": None
        }
    
    # Extract username
    username = extract_linkedin_username(url_or_username)
    if not username:
        return {
            "success": False,
            "message": "Invalid LinkedIn URL or username. Please provide a valid link like linkedin.com/in/yourname",
            "profile": None
        }
    
    logger.info(f"Scraping LinkedIn profile: {username}")
    
    try:
        # Build the LinkedIn URL
        linkedin_url = f"https://www.linkedin.com/in/{username}"
        logger.info(f"Calling Apify with username: {username}")
        
        # Call Apify API - use publicIdentifiers for better results
        response = httpx.post(
            APIFY_API_URL,
            params={"token": APIFY_TOKEN},
            json={
                "publicIdentifiers": [username],  # Just the username, not full URL
                "scrapeProfileDetails": True,
                "scrapeEmail": False,  # Save money, we don't need email search
            },
            timeout=120.0  # LinkedIn scraping can take a while
        )
        
        logger.info(f"Apify response status: {response.status_code}")
        logger.debug(f"Apify response body: {response.text[:1000]}")
        
        if response.status_code not in [200, 201]:
            logger.error(f"Apify API error: {response.status_code} - {response.text[:500]}")
            return {
                "success": False,
                "message": "Failed to fetch LinkedIn profile. Please try again.",
                "profile": None
            }
        
        data = response.json()
        logger.info(f"Apify returned {len(data) if data else 0} profile(s) for {username}")
        
        if not data or len(data) == 0:
            logger.warning(f"No data returned for profile: {username}")
            return {
                "success": False,
                "message": "LinkedIn profile not found or is private. Please check the URL.",
                "profile": None
            }
        
        # Extract the first (and only) profile
        linkedin_profile = data[0]
        
        # Map to our ProfileV3 structure
        profile_v3 = map_linkedin_to_profile_v3(linkedin_profile)
        
        logger.info(f"Successfully scraped LinkedIn profile: {username}")
        return {
            "success": True,
            "message": "Profile extracted successfully!",
            "profile": profile_v3,
            "extraction_confidence": 0.95  # LinkedIn data is very structured
        }
        
    except httpx.TimeoutException:
        logger.error(f"Timeout scraping LinkedIn profile: {username}")
        return {
            "success": False,
            "message": "Request timed out. LinkedIn may be slow - please try again.",
            "profile": None
        }
    except Exception as e:
        logger.error(f"Error scraping LinkedIn profile: {e}", exc_info=True)
        return {
            "success": False,
            "message": "An error occurred while fetching your profile. Please try again.",
            "profile": None
        }


def map_linkedin_to_profile_v3(linkedin_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map LinkedIn API response to our ProfileV3 structure.
    Captures ALL available LinkedIn data for UmukoziHR Talent Rich!
    """
    # Extract name parts
    first_name = linkedin_data.get("firstName", "")
    last_name = linkedin_data.get("lastName", "")
    full_name = f"{first_name} {last_name}".strip()
    
    # Location
    location_data = linkedin_data.get("location", {})
    location = ""
    if isinstance(location_data, dict):
        location = location_data.get("linkedinText", "") or location_data.get("parsed", {}).get("text", "")
    elif isinstance(location_data, str):
        location = location_data
    
    # Basics
    basics = {
        "full_name": full_name,
        "headline": linkedin_data.get("headline", ""),
        "summary": linkedin_data.get("about", ""),
        "location": location,
        "email": "",  # Not available from public scrape
        "phone": "",
        "website": "",
        "links": [linkedin_data.get("linkedinUrl", "")]
    }
    
    # Experience
    experience = []
    for exp in linkedin_data.get("experience", []):
        # Parse dates
        start_date = ""
        end_date = "present"
        
        start_info = exp.get("startDate", {})
        if isinstance(start_info, dict):
            year = start_info.get("year", "")
            month = start_info.get("month", "")
            if year:
                # Convert month name to number if needed
                month_num = _month_to_num(month) if month else "01"
                start_date = f"{year}-{month_num}"
        
        end_info = exp.get("endDate", {})
        if isinstance(end_info, dict):
            if end_info.get("text", "").lower() == "present":
                end_date = "present"
            else:
                year = end_info.get("year", "")
                month = end_info.get("month", "")
                if year:
                    month_num = _month_to_num(month) if month else "12"
                    end_date = f"{year}-{month_num}"
        
        # Parse description into bullets
        description = exp.get("description", "")
        bullets = []
        if description:
            # Split by newlines or bullet points
            lines = re.split(r'\n+|\*|•|–|\d+\.\s', description)
            bullets = [line.strip() for line in lines if line.strip() and len(line.strip()) > 10]
        
        if not bullets and description:
            bullets = [description[:500]]  # Use description as single bullet
        
        experience.append({
            "title": exp.get("position", "") or exp.get("title", ""),
            "company": exp.get("companyName", ""),
            "location": exp.get("location", ""),
            "start": start_date,
            "end": end_date,
            "employment_type": (exp.get("employmentType", "") or "full-time").lower(),
            "bullets": bullets[:6]  # Max 6 bullets per role
        })
    
    # Education
    education = []
    for edu in linkedin_data.get("education", []):
        start_year = ""
        end_year = ""
        
        start_info = edu.get("startDate", {})
        if isinstance(start_info, dict):
            start_year = str(start_info.get("year", ""))
        
        end_info = edu.get("endDate", {})
        if isinstance(end_info, dict):
            end_year = str(end_info.get("year", ""))
        
        # Combine degree and field of study
        degree = edu.get("degree", "")
        field = edu.get("fieldOfStudy", "")
        full_degree = f"{degree} in {field}" if degree and field else (degree or field)
        
        education.append({
            "school": edu.get("schoolName", ""),
            "degree": full_degree,
            "start": start_year,
            "end": end_year,
            "gpa": edu.get("grade", None)
        })
    
    # Skills - extract from topSkills, skills array, and experience skills
    skills = []
    seen_skills = set()
    
    # Top skills first
    top_skills = linkedin_data.get("topSkills", "")
    if top_skills:
        skill_names = [s.strip() for s in top_skills.split("•") if s.strip()]
        for skill_name in skill_names:
            if skill_name.lower() not in seen_skills:
                skills.append({
                    "name": skill_name,
                    "level": "expert",  # Top skills = expert
                    "keywords": []
                })
                seen_skills.add(skill_name.lower())
    
    # Skills array if available
    for skill in linkedin_data.get("skills", []):
        skill_name = skill.get("name", "") if isinstance(skill, dict) else str(skill)
        if skill_name and skill_name.lower() not in seen_skills:
            skills.append({
                "name": skill_name,
                "level": "intermediate",
                "keywords": []
            })
            seen_skills.add(skill_name.lower())
    
    # Experience-attached skills
    for exp in linkedin_data.get("experience", []):
        exp_skills = exp.get("skills") or []
        for skill in exp_skills:
            if skill.lower() not in seen_skills:
                skills.append({
                    "name": skill,
                    "level": "intermediate", 
                    "keywords": []
                })
                seen_skills.add(skill.lower())
    
    # Projects
    projects = []
    for proj in linkedin_data.get("projects", []):
        projects.append({
            "name": proj.get("title", "") or proj.get("name", ""),
            "url": proj.get("url", ""),
            "stack": [],
            "bullets": [proj.get("description", "")] if proj.get("description") else []
        })
    
    # Certifications
    certifications = []
    for cert in linkedin_data.get("certifications", []):
        cert_date = ""
        if cert.get("startDate"):
            cert_date = str(cert.get("startDate", {}).get("year", ""))
        certifications.append({
            "name": cert.get("name", ""),
            "issuer": cert.get("authority", "") or cert.get("organization", ""),
            "date": cert_date
        })
    
    # Languages
    languages = []
    for lang in linkedin_data.get("languages", []):
        languages.append({
            "name": lang.get("name", ""),
            "level": lang.get("proficiency", "") or "Professional"
        })
    
    # Awards/Honors
    awards = []
    for honor in linkedin_data.get("honorsAndAwards", []):
        award_date = ""
        if honor.get("issuedOn"):
            award_date = str(honor.get("issuedOn", {}).get("year", ""))
        awards.append({
            "name": honor.get("title", ""),
            "by": honor.get("issuer", ""),
            "date": award_date
        })
    
    # Volunteering
    volunteering = []
    for vol in linkedin_data.get("volunteering", []):
        vol_start = ""
        vol_end = ""
        if vol.get("startDate"):
            vol_start = str(vol.get("startDate", {}).get("year", ""))
        if vol.get("endDate"):
            end_text = vol.get("endDate", {}).get("text", "")
            if "present" in end_text.lower():
                vol_end = "present"
            else:
                vol_end = str(vol.get("endDate", {}).get("year", ""))
        volunteering.append({
            "organization": vol.get("organizationName", "") or vol.get("organization", "") or vol.get("companyName", ""),
            "role": vol.get("role", "") or vol.get("title", ""),
            "cause": vol.get("cause", ""),
            "start": vol_start,
            "end": vol_end,
            "description": vol.get("description", "")
        })
    
    # Publications
    publications = []
    for pub in linkedin_data.get("publications", []):
        pub_date = ""
        if pub.get("publishedOn"):
            pub_date = str(pub.get("publishedOn", {}).get("year", ""))
        publications.append({
            "title": pub.get("title", "") or pub.get("name", ""),
            "publisher": pub.get("publisher", ""),
            "date": pub_date,
            "url": pub.get("url", ""),
            "description": pub.get("description", "")
        })
    
    # Courses
    courses = []
    for course in linkedin_data.get("courses", []):
        courses.append({
            "name": course.get("name", ""),
            "number": course.get("number", ""),
            "associated_with": course.get("associatedWith", "")
        })
    
    # LinkedIn Meta (talent intelligence)
    current_positions = linkedin_data.get("currentPosition", [])
    current_company = current_positions[0].get("companyName", "") if current_positions else ""
    
    linkedin_meta = {
        "linkedin_url": linkedin_data.get("linkedinUrl", ""),
        "linkedin_id": linkedin_data.get("id", "") or linkedin_data.get("publicIdentifier", ""),
        "photo_url": linkedin_data.get("photo", ""),
        "open_to_work": linkedin_data.get("openToWork", False),
        "hiring": linkedin_data.get("hiring", False),
        "premium": linkedin_data.get("premium", False),
        "verified": linkedin_data.get("verified", False),
        "influencer": linkedin_data.get("influencer", False),
        "connections_count": linkedin_data.get("connectionsCount", 0),
        "followers_count": linkedin_data.get("followerCount", 0),
        "registered_at": linkedin_data.get("registeredAt", ""),
        "current_company": current_company,
        "industry": linkedin_data.get("industry", "")
    }
    
    return {
        "basics": basics,
        "skills": skills,
        "experience": experience,
        "education": education,
        "projects": projects,
        "certifications": certifications,
        "awards": awards,
        "languages": languages,
        "volunteering": volunteering,
        "publications": publications,
        "courses": courses,
        "linkedin_meta": linkedin_meta,
        "preferences": {"regions": ["US"], "templates": ["minimal"]},
        "version": 1
    }


def _month_to_num(month_str: str) -> str:
    """Convert month name to 2-digit number."""
    if not month_str:
        return "01"
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12"
    }
    month_lower = month_str.lower()[:3]
    return months.get(month_lower, "01")
