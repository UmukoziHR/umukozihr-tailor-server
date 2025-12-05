"""
Job Description fetching endpoint
Attempts to scrape JD from URL, falls back to manual entry
"""
import logging
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from app.models import JDFetchRequest, JDFetchResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/jd/fetch", response_model=JDFetchResponse)
def fetch_jd(request: JDFetchRequest):
    """
    POST /api/v1/jd/fetch
    Attempt to fetch and parse job description from URL
    """
    url = request.url.strip()
    logger.info(f"Attempting to fetch JD from: {url}")

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        return JDFetchResponse(
            success=False,
            message="Invalid URL. Please provide a valid HTTP/HTTPS URL."
        )

    try:
        # Fetch with user agent and timeout
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract job title (try common selectors)
        title = None
        title_selectors = [
            "h1.job-title",
            "h1[class*='job']",
            "h1[class*='title']",
            ".job-title",
            "h1",
        ]
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                break

        # Extract company name
        company = None
        company_selectors = [
            ".company-name",
            "[class*='company']",
            "span.employer",
            ".employer-name",
        ]
        for selector in company_selectors:
            elem = soup.select_one(selector)
            if elem:
                company = elem.get_text(strip=True)
                break

        # Extract job description text
        jd_text = None
        jd_selectors = [
            ".job-description",
            "[class*='description']",
            ".job-details",
            "article",
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

        # If we got at least some text, consider it a success
        if jd_text and len(jd_text) > 100:
            logger.info(f"Successfully extracted JD ({len(jd_text)} chars)")
            return JDFetchResponse(
                success=True,
                jd_text=jd_text,
                company=company,
                title=title,
                region=None,  # Can't reliably detect region from URL
                message="Job description extracted successfully"
            )
        else:
            return JDFetchResponse(
                success=False,
                message="Could not extract enough text from page. Please paste JD manually."
            )

    except requests.Timeout:
        logger.warning(f"Timeout fetching URL: {url}")
        return JDFetchResponse(
            success=False,
            message="Request timed out. Please paste JD manually."
        )

    except requests.RequestException as e:
        logger.warning(f"Error fetching URL: {e}")
        return JDFetchResponse(
            success=False,
            message=f"Failed to fetch URL. Please paste JD manually."
        )

    except Exception as e:
        logger.error(f"Unexpected error parsing JD: {e}")
        return JDFetchResponse(
            success=False,
            message="Failed to parse page. Please paste JD manually."
        )
