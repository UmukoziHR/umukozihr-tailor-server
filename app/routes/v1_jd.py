"""
Job Description fetching endpoint
Attempts to scrape JD from URL with smart handlers for popular job boards
Supports: LinkedIn, Ashby, Greenhouse, Lever, and generic pages via Jina Reader
"""
import logging
import re
import requests
import time
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from app.models import JDFetchRequest, JDFetchResponse
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

router = APIRouter()

# Jina AI Reader - renders JavaScript and returns clean text
JINA_READER_URL = "https://r.jina.ai/"

# Patterns indicating garbage/error content rather than a real JD
GARBAGE_PATTERNS = [
    # Error pages
    r'access\s*denied',
    r'page\s*not\s*found',
    r'404\s*(error|not\s*found)',
    r'403\s*forbidden',
    r'error\s*occurred',
    r'something\s*went\s*wrong',
    r'unable\s*to\s*(load|fetch|find)',
    r'this\s*page\s*(is\s*not|cannot)',
    # Auth walls
    r'sign\s*in\s*(to\s*view|required|to\s*continue)',
    r'login\s*(required|to\s*view|to\s*continue)',
    r'please\s*log\s*in',
    r'create\s*(an\s*)?account\s*to',
    r'join\s*to\s*view',
    r'authwall',
    # Bot detection
    r'captcha',
    r'verify\s*you\s*are\s*(human|not\s*a\s*robot)',
    r'cloudflare',
    r'security\s*check',
    r'bot\s*detection',
    r'unusual\s*traffic',
    # Cookie/consent
    r'cookie\s*(policy|consent)',
    r'accept\s*(all\s*)?cookies',
    r'we\s*use\s*cookies',
    # Generic errors
    r'oops',
    r'sorry,\s*(we|this)',
    r'temporarily\s*unavailable',
    r'try\s*again\s*later',
    r'session\s*(expired|timeout)',
]

# Keywords that should be present in a valid job description
JD_REQUIRED_KEYWORDS = [
    'experience', 'requirements', 'responsibilities', 'qualifications',
    'skills', 'role', 'position', 'about', 'we are looking', 'looking for',
    'job description', 'what you', 'who you', 'you will', 'your responsibilities',
    'your role', 'team', 'company', 'benefits', 'salary', 'compensation',
    'apply', 'candidate', 'work with', 'collaborate', 'develop', 'manage',
]


def validate_jd_content(text: str) -> tuple[bool, str]:
    """
    Validate that the fetched content is actually a job description,
    not an error page, captcha, or garbage.
    
    Returns: (is_valid, error_message)
    """
    if not text:
        return False, "No content extracted from the page."
    
    text_lower = text.lower()
    text_len = len(text)
    
    # Too short to be a real JD
    if text_len < 300:
        return False, "Content too short to be a valid job description."
    
    # Check for garbage patterns
    for pattern in GARBAGE_PATTERNS:
        if re.search(pattern, text_lower):
            # Don't flag if the pattern is just a small part of a larger text
            if text_len < 1000:
                return False, "The page returned an error or requires login. Please copy the job description and paste it manually."
    
    # Check if content has JD-like keywords
    keyword_count = sum(1 for kw in JD_REQUIRED_KEYWORDS if kw in text_lower)
    
    # Need at least 3 JD-related keywords for a valid JD
    if keyword_count < 3:
        # Check if text is mostly navigation/boilerplate
        nav_patterns = ['menu', 'navigation', 'footer', 'header', 'copyright', 'privacy policy', 'terms of']
        nav_count = sum(1 for p in nav_patterns if p in text_lower)
        
        if nav_count >= 2 and keyword_count < 2:
            return False, "The page appears to be mostly navigation or boilerplate. Please copy the actual job description and paste it manually."
    
    # Check for too much repetition (sign of broken scraping)
    words = text.split()
    if len(words) > 50:
        unique_words = set(words)
        repetition_ratio = len(unique_words) / len(words)
        if repetition_ratio < 0.2:  # Less than 20% unique words = very repetitive
            return False, "Content appears corrupted or repetitive. Please copy the job description manually."
    
    return True, ""


