"""
Job Description fetching endpoint
Attempts to scrape JD from URL with smart handlers for popular job boards
Supports: Ashby, Greenhouse, Lever, Workday, and generic pages via Jina Reader
"""
import logging
import re
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from app.models import JDFetchRequest, JDFetchResponse
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

router = APIRouter()

# Jina AI Reader - renders JavaScript and returns clean text
JINA_READER_URL = "https://r.jina.ai/"


def fetch_ashby_job(url: str) -> dict:
    """
    Fetch job from Ashby using their public posting API
    URL format: https://jobs.ashbyhq.com/{company}/{job_id}
    """
    match = re.match(r'https?://jobs\.ashbyhq\.com/([^/]+)/([^/\?]+)', url)
    if not match:
        return None
    
    company_slug = match.group(1)
    job_id = match.group(2)
    
    logger.info(f"Fetching Ashby job: company={company_slug}, job_id={job_id}")
    
    # Fetch all jobs from company's job board
    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Find the specific job by ID
        for job in data.get('jobs', []):
            if job.get('id') == job_id:
                # Build JD text from job data
                jd_parts = []
                if job.get('title'):
                    jd_parts.append(f"Position: {job['title']}")
                if job.get('location'):
                    jd_parts.append(f"Location: {job['location']}")
                if job.get('department'):
                    jd_parts.append(f"Department: {job['department']}")
                if job.get('employmentType'):
                    jd_parts.append(f"Type: {job['employmentType']}")
                if job.get('descriptionHtml'):
                    # Parse HTML description
                    soup = BeautifulSoup(job['descriptionHtml'], 'html.parser')
                    jd_parts.append("\n" + soup.get_text(separator="\n", strip=True))
                elif job.get('descriptionPlain'):
                    jd_parts.append("\n" + job['descriptionPlain'])
                
                return {
                    'success': True,
                    'title': job.get('title'),
                    'company': company_slug.replace('-', ' ').title(),
                    'jd_text': "\n".join(jd_parts),
                    'region': detect_region(job.get('location', ''))
                }
        
        logger.warning(f"Job ID {job_id} not found in Ashby response")
        return None
        
    except Exception as e:
        logger.warning(f"Ashby API error: {e}")
        return None


def fetch_greenhouse_job(url: str) -> dict:
    """
    Fetch job from Greenhouse using their public API
    URL formats:
    - https://boards.greenhouse.io/{company}/jobs/{job_id}
    - https://{company}.greenhouse.io/jobs/{job_id}
    """
    # Pattern 1: boards.greenhouse.io
    match = re.match(r'https?://boards\.greenhouse\.io/([^/]+)/jobs/(\d+)', url)
    if not match:
        # Pattern 2: {company}.greenhouse.io
        match = re.match(r'https?://([^.]+)\.greenhouse\.io/jobs/(\d+)', url)
    
    if not match:
        return None
    
    company_slug = match.group(1)
    job_id = match.group(2)
    
    logger.info(f"Fetching Greenhouse job: company={company_slug}, job_id={job_id}")
    
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs/{job_id}"
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        job = response.json()
        
        jd_parts = []
        if job.get('title'):
            jd_parts.append(f"Position: {job['title']}")
        if job.get('location', {}).get('name'):
            jd_parts.append(f"Location: {job['location']['name']}")
        if job.get('content'):
            soup = BeautifulSoup(job['content'], 'html.parser')
            jd_parts.append("\n" + soup.get_text(separator="\n", strip=True))
        
        return {
            'success': True,
            'title': job.get('title'),
            'company': company_slug.replace('-', ' ').title(),
            'jd_text': "\n".join(jd_parts),
            'region': detect_region(job.get('location', {}).get('name', ''))
        }
        
    except Exception as e:
        logger.warning(f"Greenhouse API error: {e}")
        return None


def fetch_lever_job(url: str) -> dict:
    """
    Fetch job from Lever using their public API
    URL format: https://jobs.lever.co/{company}/{job_id}
    """
    match = re.match(r'https?://jobs\.lever\.co/([^/]+)/([^/\?]+)', url)
    if not match:
        return None
    
    company_slug = match.group(1)
    job_id = match.group(2)
    
    logger.info(f"Fetching Lever job: company={company_slug}, job_id={job_id}")
    
    api_url = f"https://api.lever.co/v0/postings/{company_slug}/{job_id}"
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        job = response.json()
        
        jd_parts = []
        if job.get('text'):
            jd_parts.append(f"Position: {job['text']}")
        if job.get('categories', {}).get('location'):
            jd_parts.append(f"Location: {job['categories']['location']}")
        if job.get('categories', {}).get('team'):
            jd_parts.append(f"Team: {job['categories']['team']}")
        if job.get('descriptionPlain'):
            jd_parts.append("\n" + job['descriptionPlain'])
        
        # Also add lists (requirements, responsibilities, etc.)
        for lst in job.get('lists', []):
            if lst.get('text'):
                jd_parts.append(f"\n{lst['text']}:")
            if lst.get('content'):
                soup = BeautifulSoup(lst['content'], 'html.parser')
                jd_parts.append(soup.get_text(separator="\n", strip=True))
        
        return {
            'success': True,
            'title': job.get('text'),
            'company': company_slug.replace('-', ' ').title(),
            'jd_text': "\n".join(jd_parts),
            'region': detect_region(job.get('categories', {}).get('location', ''))
        }
        
    except Exception as e:
        logger.warning(f"Lever API error: {e}")
        return None


