import os
import json
import logging
from dotenv import load_dotenv
from google import genai
from google.genai.types import Tool, Schema, GenerateContentConfig

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)


SYSTEM = (
    "You are an expert ATS resume & cover-letter tailor with 20+ years of experience. "
    "Return ONLY valid JSON matching the provided schema. "
    "RULES: "
    "1) NEVER invent companies, schools, dates, or achievements - use ONLY what exists in the profile. "
    "2) DATES ARE SACRED: Copy start/end dates EXACTLY as provided in the profile - NEVER change years (e.g., if profile says 2025, output 2025 NOT 2024). "
    "3) Use exact JD keywords ONLY when they truthfully match the candidate's experience. "
    "4) Respect region style rules (US=1 page, EU=2 pages allowed, GL=1 page). "
    "5) Write concise, metric-first quantitative bullets following <action verb → measurable result>. "
    "6) NEVER repeat the same bullet point or achievement - each bullet must be unique. "
    "7) Include relevant certifications, awards, and languages when they match the JD requirements. "
    "8) For cover letter, reference specific company values/projects from the JD. "
    "9) Tailor the summary to directly address the job's key requirements."
)

# Strict JSON Schema for gemini to avoid hallucinations and stick to our convention
# Updated to include certifications, awards, and languages for full profile context
OUTPUT_JSON_SCHEMA = Schema(
    type="OBJECT",
    required=["resume","cover_letter","ats"],
    properties={
        "resume": Schema(type="OBJECT", required=["summary","skills_line","experience","projects","education"], properties={
            "summary": Schema(type="STRING"),
            "skills_line": Schema(type="ARRAY", items=Schema(type="STRING")),
            "experience": Schema(type="ARRAY", items=Schema(type="OBJECT", required=["title","company","bullets"], properties={
                "title": Schema(type="STRING"),
                "company": Schema(type="STRING"),
                "start": Schema(type="STRING"),
                "end": Schema(type="STRING"),
                "bullets": Schema(type="ARRAY", items=Schema(type="STRING")),
            })),
            "projects": Schema(type="ARRAY", items=Schema(type="OBJECT", properties={
                "name": Schema(type="STRING"),
                "stack": Schema(type="ARRAY", items=Schema(type="STRING")),
                "bullets": Schema(type="ARRAY", items=Schema(type="STRING")),
            })),
            "education": Schema(type="ARRAY", items=Schema(type="OBJECT", properties={
                "school": Schema(type="STRING"),
                "degree": Schema(type="STRING"),
                "period": Schema(type="STRING"),
            })),
            # New fields for full profile data
            "certifications": Schema(type="ARRAY", items=Schema(type="OBJECT", properties={
                "name": Schema(type="STRING"),
                "issuer": Schema(type="STRING"),
                "date": Schema(type="STRING"),
            })),
            "awards": Schema(type="ARRAY", items=Schema(type="OBJECT", properties={
                "name": Schema(type="STRING"),
                "by": Schema(type="STRING"),
                "date": Schema(type="STRING"),
            })),
            "languages": Schema(type="ARRAY", items=Schema(type="OBJECT", properties={
                "name": Schema(type="STRING"),
                "level": Schema(type="STRING"),
            })),
        }),
        "cover_letter": Schema(type="OBJECT", required=["address","intro","why_you","evidence","why_them","close"], properties={
            "address": Schema(type="STRING"),
            "intro": Schema(type="STRING"),
            "why_you": Schema(type="STRING"),
            "evidence": Schema(type="ARRAY", items=Schema(type="STRING")),
            "why_them": Schema(type="STRING"),
            "close": Schema(type="STRING"),
        }),
        "ats": Schema(type="OBJECT", required=["jd_keywords_matched","risks"], properties={
            "jd_keywords_matched": Schema(type="ARRAY", items=Schema(type="STRING")),
            "risks": Schema(type="ARRAY", items=Schema(type="STRING")),
        })
    },
)


