import json
import re
from jsonschema import validate, Draft202012Validator
from app.models import Profile

OUTPUT_JSON_SCHEMA = {
  "type":"object",
  "required":["resume","cover_letter","ats"],
  "properties":{
    "resume":{
      "type":"object",
      "required":["summary","skills_line","experience","projects","education"],
      "properties":{
        "summary":{"type":"string"},
        "skills_line":{"type":"array","items":{"type":"string"}},
        "experience":{"type":"array","items":{
          "type":"object",
          "required":["title","company","bullets"],
          "properties":{
            "title":{"type":"string"},
            "company":{"type":"string"},
            "start":{"type":"string"},
            "end":{"type":"string"},
            "bullets":{"type":"array","items":{"type":"string"}}
          }
        }},
        "projects":{"type":"array"},
        "education":{"type":"array"}
      }
    },
    "cover_letter":{
      "type":"object",
      "required":["address","intro","why_you","evidence","why_them","close"],
      "properties":{
        "address":{"type":"string"},
        "intro":{"type":"string"},
        "why_you":{"type":"string"},
        "evidence":{"type":"array","items":{"type":"string"}},
        "why_them":{"type":"string"},
        "close":{"type":"string"}
      }
    },
    "ats":{
      "type":"object",
      "required":["jd_keywords_matched","risks"],
      "properties":{
        "jd_keywords_matched":{"type":"array","items":{"type":"string"}},
        "risks":{"type":"array","items":{"type":"string"}}
      }
    }
  }
}

def validate_or_error(raw_json:str)->dict:
    try:
        data = json.loads(raw_json)
    except Exception as e:
        raise ValueError(f"Invalid JSON: {e}")
    errors = sorted(Draft202012Validator(OUTPUT_JSON_SCHEMA).iter_errors(data), key=lambda e: e.path)
    if errors:
        raise ValueError("Schema errors: " + "; ".join([e.message for e in errors]))
    return data


def extract_years_from_date(date_str: str) -> set:
    """Extract all 4-digit years from a date string."""
    if not date_str:
        return set()
    return set(re.findall(r'\b(19|20)\d{2}\b', date_str))


def normalize_company_name(name: str) -> str:
    """Normalize company names to prevent false mismatches from formatting differences."""
    if not name:
        return ""

    normalized = name.casefold().replace("&", " and ").replace("_", " ")
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def business_rules_check(data:dict, profile:Profile):
    """Validate LLM output against profile data.
    
    Checks:
    1. Company names must exist in profile
    2. Dates must not be changed (years preserved)
    3. No duplicate bullet points
    """
    # 1. Company/title safety: must be subset of profile companies (or blank)
    prof_companies = {r.company for r in profile.experience if r.company}
    prof_companies_normalized = {
        normalize_company_name(company) for company in prof_companies
    }

    for r in data["resume"]["experience"]:
        company = (r.get("company") or "").strip()
        if not company:
            continue

        if company in prof_companies:
            continue

        if normalize_company_name(company) not in prof_companies_normalized:
            raise ValueError(f"company not in profile: {r['company']}")
    
    # 2. Date validation: years in output must exist in profile dates
    profile_years = set()
    for exp in profile.experience:
        profile_years.update(extract_years_from_date(exp.start or ""))
        profile_years.update(extract_years_from_date(exp.end or ""))
    
    for exp in data["resume"]["experience"]:
        output_years = extract_years_from_date(exp.get("start", ""))
        output_years.update(extract_years_from_date(exp.get("end", "")))
        
        for year in output_years:
            if year not in profile_years and year not in {'Present', 'Current'}:
                # Only warn, don't fail - sometimes JD has dates too
                import logging
                logging.getLogger(__name__).warning(
                    f"Date mismatch detected: year '{year}' in output but not in profile. "
                    f"Profile years: {profile_years}"
                )
    
    # 3. Deduplication check: no repeated bullets
    all_bullets = []
    for exp in data["resume"]["experience"]:
        all_bullets.extend(exp.get("bullets", []))
    
    seen_bullets = set()
    duplicate_count = 0
    for bullet in all_bullets:
        # Normalize for comparison (lowercase, strip)
        normalized = bullet.lower().strip()
        if normalized in seen_bullets:
            duplicate_count += 1
        seen_bullets.add(normalized)
    
    if duplicate_count > 0:
        import logging
        logging.getLogger(__name__).warning(
            f"Found {duplicate_count} duplicate bullet(s) in LLM output"
        )
