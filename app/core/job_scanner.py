"""
Job Scanner Service — UmukoziHR Tailor v2.5
Discovers jobs from configured company career pages using Playwright, Greenhouse API, and httpx.
"""
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-configured companies (from CareerOps portals.example.yml)
# ---------------------------------------------------------------------------

DEFAULT_COMPANIES = [
    # AI Labs — from CareerOps verified slugs
    {"name": "Anthropic",     "api_slug": "anthropic",  "url": "https://job-boards.greenhouse.io/anthropic",  "platform": "greenhouse"},
    {"name": "PolyAI",        "api_slug": "polyai",     "url": "https://job-boards.eu.greenhouse.io/polyai",  "platform": "greenhouse"},
    {"name": "Hume AI",       "api_slug": "humeai",     "url": "https://job-boards.greenhouse.io/humeai",     "platform": "greenhouse"},
    {"name": "Intercom",      "api_slug": "intercom",   "url": "https://job-boards.greenhouse.io/intercom",   "platform": "greenhouse"},
    # Voice AI
    {"name": "ElevenLabs",    "url": "https://jobs.ashbyhq.com/elevenlabs",   "platform": "ashby"},
    {"name": "Deepgram",      "url": "https://jobs.ashbyhq.com/deepgram",     "platform": "ashby"},
    {"name": "Vapi",          "url": "https://jobs.ashbyhq.com/vapi",         "platform": "ashby"},
    # AI Platforms
    {"name": "Vercel",        "api_slug": "vercel",     "url": "https://job-boards.greenhouse.io/vercel",    "platform": "greenhouse"},
    {"name": "Temporal",      "api_slug": "temporal",   "url": "https://job-boards.greenhouse.io/temporal",  "platform": "greenhouse"},
    {"name": "Glean",         "api_slug": "gleanwork",  "url": "https://job-boards.greenhouse.io/gleanwork", "platform": "greenhouse"},
    {"name": "Airtable",      "api_slug": "airtable",   "url": "https://job-boards.greenhouse.io/airtable",  "platform": "greenhouse"},
    {"name": "Arize AI",      "api_slug": "arizeai",    "url": "https://job-boards.greenhouse.io/arizeai",   "platform": "greenhouse"},
    # Agentic / Automation
    {"name": "LangChain",     "url": "https://jobs.ashbyhq.com/langchain",   "platform": "ashby"},
    {"name": "n8n",           "url": "https://jobs.ashbyhq.com/n8n",         "platform": "ashby"},
    # Contact Center AI
    {"name": "Ada",           "url": "https://jobs.ashbyhq.com/ada",         "platform": "ashby"},
    {"name": "Sierra",        "url": "https://jobs.ashbyhq.com/sierra",      "platform": "ashby"},
    {"name": "Parloa",        "api_slug": "parloa",     "url": "https://job-boards.eu.greenhouse.io/parloa", "platform": "greenhouse"},
    # Data / LLMOps
    {"name": "Langfuse",      "url": "https://jobs.ashbyhq.com/langfuse",    "platform": "ashby"},
    {"name": "Tinybird",      "url": "https://jobs.ashbyhq.com/tinybird",    "platform": "ashby"},
    {"name": "RunPod",        "api_slug": "runpod",     "url": "https://job-boards.greenhouse.io/runpod",    "platform": "greenhouse"},
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredJobData:
    company: str
    title: str
    url: str
    platform: str
    scan_source: str  # playwright, api, httpx


@dataclass
class ScanResult:
    new_jobs: int = 0
    total_found: int = 0
    skipped_duplicates: int = 0
    errors: list = field(default_factory=list)
    scan_started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ---------------------------------------------------------------------------
# Title filtering
# ---------------------------------------------------------------------------

def _title_matches_filters(
    title: str,
    positive: list[str],
    negative: list[str],
) -> bool:
    """Return True if title matches positive keywords and does not match negative keywords."""
    title_lower = title.lower()
    if negative and any(kw.lower() in title_lower for kw in negative):
        return False
    if positive and not any(kw.lower() in title_lower for kw in positive):
        return False
    return True


# ---------------------------------------------------------------------------
# Greenhouse API scanner
# ---------------------------------------------------------------------------

async def _scan_greenhouse_api(company: dict) -> list[DiscoveredJobData]:
    """Fetch jobs from Greenhouse public API."""
    api_slug = company.get("api_slug")
    if not api_slug:
        return []

    url = f"https://boards-api.greenhouse.io/v1/boards/{api_slug}/jobs?content=false"
    jobs = []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            raw_jobs = data.get("jobs", [])

            for j in raw_jobs:
                title = j.get("title", "")
                job_url = j.get("absolute_url", "")
                if title and job_url:
                    jobs.append(DiscoveredJobData(
                        company=company["name"],
                        title=title,
                        url=job_url,
                        platform="greenhouse",
                        scan_source="api",
                    ))
    except Exception as e:
        logger.warning(f"Greenhouse API scan failed for {company['name']}: {e}")

    return jobs


# ---------------------------------------------------------------------------
# Playwright scanner
# ---------------------------------------------------------------------------

async def _scan_ashby_api(company: dict) -> list[DiscoveredJobData]:
    """Scan an Ashby job board via their embed API (no auth required for public boards)."""
    # Extract company slug from URL like https://jobs.ashbyhq.com/vercel → vercel
    url = company.get("url", "")
    import re as _re
    match = _re.search(r"ashbyhq\.com/([^/]+)", url)
    if not match:
        return []
    slug = match.group(1)

    jobs = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Ashby's iFrame embed API endpoint (publicly accessible)
            resp = await client.get(
                f"https://jobs.ashbyhq.com/api/non-user-graphql",
                params={"op": "ApiJobBoardWithTeams"},
                headers={"Content-Type": "application/json"},
            )
            # Fallback: try their public JSON feed
            if resp.status_code != 200:
                return []
    except Exception:
        pass

    # Ashby iFrame embed: fetch the rendered page and parse JSON from __NEXT_DATA__
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; UmukoziHR/2.5 job-scanner)"
            })
            if resp.status_code != 200:
                return []
        import json as _json
        import re as _re2
        # Next.js pages embed __NEXT_DATA__ with the full page props as JSON
        match = _re2.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', resp.text, _re2.DOTALL)
        if not match:
            return []
        data = _json.loads(match.group(1))
        postings = (
            data.get("props", {}).get("pageProps", {}).get("jobPostings")
            or data.get("props", {}).get("pageProps", {}).get("jobs")
            or []
        )
        for post in postings:
            title = post.get("title") or post.get("name", "")
            job_path = post.get("jobUrl") or post.get("externalLink") or post.get("id", "")
            if job_path and not job_path.startswith("http"):
                job_path = f"https://jobs.ashbyhq.com/{slug}/{job_path}"
            if title and job_path:
                jobs.append(DiscoveredJobData(
                    company=company["name"],
                    title=title,
                    url=job_path,
                    platform="ashby",
                    scan_source="api",
                ))
    except Exception as e:
        logger.debug(f"Ashby __NEXT_DATA__ parse failed for {company['name']}: {e}")

    return jobs


