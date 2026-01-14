# Improved Tailor pipeline: pre-filter -> LLM -> validate -> repair
# v1.3: Now passes FULL ProfileV3 to LLM for complete context
# v1.4: Added auto-region detection from job location

import re, json, logging
from collections import Counter
from .llm import build_user_prompt, call_llm, SYSTEM, OUTPUT_JSON_SCHEMA
from .validate import validate_or_error, business_rules_check
from app.models import Profile, JobJD, LLMOutput, ProfileV3

logger = logging.getLogger(__name__)

STOP = set("""a an the and or for to of in on at with from by as is are was were be been being will would should could into about over under within across""".split())

# Location patterns for auto-region detection
US_PATTERNS = [
    r'\b(usa|united states|u\.s\.?a?\.?|america)\b',
    r'\b(new york|nyc|san francisco|sf|los angeles|la|seattle|austin|boston|chicago|denver|atlanta|miami|dallas|houston|phoenix|philadelphia|washington\s*d\.?c\.?)\b',
    r'\b(california|texas|florida|washington|colorado|massachusetts|georgia|illinois|arizona|pennsylvania|virginia|north carolina|ohio|michigan|new jersey|oregon|nevada)\b',
    r'\b(silicon valley|bay area|wall street)\b',
]

EU_PATTERNS = [
    r'\b(europe|european union|eu\b|emea)\b',
    r'\b(london|berlin|paris|amsterdam|dublin|munich|frankfurt|zurich|stockholm|copenhagen|barcelona|madrid|milan|vienna|brussels|lisbon|prague|warsaw|oslo|helsinki)\b',
    r'\b(uk|united kingdom|britain|england|scotland|wales|ireland|germany|france|netherlands|switzerland|sweden|denmark|spain|italy|austria|belgium|portugal|poland|norway|finland|czech)\b',
]

def detect_region_from_jd(jd_text: str, company: str = "") -> str:
    """
    Auto-detect region (US/EU/GL) from job description text and company name.
    Returns 'US', 'EU', or 'GL' (Global/default).
    """
    text = f"{jd_text} {company}".lower()
    
    # Check US patterns
    for pattern in US_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.info(f"Auto-detected region: US (matched pattern: {pattern})")
            return "US"
    
    # Check EU patterns
    for pattern in EU_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.info(f"Auto-detected region: EU (matched pattern: {pattern})")
            return "EU"
    
    # Default to Global
    logger.info("Auto-detected region: GL (no specific region patterns found)")
    return "GL"

def norm_tokens(text:str):
    tokens = re.findall(r"[A-Za-z0-9\+\#\.]+", text.lower())
    return [t for t in tokens if t not in STOP and len(t)>1]

def score_bullet(bullet:str, jd_counts:Counter):
    toks = norm_tokens(bullet)
    return sum(jd_counts.get(t,0) for t in toks)

def select_topk_bullets(profile: Profile, jd_text: str, k:int=12):
    jd_counts = Counter(norm_tokens(jd_text))
    pool = []
    for row in profile.experience:
        for bullet in row.bullets:
            pool.append({
                "role_title": row.title,
                "company": row.company,
                "bullet": bullet,
                "score": score_bullet(bullet, jd_counts)
            })
    pool.sort(key=lambda x: x["score"], reverse=True)
    return [{"role_title":p["role_title"], "company":p["company"], "bullet":p["bullet"]} for p in pool[:k]]

def region_rules(region:str)->dict:
    if region=="US": return {"pages":1,"style":"no photo; concise; one-page","date_format":"YYYY-MM"}
    if region=="EU": return {"pages":2,"style":"two-page allowed; simple","date_format":"YYYY-MM"}
    if region=="GL": return {"pages":1,"style":"one-page allowed; simple","date_format":"YYYY-MM"}    
    return {"pages":2,"style":"no photo; refs on request ok","date_format":"YYYY-MM"}

