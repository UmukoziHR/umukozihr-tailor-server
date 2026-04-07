"""
Job Application Form Analyzer — UmukoziHR Tailor v2.5
Analyzes application forms for Ashby, Greenhouse, and Lever.
Returns pre-filled field data for human review. NEVER auto-submits.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field mapping: common form label patterns → profile field paths
# ---------------------------------------------------------------------------

FIELD_LABEL_MAP = [
    # Name fields
    (re.compile(r"first\s*name", re.I), "basics.first_name", "text"),
    (re.compile(r"last\s*name|surname|family\s*name", re.I), "basics.last_name", "text"),
    (re.compile(r"^full\s*name|your\s*name", re.I), "basics.full_name", "text"),
    # Contact
    (re.compile(r"email|e-mail", re.I), "basics.email", "email"),
    (re.compile(r"phone|mobile|telephone", re.I), "basics.phone", "text"),
    # Location
    (re.compile(r"city|location|where\s*are\s*you", re.I), "basics.location", "text"),
    # Links
    (re.compile(r"linkedin", re.I), "basics.linkedin_url", "url"),
    (re.compile(r"github", re.I), "basics.github_url", "url"),
    (re.compile(r"portfolio|website|personal\s*site", re.I), "basics.portfolio_url", "url"),
    # Resume upload
    (re.compile(r"resume|cv\b|curriculum", re.I), "resume_pdf_path", "file"),
    # Cover letter
    (re.compile(r"cover\s*letter", re.I), "cover_letter_text", "textarea"),
    # Application questions (matched to draft answers if score >= 4.5)
    (re.compile(r"why.*interested|why.*role|what.*attracts|why.*applying", re.I), "application_draft.why_role", "textarea"),
    (re.compile(r"why.*company|why.*us\b|why.*join", re.I), "application_draft.why_company", "textarea"),
    (re.compile(r"relevant.*project|relevant.*experience|tell us about", re.I), "application_draft.relevant_experience", "textarea"),
    (re.compile(r"good\s*fit|why\s*you|qualif", re.I), "application_draft.good_fit", "textarea"),
    # Salary
    (re.compile(r"salary|compensation|desired.*pay|expected.*pay", re.I), "basics.salary_expectation", "text"),
    # Work authorization
    (re.compile(r"work.*authorization|authorized.*work|right.*work|visa|sponsorship", re.I), "basics.work_authorization", "text"),
    # How did you hear
    (re.compile(r"how.*hear|referral|source", re.I), "source_answer", "text"),
]

SOURCE_ANSWER = "Found through UmukoziHR Tailor job pipeline — evaluated against my criteria and it scored as a strong match."


@dataclass
class FilledField:
    field_name: str
    field_type: str  # text, textarea, email, url, file, select, checkbox
    value: str
    confidence: str  # high, medium, low
    profile_path: str  # which profile field this came from


@dataclass
class FormFillResult:
    filled_fields: list = field(default_factory=list)
    unfilled_fields: list = field(default_factory=list)
    platform_detected: str = "unknown"
    notes: str = ""
    error: Optional[str] = None


def _get_profile_value(profile_data: dict, path: str, evaluation_data: Optional[dict] = None) -> Optional[str]:
    """Extract a value from nested profile data using dot-notation path."""
    if path == "source_answer":
        return SOURCE_ANSWER

    if path.startswith("application_draft.") and evaluation_data:
        key = path.split(".", 1)[1]
        draft = evaluation_data.get("application_draft") or {}
        return draft.get(key)

    if path == "basics.full_name":
        basics = profile_data.get("basics", {})
        first = basics.get("first_name") or basics.get("name", "").split()[0] if basics.get("name") else ""
        last = basics.get("last_name") or (" ".join(basics.get("name", "").split()[1:]) if basics.get("name") else "")
        if first or last:
            return f"{first} {last}".strip()
        return basics.get("name") or basics.get("full_name")

    if path == "basics.first_name":
        basics = profile_data.get("basics", {})
        name = basics.get("name") or basics.get("full_name") or ""
        return basics.get("first_name") or (name.split()[0] if name else None)

    if path == "basics.last_name":
        basics = profile_data.get("basics", {})
        name = basics.get("name") or basics.get("full_name") or ""
        return basics.get("last_name") or (" ".join(name.split()[1:]) if name else None)

    parts = path.split(".")
    obj = profile_data
    for part in parts:
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return str(obj) if obj else None


def _detect_platform(form_url: str) -> str:
    if "ashbyhq.com" in form_url or "ashby.io" in form_url:
        return "ashby"
    if "greenhouse.io" in form_url or "greenhouse.com" in form_url:
        return "greenhouse"
    if "lever.co" in form_url:
        return "lever"
    return "custom"


async def analyze_application_form(
    form_url: str,
    profile_data: dict,
    evaluation_data: Optional[dict] = None,
    cover_letter_text: Optional[str] = None,
    resume_pdf_path: Optional[str] = None,
) -> FormFillResult:
    """
    Analyze an application form and return pre-filled field data.

    This function uses Playwright to read the form structure, identifies fields
    by label text, and maps them to profile data. It does NOT fill or submit the form.

    Args:
        form_url: URL of the application form.
        profile_data: User's ProfileV3 data.
        evaluation_data: JobEvaluation data (for application draft answers).
        cover_letter_text: Generated cover letter text.
        resume_pdf_path: Path to the generated resume PDF.

    Returns:
        FormFillResult with pre-analyzed field data for human review.
    """
    result = FormFillResult(platform_detected=_detect_platform(form_url))

    # Extend profile_data with generated content for field lookup
    extended_profile = dict(profile_data)
    if cover_letter_text:
        extended_profile["cover_letter_text"] = cover_letter_text
    if resume_pdf_path:
        extended_profile["resume_pdf_path"] = resume_pdf_path

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(form_url, wait_until="networkidle", timeout=30000)

            # Extract all form labels and their associated input elements
            form_elements = await page.evaluate("""() => {
                const fields = [];
                const inputs = document.querySelectorAll('input, textarea, select');
                inputs.forEach(input => {
                    let label = '';
                    // Try aria-label
                    if (input.getAttribute('aria-label')) {
                        label = input.getAttribute('aria-label');
                    }
                    // Try associated label element
                    else if (input.id) {
                        const labelEl = document.querySelector(`label[for="${input.id}"]`);
                        if (labelEl) label = labelEl.innerText.trim();
                    }
                    // Try parent label
                    else {
                        const parentLabel = input.closest('label');
                        if (parentLabel) label = parentLabel.innerText.trim();
                    }
                    // Try placeholder as fallback
                    if (!label && input.placeholder) label = input.placeholder;

                    fields.push({
                        label: label,
                        type: input.tagName.toLowerCase() === 'textarea' ? 'textarea'
                              : input.tagName.toLowerCase() === 'select' ? 'select'
                              : (input.type || 'text'),
                        name: input.name || input.id || '',
                        required: input.required || false
                    });
                });
                return fields;
            }""")

            await browser.close()

        # Map form fields to profile values
        for fe in form_elements:
            label = fe.get("label", "").strip()
            field_type = fe.get("type", "text")
            field_name = fe.get("name", label)

            if not label or field_type in ("hidden", "submit", "button", "reset"):
                continue

            matched = False
            for pattern, profile_path, suggested_type in FIELD_LABEL_MAP:
                if pattern.search(label):
                    value = _get_profile_value(extended_profile, profile_path, evaluation_data)
                    if value:
                        # File fields: just note the file path, don't actually upload
                        if profile_path == "resume_pdf_path":
                            confidence = "high"
                            value = f"[FILE: {value}] — upload manually"
                        elif profile_path.startswith("application_draft."):
                            confidence = "high" if evaluation_data else "low"
                        else:
                            confidence = "high"

                        result.filled_fields.append(FilledField(
                            field_name=label or field_name,
                            field_type=suggested_type,
                            value=value,
                            confidence=confidence,
                            profile_path=profile_path,
                        ))
                        matched = True
                        break

            if not matched and label:
                result.unfilled_fields.append(label)

        # Add notes
        if result.unfilled_fields:
            result.notes = f"Could not auto-fill {len(result.unfilled_fields)} field(s): {', '.join(result.unfilled_fields[:5])}"

        notes_parts = [
            f"Platform detected: {result.platform_detected}",
            f"Pre-filled {len(result.filled_fields)} fields",
        ]
        if result.unfilled_fields:
            notes_parts.append(f"Needs manual input: {', '.join(result.unfilled_fields[:3])}")
        result.notes = ". ".join(notes_parts) + ". Review all fields before submitting."

    except ImportError:
        result.notes = "Playwright not installed — form analysis unavailable."
        result.error = "playwright_not_installed"
        # Still try to fill from known profile data without form scraping
        _fill_common_fields_without_scraping(result, extended_profile, evaluation_data)

    except Exception as e:
        logger.error(f"Form analysis failed for {form_url}: {e}", exc_info=True)
        result.error = str(e)
        _fill_common_fields_without_scraping(result, extended_profile, evaluation_data)

    return result


def _fill_common_fields_without_scraping(
    result: FormFillResult,
    profile_data: dict,
    evaluation_data: Optional[dict],
) -> None:
    """Fallback: fill common fields from profile without scraping the form."""
    common_fields = [
        ("First Name", "basics.first_name", "text"),
        ("Last Name", "basics.last_name", "text"),
        ("Email", "basics.email", "email"),
        ("Phone", "basics.phone", "text"),
        ("LinkedIn URL", "basics.linkedin_url", "url"),
        ("Portfolio / Website", "basics.portfolio_url", "url"),
        ("Resume", "resume_pdf_path", "file"),
        ("Cover Letter", "cover_letter_text", "textarea"),
        ("Why this role?", "application_draft.why_role", "textarea"),
        ("Why this company?", "application_draft.why_company", "textarea"),
        ("How did you hear about us?", "source_answer", "text"),
    ]
    for label, path, ftype in common_fields:
        value = _get_profile_value(profile_data, path, evaluation_data)
        if value:
            result.filled_fields.append(FilledField(
                field_name=label,
                field_type=ftype,
                value=value,
                confidence="medium",
                profile_path=path,
            ))