async def _scan_with_playwright(company: dict) -> list[DiscoveredJobData]:
    """Scan a career page using Playwright headless Chromium."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("playwright not installed — skipping Playwright scan")
        return []

    url = company.get("url")
    if not url:
        return []

    platform = company.get("platform", "custom")
    jobs = []

    try:
        import sys
        # Windows requires ProactorEventLoop for Playwright subprocess transport
        if sys.platform == "win32":
            import asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.content()
            await browser.close()

        soup = BeautifulSoup(content, "html.parser")
        jobs = _parse_job_listings(soup, company["name"], platform, url)

    except Exception as e:
        logger.warning(f"Playwright scan failed for {company['name']} ({url}): {e}")

    return jobs


def _parse_job_listings(
    soup: BeautifulSoup,
    company_name: str,
    platform: str,
    base_url: str,
) -> list[DiscoveredJobData]:
    """Extract job listings from parsed HTML based on platform heuristics."""
    jobs = []
    parsed_base = urlparse(base_url)
    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"

    if platform == "ashby":
        # Ashby: job links have /jobs/ in path, title in h3 or .ashby-job-posting-brief-name
        for link in soup.find_all("a", href=re.compile(r"/jobs/")):
            title_el = link.find(["h3", "h2", "span"]) or link
            title = title_el.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("/"):
                href = base_domain + href
            if title and href:
                jobs.append(DiscoveredJobData(
                    company=company_name, title=title, url=href,
                    platform=platform, scan_source="playwright",
                ))

    elif platform == "greenhouse":
        # Greenhouse: .job-post elements with .job-post-header links
        for post in soup.find_all(class_=re.compile(r"job-post")):
            link = post.find("a")
            if link:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if href.startswith("/"):
                    href = base_domain + href
                if title and href:
                    jobs.append(DiscoveredJobData(
                        company=company_name, title=title, url=href,
                        platform=platform, scan_source="playwright",
                    ))

    elif platform == "lever":
        # Lever: .posting-title h5 elements
        for posting in soup.find_all(class_=re.compile(r"posting")):
            title_el = posting.find(["h5", "h4", "h3"])
            link = posting.find("a")
            if title_el and link:
                title = title_el.get_text(strip=True)
                href = link.get("href", "")
                if href.startswith("/"):
                    href = base_domain + href
                if title and href:
                    jobs.append(DiscoveredJobData(
                        company=company_name, title=title, url=href,
                        platform=platform, scan_source="playwright",
                    ))

    else:
        # Generic: find all links with "apply" or "/jobs/" in href
        for link in soup.find_all("a", href=re.compile(r"/(jobs?|careers?|apply)/")):
            title_el = link.find(["h3", "h2", "h4", "span"]) or link
            title = title_el.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("/"):
                href = base_domain + href
            if title and len(title) > 3 and href:
                jobs.append(DiscoveredJobData(
                    company=company_name, title=title, url=href,
                    platform=platform, scan_source="playwright",
                ))

    # Deduplicate by URL within this batch
    seen_urls = set()
    unique_jobs = []
    for j in jobs:
        if j.url not in seen_urls:
            seen_urls.add(j.url)
            unique_jobs.append(j)

    return unique_jobs


# ---------------------------------------------------------------------------
# JD text fetcher (called lazily when a user requests details)
# ---------------------------------------------------------------------------

async def fetch_jd_text(job_url: str) -> Optional[str]:
    """
    Fetch and extract the full job description text from a job URL.

    Strategy:
    1. Greenhouse API (for job-boards.greenhouse.io URLs) — most reliable
    2. httpx + BeautifulSoup for static HTML pages
    3. Playwright fallback for JS-heavy pages
    """
    # ── Strategy 1: Greenhouse API ─────────────────────────────────────────
    gh_match = re.search(
        r"(?:job-boards(?:\.eu)?\.greenhouse\.io|boards\.greenhouse\.io)/([^/]+)/jobs/(\d+)",
        job_url,
    )
    if gh_match:
        board_slug, job_id = gh_match.group(1), gh_match.group(2)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{board_slug}/jobs/{job_id}"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw_html = data.get("content", "")
                    if raw_html:
                        # Greenhouse returns entity-encoded HTML (&lt;div&gt;) — decode first
                        from html import unescape
                        decoded = unescape(raw_html)
                        soup = BeautifulSoup(decoded, "html.parser")
                        for tag in soup(["script", "style"]):
                            tag.decompose()
                        lines = [ln.strip() for ln in soup.get_text(separator="\n", strip=True).splitlines() if ln.strip()]
                        return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Greenhouse API JD fetch failed for {job_url}: {e}")

    # ── Strategy 2: httpx + BeautifulSoup ─────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(job_url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; UmukoziHR/2.5 job-scanner)"
            })
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["nav", "header", "footer", "script", "style", "button"]):
                    tag.decompose()
                jd_el = (
                    soup.find(class_=re.compile(r"job-description|posting-content|description|job-content", re.I))
                    or soup.find("main")
                    or soup.find("article")
                    or soup.body
                )
                if jd_el:
                    lines = [ln.strip() for ln in jd_el.get_text(separator="\n", strip=True).splitlines() if ln.strip()]
                    if len(lines) > 10:  # Enough content
                        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"httpx JD fetch failed for {job_url}: {e}")

    # ── Strategy 3: Playwright fallback ───────────────────────────────────
    try:
        from playwright.async_api import async_playwright
        import sys
        if sys.platform == "win32":
            import asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(job_url, wait_until="networkidle", timeout=30000)
            content = await page.content()
            await browser.close()

        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["nav", "header", "footer", "script", "style", "button"]):
            tag.decompose()
        jd_el = (
            soup.find(class_=re.compile(r"job-description|posting-content|description|job-content", re.I))
            or soup.find("main")
            or soup.find("article")
            or soup.body
        )
        if jd_el:
            lines = [ln.strip() for ln in jd_el.get_text(separator="\n", strip=True).splitlines() if ln.strip()]
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Playwright JD fetch failed for {job_url}: {e}")

    return None


# ---------------------------------------------------------------------------
# Main scanner entry point
# ---------------------------------------------------------------------------

async def scan_portals(
    portal_config: dict,
    existing_urls: set[str],
    dry_run: bool = False,
) -> tuple[list[DiscoveredJobData], ScanResult]:
    """
    Scan configured company career pages for new jobs.

    Args:
        portal_config: User's portal config dict (companies, filters).
        existing_urls: Set of job URLs already in the DB (for dedup).
        dry_run: If True, return sample data without actual HTTP calls.

    Returns:
        (new_jobs_list, scan_result_summary)
    """
    if dry_run:
        sample = [
            DiscoveredJobData("Anthropic", "Senior AI Engineer", "https://jobs.ashbyhq.com/anthropic/12345", "ashby", "dry_run"),
            DiscoveredJobData("OpenAI", "Research Engineer, AI Safety", "https://boards.greenhouse.io/openai/67890", "greenhouse", "dry_run"),
        ]
        return sample, ScanResult(new_jobs=len(sample), total_found=len(sample), skipped_duplicates=0)

    companies = portal_config.get("companies", [])
    positive_filters = portal_config.get("role_filters_positive", [])
    negative_filters = portal_config.get("role_filters_negative", [])

    result = ScanResult()
    all_found: list[DiscoveredJobData] = []

    for company in companies:
        if not company.get("enabled", True):
            continue

        platform = company.get("platform", "custom")

        # Strategy 1: Greenhouse API (fastest, most reliable)
        if platform == "greenhouse" and company.get("api_slug"):
            jobs = await _scan_greenhouse_api(company)
        # Strategy 2: Ashby API via __NEXT_DATA__ scraping (no auth needed)
        elif platform == "ashby":
            jobs = await _scan_ashby_api(company)
            # Fallback to Playwright if Ashby API found nothing
            if not jobs:
                jobs = await _scan_with_playwright(company)
        else:
            # Strategy 3: Playwright for Lever and custom pages
            jobs = await _scan_with_playwright(company)

        all_found.extend(jobs)
        await asyncio.sleep(0.5)  # Rate limiting between companies

    result.total_found = len(all_found)

    # Apply title filters and dedup
    new_jobs = []
    for job in all_found:
        if not _title_matches_filters(job.title, positive_filters, negative_filters):
            continue
        if job.url in existing_urls:
            result.skipped_duplicates += 1
            continue
        new_jobs.append(job)
        existing_urls.add(job.url)  # Prevent intra-batch duplicates

    result.new_jobs = len(new_jobs)
    logger.info(
        f"Scan complete: {result.total_found} found, {result.new_jobs} new, "
        f"{result.skipped_duplicates} duplicates"
    )

    return new_jobs, result
