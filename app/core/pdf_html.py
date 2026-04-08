"""
HTML PDF Generation Service — UmukoziHR Tailor v2.5
Generates ATS-optimized PDFs using the CareerOps modern HTML template
rendered via Python Playwright Chromium. Alternative to LaTeX.
"""
import html
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Path to the modern CV template
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "cv_template_modern.html"
# Path to fonts used by the template
FONTS_DIR = Path(__file__).parent.parent / "static" / "fonts"


# ---------------------------------------------------------------------------
# ATS normalization (ported from CareerOps generate-pdf.mjs)
# ---------------------------------------------------------------------------

_ATS_REPLACEMENTS = [
    ("\u2014", "-"),   # em dash → hyphen
    ("\u2013", "-"),   # en dash → hyphen
    ("\u201c", '"'),   # left double quote
    ("\u201d", '"'),   # right double quote
    ("\u2018", "'"),   # left single quote
    ("\u2019", "'"),   # right single quote
    ("\u2026", "..."), # ellipsis
    ("\u200b", ""),    # zero-width space
    ("\u200c", ""),    # zero-width non-joiner
    ("\u200d", ""),    # zero-width joiner
    ("\u00a0", " "),   # non-breaking space
]


def _normalize_for_ats(text: str) -> str:
    """Replace Unicode typography characters with ATS-safe equivalents."""
    for char, replacement in _ATS_REPLACEMENTS:
        text = text.replace(char, replacement)
    return text


def _esc(text: str) -> str:
    """HTML-escape text and normalize for ATS."""
    return html.escape(_normalize_for_ats(str(text or "")))


# ---------------------------------------------------------------------------
# HTML renderers for each section
# ---------------------------------------------------------------------------

def _render_competency_tags(skills_line: list) -> str:
    """Render skills as competency tags."""
    if not skills_line:
        return ""
    tags = []
    for skill in skills_line[:20]:  # cap at 20 for layout
        tags.append(f'<span class="competency-tag">{_esc(skill)}</span>')
    return "\n".join(tags)


def _render_experience_html(experience: list) -> str:
    """Render work experience entries."""
    parts = []
    for job in experience or []:
        title = _esc(job.get("title") or job.get("role") or "")
        company = _esc(job.get("company") or "")
        start = _esc(job.get("start") or "")
        end = _esc(job.get("end") or "Present")
        period = f"{start} – {end}" if start else end
        location = _esc(job.get("location") or "")
        bullets = job.get("bullets") or job.get("highlights") or []

        bullet_html = ""
        if bullets:
            items = "".join(f"<li>{_esc(b)}</li>" for b in bullets)
            bullet_html = f"<ul>{items}</ul>"

        location_html = f'<div class="job-location">{location}</div>' if location else ""

        parts.append(f"""<div class="job avoid-break">
  <div class="job-header">
    <span class="job-company">{company}</span>
    <span class="job-period">{period}</span>
  </div>
  <div class="job-role">{title}</div>
  {location_html}
  {bullet_html}
</div>""")
    return "\n".join(parts)


def _render_projects_html(projects: list) -> str:
    """Render project entries."""
    parts = []
    for p in projects or []:
        name = _esc(p.get("name") or "")
        stack = _esc(p.get("stack") or p.get("tech") or "")
        bullets = p.get("bullets") or p.get("highlights") or []

        stack_html = f'<div class="project-tech">{stack}</div>' if stack else ""
        bullet_html = ""
        if bullets:
            desc = " ".join(_normalize_for_ats(str(b)) for b in bullets[:2])
            bullet_html = f'<div class="project-desc">{_esc(desc)}</div>'

        parts.append(f"""<div class="project avoid-break">
  <span class="project-title">{name}</span>
  {stack_html}
  {bullet_html}
</div>""")
    return "\n".join(parts)