def run_tailor(profile: Profile, job: JobJD, full_profile_v3: ProfileV3 = None) -> LLMOutput:
    """
    Run the tailoring pipeline.
    
    Args:
        profile: Legacy Profile object (used for bullet selection and backward compatibility)
        job: Job description object
        full_profile_v3: Optional full ProfileV3 with certifications, awards, languages, etc.
                        When provided, this complete data is sent to LLM for better tailoring.
    """
    logger.info(f"=== TAILOR START === Job: {job.id or job.title}, Company: {job.company}, Region: {job.region}")
    logger.info(f"Full ProfileV3 provided: {full_profile_v3 is not None}")

    try:
        logger.info(f"Selecting top bullets from profile (name: {profile.name})")
        selected = select_topk_bullets(profile, job.jd_text)
        logger.info(f"Selected {len(selected)} top bullets from {len(profile.experience)} experience entries")
        logger.debug(f"Top 3 selected bullets: {selected[:3]}")

        logger.info(f"Determining region rules for: {job.region}")
        reg_rules = region_rules(job.region)
        logger.info(f"Region rules: {reg_rules}")

        logger.info(f"Building LLM prompt for job: {job.id or job.title}")
        
        # Use full ProfileV3 if available, otherwise fall back to legacy Profile
        if full_profile_v3:
            full_profile_json = full_profile_v3.model_dump_json()
            # Log all profile sections for debugging
            volunteering_count = len(full_profile_v3.volunteering) if hasattr(full_profile_v3, 'volunteering') else 0
            publications_count = len(full_profile_v3.publications) if hasattr(full_profile_v3, 'publications') else 0
            courses_count = len(full_profile_v3.courses) if hasattr(full_profile_v3, 'courses') else 0
            has_linkedin_meta = bool(full_profile_v3.linkedin_meta) if hasattr(full_profile_v3, 'linkedin_meta') else False
            
            logger.info(f"Using FULL ProfileV3: "
                        f"{len(full_profile_v3.experience)} experiences, "
                        f"{len(full_profile_v3.education)} education, "
                        f"{len(full_profile_v3.skills)} skills, "
                        f"{len(full_profile_v3.certifications)} certifications, "
                        f"{len(full_profile_v3.awards)} awards, "
                        f"{len(full_profile_v3.languages)} languages, "
                        f"{volunteering_count} volunteering, "
                        f"{publications_count} publications, "
                        f"{courses_count} courses, "
                        f"linkedin_meta: {has_linkedin_meta}")
        else:
            full_profile_json = profile.model_dump_json()
            logger.info("Using legacy Profile (no ProfileV3 available)")
        
        prompt = build_user_prompt(
            full_profile_json=full_profile_json,
            jd_text=job.jd_text,
            region_rules=reg_rules,
            selected_bullets_json=json.dumps(selected, ensure_ascii=False),
            schema_json=json.dumps(OUTPUT_JSON_SCHEMA.to_json_dict(), ensure_ascii=False),
        )
        logger.info(f"LLM prompt built - length: {len(prompt)} chars, JD length: {len(job.jd_text)} chars")

        logger.info(f"Calling LLM for job: {job.id or job.title}")
        raw = call_llm(prompt)
        logger.info(f"LLM response received - length: {len(raw)} chars")
        logger.debug(f"Raw LLM response (first 500 chars): {raw[:500]}")

        # call validator to check the schema
        logger.info(f"Validating LLM output schema for job: {job.id or job.title}")
        try:
            data = validate_or_error(raw)
            logger.info("LLM output passed schema validation successfully")
        except Exception as validation_error:
            logger.error(f"=== SCHEMA VALIDATION FAILED === Job: {job.id or job.title}")
            logger.error(f"Validation error: {validation_error}")
            logger.error(f"Full raw LLM response that failed validation (length: {len(raw)}): {raw}")
            raise

        # check to make sure it is grounded with facts
        logger.info(f"Performing business rules validation for job: {job.id or job.title}")
        try:
            business_rules_check(data, profile)
            logger.info("LLM output passed business rules validation successfully")
        except Exception as business_error:
            logger.error(f"=== BUSINESS RULES VALIDATION FAILED === Job: {job.id or job.title}")
            logger.error(f"Business rules error: {business_error}")
            logger.error(f"Data that failed business rules: {json.dumps(data, indent=2)}")
            raise

        logger.info(f"=== TAILOR SUCCESS === Job: {job.id or job.title}, Resume bullets: {len(data.get('resume', {}).get('experience', []))}, Cover letter paragraphs: {len(data.get('cover_letter', {}).get('body_paragraphs', []))}")
        return LLMOutput(**data)
    except Exception as e:
        logger.error(f"=== TAILOR ERROR === Job: {job.id or job.title}, Error: {str(e)}", exc_info=True)
        raise