def fetch_via_jina_reader(url: str) -> dict:
    """
    Fallback: Use Jina AI Reader to fetch and render JavaScript pages
    This handles any JS-rendered page by returning clean text
    """
    logger.info(f"Fetching via Jina Reader: {url}")
    
    jina_url = f"{JINA_READER_URL}{url}"
    try:
        headers = {
            "Accept": "text/plain",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(jina_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        text = response.text
        
        # Extract title from first line if it looks like a title
        lines = text.strip().split('\n')
        title = None
        company = None
        
        # Try to find title and company from the text
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            if not title and len(line) > 5 and len(line) < 100:
                # First meaningful line is often the title
                if not line.startswith(('http', '#', '!', '[')):
                    title = line
                    break
        
        # Try to extract company from URL
        parsed = urlparse(url)
        domain_parts = parsed.netloc.split('.')
        if 'jobs' in domain_parts:
            domain_parts.remove('jobs')
        if domain_parts:
            company = domain_parts[0].replace('-', ' ').title()
        
        if len(text) > 200:
            return {
                'success': True,
                'title': title,
                'company': company,
                'jd_text': text,
                'region': detect_region(text[:500])
            }
        
        return None
        
    except Exception as e:
        logger.warning(f"Jina Reader error: {e}")
        return None


def detect_region(location_text: str) -> str:
    """
    Try to detect region from location text
    """
    location_lower = location_text.lower()
    
    # US indicators
    us_states = ['usa', 'united states', 'california', 'new york', 'texas', 'washington', 
                 'san francisco', 'los angeles', 'seattle', 'austin', 'boston', 'chicago',
                 'denver', 'atlanta', 'miami', 'nyc', 'sf', 'la', ', ca', ', ny', ', tx',
                 ', wa', ', co', ', ma', ', fl', ', ga', ', il']
    if any(state in location_lower for state in us_states):
        return 'US'
    
    # EU indicators  
    eu_countries = ['europe', 'uk', 'united kingdom', 'germany', 'france', 'netherlands',
                    'ireland', 'spain', 'italy', 'poland', 'sweden', 'berlin', 'london',
                    'paris', 'amsterdam', 'dublin', 'munich', 'stockholm', 'emea']
    if any(country in location_lower for country in eu_countries):
        return 'EU'
    
    return 'GL'  # Global/default


@router.post("/jd/fetch", response_model=JDFetchResponse)
def fetch_jd(request: JDFetchRequest):
    """
    POST /api/v1/jd/fetch
    Attempt to fetch and parse job description from URL
    
    Supports:
    - Ashby (jobs.ashbyhq.com)
    - Greenhouse (boards.greenhouse.io)
    - Lever (jobs.lever.co)
    - Any other URL via Jina AI Reader (handles JavaScript)
    """
    url = request.url.strip()
    logger.info(f"Attempting to fetch JD from: {url}")

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        return JDFetchResponse(
            success=False,
            message="Invalid URL. Please provide a valid HTTP/HTTPS URL."
        )

    result = None
    
    # Try specific job board handlers first (faster, more reliable)
    if 'ashbyhq.com' in url:
        result = fetch_ashby_job(url)
    elif 'greenhouse.io' in url:
        result = fetch_greenhouse_job(url)
    elif 'lever.co' in url:
        result = fetch_lever_job(url)
    
    # If specific handler failed or not matched, try Jina Reader
    if not result:
        logger.info("Specific handler not available, trying Jina Reader...")
        result = fetch_via_jina_reader(url)
    
    # If Jina also failed, try basic requests as last resort
    if not result:
        logger.info("Jina Reader failed, trying basic fetch...")
        result = fetch_basic(url)
    
    if result and result.get('success'):
        return JDFetchResponse(
            success=True,
            jd_text=result.get('jd_text'),
            company=result.get('company'),
            title=result.get('title'),
            region=result.get('region'),
            message="Job description extracted successfully"
        )
    else:
        return JDFetchResponse(
            success=False,
            message="Could not extract job description. Please paste JD manually."
        )


def fetch_basic(url: str) -> dict:
    """
    Basic HTML fetch - works for static pages only
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract job title
        title = None
        title_selectors = [
            "h1.job-title", "h1[class*='job']", "h1[class*='title']",
            ".job-title", "[data-testid='job-title']", "h1",
        ]
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                break

        # Extract company name
        company = None
        company_selectors = [
            ".company-name", "[class*='company']", "span.employer",
            ".employer-name", "[data-testid='company-name']",
        ]
        for selector in company_selectors:
            elem = soup.select_one(selector)
            if elem:
                company = elem.get_text(strip=True)
                break

        # Extract job description text
        jd_text = None
        jd_selectors = [
            ".job-description", "[class*='description']", ".job-details",
            "[data-testid='job-description']", "article", "main",
        ]
        for selector in jd_selectors:
            elem = soup.select_one(selector)
            if elem:
                jd_text = elem.get_text(separator="\n", strip=True)
                break

        # Fallback: get all paragraph text
        if not jd_text:
            paragraphs = soup.find_all("p")
            if paragraphs:
                jd_text = "\n\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

        if jd_text and len(jd_text) > 100:
            return {
                'success': True,
                'title': title,
                'company': company,
                'jd_text': jd_text,
                'region': detect_region(jd_text[:500])
            }
        
        return None

    except Exception as e:
        logger.warning(f"Basic fetch error: {e}")
        return None