def _render_education_html(education: list) -> str:
    """Render education entries."""
    parts = []
    for edu in education or []:
        school = _esc(edu.get("school") or edu.get("institution") or "")
        degree = _esc(edu.get("degree") or "")
        period = _esc(edu.get("period") or edu.get("year") or "")
        desc = _esc(edu.get("description") or "")

        desc_html = f'<div class="edu-desc">{desc}</div>' if desc else ""
        parts.append(f"""<div class="edu-item avoid-break">
  <div class="edu-header">
    <span class="edu-title">{degree} — <span class="edu-org">{school}</span></span>
    <span class="edu-year">{period}</span>
  </div>
  {desc_html}
</div>""")
    return "\n".join(parts)


def _render_certifications_html(certifications: list) -> str:
    """Render certification entries."""
    parts = []
    for cert in certifications or []:
        name = _esc(cert.get("name") or "")
        issuer = _esc(cert.get("issuer") or cert.get("by") or "")
        date = _esc(cert.get("date") or cert.get("year") or "")

        parts.append(f"""<div class="cert-item">
  <span class="cert-title">{name} — <span class="cert-org">{issuer}</span></span>
  <span class="cert-year">{date}</span>
</div>""")
    return "\n".join(parts)


def _render_skills_html(skills_data) -> str:
    """Render skills section — handles both list-of-strings and categorized dict."""
    if not skills_data:
        return ""

    if isinstance(skills_data, list):
        # Flat list: render as tags
        items = "".join(f'<span class="skill-item">{_esc(s)}</span>' for s in skills_data)
        return f'<div class="skills-grid">{items}</div>'

    if isinstance(skills_data, dict):
        # Categorized: {category: [skills]}
        parts = []
        for category, items in skills_data.items():
            if isinstance(items, list):
                items_str = ", ".join(_esc(str(s)) for s in items)
            else:
                items_str = _esc(str(items))
            parts.append(
                f'<div><span class="skill-category">{_esc(category)}:</span> '
                f'<span class="skill-item">{items_str}</span></div>'
            )
        return "\n".join(parts)

    return ""


def _extract_domain(url: str) -> str:
    """Extract display domain from URL."""
    if not url:
        return ""
    match = re.search(r"(?:https?://)?(?:www\.)?([^/]+)", url)
    return match.group(1) if match else url


def _extract_linkedin_handle(url: str) -> str:
    """Extract LinkedIn handle from URL."""
    if not url:
        return ""
    match = re.search(r"linkedin\.com/in/([^/\s]+)", url)
    return f"linkedin.com/in/{match.group(1)}" if match else _extract_domain(url)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _build_template_vars(llm_output: dict, profile: dict, region: str) -> dict:
    """Map ProfileV3 + LLM output to template placeholder variables."""
    basics = profile.get("basics") or {}
    resume = llm_output.get("resume") or {}

    full_name = basics.get("name") or basics.get("full_name") or ""
    email = basics.get("email") or ""
    phone = basics.get("phone") or ""
    location = basics.get("location") or basics.get("city") or ""
    linkedin_url = basics.get("linkedin_url") or basics.get("linkedin") or ""
    portfolio_url = basics.get("portfolio_url") or basics.get("website") or ""

    # Build contact row — only include non-empty fields
    contact_parts = [f"<span>{_esc(email)}</span>"] if email else []
    if phone:
        contact_parts.append(f'<span class="separator">|</span><span>{_esc(phone)}</span>')
    if linkedin_url:
        contact_parts.append(
            f'<span class="separator">|</span>'
            f'<a href="{_esc(linkedin_url)}">{_esc(_extract_linkedin_handle(linkedin_url))}</a>'
        )
    if portfolio_url:
        contact_parts.append(
            f'<span class="separator">|</span>'
            f'<a href="{_esc(portfolio_url)}">{_esc(_extract_domain(portfolio_url))}</a>'
        )
    if location:
        contact_parts.append(f'<span class="separator">|</span><span>{_esc(location)}</span>')

    contact_row_html = "\n".join(contact_parts)

    page_width = "8.5in" if region == "us" else "210mm"
    page_format = "Letter" if region == "us" else "A4"
    lang = "en"

    return {
        "{{LANG}}": lang,
        "{{PAGE_WIDTH}}": page_width,
        "{{PAGE_FORMAT}}": page_format,
        "{{NAME}}": _esc(full_name),
        "{{EMAIL}}": _esc(email),
        "{{LINKEDIN_URL}}": _esc(linkedin_url),
        "{{LINKEDIN_DISPLAY}}": _esc(_extract_linkedin_handle(linkedin_url)),
        "{{PORTFOLIO_URL}}": _esc(portfolio_url),
        "{{PORTFOLIO_DISPLAY}}": _esc(_extract_domain(portfolio_url)),
        "{{LOCATION}}": _esc(location),
        "{{CONTACT_ROW}}": contact_row_html,
        "{{SECTION_SUMMARY}}": "Professional Summary",
        "{{SUMMARY_TEXT}}": _esc(resume.get("summary") or ""),
        "{{SECTION_COMPETENCIES}}": "Core Competencies",
        "{{COMPETENCIES}}": _render_competency_tags(resume.get("skills_line") or []),
        "{{SECTION_EXPERIENCE}}": "Work Experience",
        "{{EXPERIENCE}}": _render_experience_html(resume.get("experience") or []),
        "{{SECTION_PROJECTS}}": "Projects",
        "{{PROJECTS}}": _render_projects_html(resume.get("projects") or []),
        "{{SECTION_EDUCATION}}": "Education",
        "{{EDUCATION}}": _render_education_html(resume.get("education") or []),
        "{{SECTION_CERTIFICATIONS}}": "Certifications",
        "{{CERTIFICATIONS}}": _render_certifications_html(resume.get("certifications") or []),
        "{{SECTION_SKILLS}}": "Skills",
        "{{SKILLS}}": _render_skills_html(resume.get("skills_line") or []),
    }