# Common headers to mimic a real browser
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def extract_linkedin_job_id(url: str) -> str:
    """
    Extract LinkedIn job ID from various URL formats:
    - https://www.linkedin.com/jobs/view/{job_id}
    - https://www.linkedin.com/jobs/collections/recommended/?currentJobId={job_id}
    - https://www.linkedin.com/jobs/search/?currentJobId={job_id}
    - https://linkedin.com/jobs/view/{job_id}
    """
    # Pattern 1: /jobs/view/{job_id}
    match = re.search(r'/jobs/view/(\d+)', url)
    if match:
        return match.group(1)
    
    # Pattern 2: currentJobId query parameter
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    if 'currentJobId' in query_params:
        return query_params['currentJobId'][0]
    
    return None


def fetch_linkedin_job(url: str) -> dict:
    """
    Fetch job from LinkedIn using their hidden guest API
    API endpoint: https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}
    """
    job_id = extract_linkedin_job_id(url)
    if not job_id:
        logger.warning(f"Could not extract LinkedIn job ID from: {url}")
        return None
    
    logger.info(f"Fetching LinkedIn job: job_id={job_id}")
    
    # LinkedIn's hidden guest API endpoint
    api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    
    try:
        # Use browser-like headers to avoid blocks
        headers = BROWSER_HEADERS.copy()
        headers["Referer"] = "https://www.linkedin.com/jobs/search/"
        
        response = requests.get(api_url, headers=headers, timeout=15)
        
        if response.status_code == 404:
            logger.warning(f"LinkedIn job {job_id} not found (404)")
            return None
        
        response.raise_for_status()
        
        # The API returns HTML, not JSON - parse it
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract job title
        title = None
        title_elem = soup.select_one('h2.top-card-layout__title, h1.topcard__title, .job-details-jobs-unified-top-card__job-title')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # Extract company name
        company = None
        company_elem = soup.select_one('a.topcard__org-name-link, .topcard__flavor--black-link, .job-details-jobs-unified-top-card__company-name')
        if company_elem:
            company = company_elem.get_text(strip=True)
        
        # Extract location
        location = None
        location_elem = soup.select_one('.topcard__flavor--bullet, .job-details-jobs-unified-top-card__bullet')
        if location_elem:
            location = location_elem.get_text(strip=True)
        
        # Extract job description
        jd_text = None
        desc_elem = soup.select_one('.description__text, .show-more-less-html__markup, .job-details-jobs-unified-top-card__job-insight')
        if desc_elem:
            jd_text = desc_elem.get_text(separator="\n", strip=True)
        
        # If description not found, try to get all content from the main section
        if not jd_text:
            main_content = soup.select_one('.decorated-job-posting__details, .details, section.description')
            if main_content:
                jd_text = main_content.get_text(separator="\n", strip=True)
        
        # Last resort - get the entire page text
        if not jd_text or len(jd_text) < 100:
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            jd_text = soup.get_text(separator="\n", strip=True)
        
        if jd_text and len(jd_text) > 100:
            # Build structured JD
            jd_parts = []
            if title:
                jd_parts.append(f"Position: {title}")
            if company:
                jd_parts.append(f"Company: {company}")
            if location:
                jd_parts.append(f"Location: {location}")
            jd_parts.append("\n" + jd_text)
            
            return {
                'success': True,
                'title': title,
                'company': company,
                'jd_text': "\n".join(jd_parts),
                'region': detect_region(location or jd_text[:500])
            }
        
        logger.warning(f"LinkedIn job {job_id}: insufficient content extracted")
        return None
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.warning(f"LinkedIn rate limited (429). Waiting and retrying...")
            time.sleep(2)
            # Retry once
            try:
                response = requests.get(api_url, headers=headers, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                for script in soup(["script", "style", "nav", "header", "footer"]):
                    script.decompose()
                jd_text = soup.get_text(separator="\n", strip=True)
                if jd_text and len(jd_text) > 100:
                    return {
                        'success': True,
                        'title': None,
                        'company': None,
                        'jd_text': jd_text,
                        'region': 'GL'
                    }
            except:
                pass
        logger.warning(f"LinkedIn HTTP error: {e}")
        return None
    except Exception as e:
        logger.warning(f"LinkedIn API error: {e}")
        return None


def fetch_linkedin_via_public_view(url: str) -> dict:
    """
    Alternative: Try to fetch LinkedIn job via the public view page
    Sometimes works when the API doesn't
    """
    job_id = extract_linkedin_job_id(url)
    if not job_id:
        return None
    
    # Construct public view URL
    public_url = f"https://www.linkedin.com/jobs/view/{job_id}"
    logger.info(f"Trying LinkedIn public view: {public_url}")
    
    try:
        headers = BROWSER_HEADERS.copy()
        response = requests.get(public_url, headers=headers, timeout=15, allow_redirects=True)
        
        # Check if we got redirected to login
        if 'login' in response.url or 'authwall' in response.url:
            logger.warning("LinkedIn redirected to login page")
            return None
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for elem in soup(["script", "style", "nav", "header", "footer", "aside"]):
            elem.decompose()
        
        # Try to extract structured data from JSON-LD
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld:
            import json
            try:
                data = json.loads(json_ld.string)
                if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                    return {
                        'success': True,
                        'title': data.get('title'),
                        'company': data.get('hiringOrganization', {}).get('name'),
                        'jd_text': data.get('description', ''),
                        'region': detect_region(data.get('jobLocation', {}).get('address', {}).get('addressCountry', ''))
                    }
            except:
                pass
        
        # Fallback: extract text content
        main = soup.select_one('main, .job-view-layout, article')
        if main:
            text = main.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return {
                    'success': True,
                    'title': None,
                    'company': None,
                    'jd_text': text,
                    'region': detect_region(text[:500])
                }
        
        return None
        
    except Exception as e:
        logger.warning(f"LinkedIn public view error: {e}")
        return None


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
        if 'www' in domain_parts:
            domain_parts.remove('www')
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
    - LinkedIn (linkedin.com/jobs) - via hidden guest API
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
    if 'linkedin.com' in url:
        logger.info("Detected LinkedIn URL, trying guest API...")
        result = fetch_linkedin_job(url)
        
        # If guest API failed, try public view
        if not result:
            logger.info("LinkedIn guest API failed, trying public view...")
            result = fetch_linkedin_via_public_view(url)
        
        # If both failed, try Jina as last resort for LinkedIn
        if not result:
            logger.info("LinkedIn direct methods failed, trying Jina Reader...")
            result = fetch_via_jina_reader(url)
        
        # If everything failed for LinkedIn, return helpful message
        if not result:
            return JDFetchResponse(
                success=False,
                message="LinkedIn requires login for this job. Please copy the job description from LinkedIn and paste it manually."
            )
    
    elif 'ashbyhq.com' in url:
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
        jd_text = result.get('jd_text', '')
        
        # Validate that the content is actually a job description
        is_valid, error_msg = validate_jd_content(jd_text)
        
        if not is_valid:
            logger.warning(f"JD validation failed for {url}: {error_msg}")
            return JDFetchResponse(
                success=False,
                message=error_msg
            )
        
        logger.info(f"Successfully extracted JD: title={result.get('title')}, company={result.get('company')}, length={len(jd_text)}")
        return JDFetchResponse(
            success=True,
            jd_text=jd_text,
            company=result.get('company'),
            title=result.get('title'),
            region=result.get('region'),
            message="Job description extracted successfully"
        )
    else:
        return JDFetchResponse(
            success=False,
            message="Could not extract job description from this URL. Please copy the job description from the job posting and paste it manually."
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