def build_user_prompt(
    full_profile_json: str,
    jd_text: str,
    region_rules: dict,
    selected_bullets_json: str,
    schema_json: str,
    profile_min_json: str = None  # Kept for backward compatibility
) -> str:
    """
    Build the LLM prompt with FULL profile context.
    
    Args:
        full_profile_json: Complete ProfileV3 JSON with all fields (certifications, awards, languages, etc.)
        jd_text: The job description text
        region_rules: Regional formatting rules (US/EU/GL)
        selected_bullets_json: Pre-filtered top bullets for relevance
        schema_json: Output schema for structured response
        profile_min_json: Legacy parameter (ignored if full_profile_json provided)
    """
    # Use full profile if provided, otherwise fall back to legacy
    profile_data = full_profile_json if full_profile_json else profile_min_json
    
    return (
        f"=== CANDIDATE FULL PROFILE (use ALL relevant data) ===\n"
        f"{profile_data}\n\n"
        f"=== JOB DESCRIPTION ===\n"
        f"{jd_text}\n\n"
        f"=== REGION FORMATTING RULES ===\n"
        f"{json.dumps(region_rules, ensure_ascii=False)}\n\n"
        f"=== PRE-SELECTED TOP BULLETS (prioritize these for experience section) ===\n"
        f"{selected_bullets_json}\n\n"
        f"=== OUTPUT SCHEMA (follow exactly) ===\n"
        f"{schema_json}\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Analyze the JD carefully for keywords, requirements, and company values.\n"
        f"2. Use the FULL PROFILE to find matching certifications, awards, languages, and skills.\n"
        f"3. Include certifications/awards/languages ONLY if they add value for this specific role.\n"
        f"4. Tailor the summary to directly address the job's top 3 requirements.\n"
        f"5. For cover letter, reference specific details from the JD (company projects, values, tech stack).\n"
        f"6. CRITICAL: Copy ALL dates (start, end, period) EXACTLY from the profile - do NOT change any year values.\n"
        f"7. CRITICAL: Do NOT repeat any bullet point - each achievement must appear only once.\n"
        f"8. Return ONLY valid JSON matching the schema. No markdown, no extra text."
    )

def call_llm(prompt:str)->str:
    logger.info(f"=== LLM CALL START ===")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("=== LLM ERROR === GEMINI_API_KEY environment variable not set")
        raise RuntimeError("GEMINI_API_KEY not set")

    logger.info(f"API key found, length: {len(api_key)} chars")
    logger.info(f"Prompt length: {len(prompt)} chars")
    logger.info(f"Creating Gemini client...")

    try:
        client = genai.Client(api_key=api_key)
        logger.info(f"Gemini client created successfully")

        # Increased from 10k to 32k to prevent output truncation
        # Gemini 2.5 Pro supports up to 65,536 output tokens
        logger.info(f"Configuring generation settings: model=gemini-2.5-pro, temp=0.2, max_tokens=32000")
        cfg = GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=OUTPUT_JSON_SCHEMA,
            temperature=0.2,
            top_p=0.9,
            candidate_count=1,
            max_output_tokens=32000,
        )

        logger.info(f"Sending request to Gemini API...")
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[f"{SYSTEM}\n\n{prompt}"],
            config=cfg,
        )
        logger.info(f"Gemini API call completed, processing response...")

        # Log detailed response information for debugging
        logger.debug(f"LLM response object type: {type(response)}")
        logger.debug(f"LLM response candidates count: {len(response.candidates) if hasattr(response, 'candidates') else 'N/A'}")

        # Check for blocking or safety issues
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            logger.info(f"LLM prompt feedback: {response.prompt_feedback}")
            if hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
                logger.error(f"=== LLM ERROR === Prompt blocked! Reason: {response.prompt_feedback.block_reason}")
                raise RuntimeError(f"LLM prompt blocked: {response.prompt_feedback.block_reason}")

        # Check if we have candidates
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                logger.info(f"LLM finish reason: {candidate.finish_reason}")
                if candidate.finish_reason and str(candidate.finish_reason) != 'STOP':
                    logger.warning(f"LLM finished with non-STOP reason: {candidate.finish_reason}")

            if hasattr(candidate, 'safety_ratings'):
                logger.debug(f"LLM safety ratings: {candidate.safety_ratings}")

        # Get the actual text response
        logger.info(f"Extracting text from LLM response...")
        result = response.text if response.text else None

        if not result:
            logger.error("=== LLM ERROR === Returned empty response!")
            logger.error(f"Full response object: {response}")
            raise RuntimeError("LLM returned empty response. Check prompt feedback and safety ratings above.")

        logger.info(f"=== LLM CALL SUCCESS === Response length: {len(result)} chars")
        logger.debug(f"LLM response preview (first 200 chars): {result[:200]}")
        return result

    except Exception as e:
        logger.error(f"=== LLM CALL ERROR === {str(e)}", exc_info=True)
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Prompt that caused error (first 500 chars): {prompt[:500]}")
        raise