def _render_template(template_html: str, vars_map: dict) -> str:
    """Replace all template placeholders with rendered content."""
    result = template_html
    for placeholder, value in vars_map.items():
        result = result.replace(placeholder, value)

    # Replace font paths to use absolute file:// paths
    fonts_abs = FONTS_DIR.as_posix()
    result = result.replace("./fonts/", f"file:///{fonts_abs}/")
    result = result.replace("../fonts/", f"file:///{fonts_abs}/")

    return result


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

async def generate_modern_pdf(
    llm_output: dict,
    profile: dict,
    artifacts_dir: str,
    run_id: str,
    region: str = "us",
) -> Optional[str]:
    """
    Generate an ATS-optimized PDF using the modern HTML template.

    Args:
        llm_output: Tailored resume data from the LLM (same structure as LaTeX pipeline).
        profile: User's ProfileV3 data dict.
        artifacts_dir: Directory to save the PDF in.
        run_id: Run ID for file naming.
        region: 'us' (Letter format) or 'eu'/'gl' (A4 format).

    Returns:
        Absolute path to the generated PDF, or None on failure.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("playwright package not installed — cannot generate modern PDF")
        return None

    if not TEMPLATE_PATH.exists():
        logger.error(f"Modern CV template not found at {TEMPLATE_PATH}")
        return None

    try:
        template_html = TEMPLATE_PATH.read_text(encoding="utf-8")
        vars_map = _build_template_vars(llm_output, profile, region)
        rendered_html = _render_template(template_html, vars_map)

        # Write rendered HTML to a temp file
        output_dir = Path(artifacts_dir) / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        html_path = output_dir / "resume_modern.html"
        html_path.write_text(rendered_html, encoding="utf-8")

        pdf_path = output_dir / "resume_modern.pdf"

        page_format = vars_map.get("{{PAGE_FORMAT}}", "Letter")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Load from file:// URL so fonts resolve correctly
            await page.goto(f"file:///{html_path.as_posix()}", wait_until="networkidle")
            # Wait for fonts to load
            await page.evaluate("document.fonts.ready")

            await page.pdf(
                path=str(pdf_path),
                format=page_format,
                margin={"top": "0.6in", "bottom": "0.6in", "left": "0.6in", "right": "0.6in"},
                print_background=True,
            )
            await browser.close()

        logger.info(f"Modern PDF generated: {pdf_path} ({pdf_path.stat().st_size // 1024}KB)")
        return str(pdf_path)

    except Exception as e:
        logger.error(f"Modern PDF generation failed: {e}", exc_info=True)
        return None
