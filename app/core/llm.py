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
"You are an expert ATS resume & cover-letter tailor"
"Return ONLY valid JSON for the given schema"
"Never invent companies, schools, or dates"
"Use exact JD Keyowrds only when truthful"
"Respect region style rules. Keep concise, metric-first quantitative bullets, each bullet also flowing in the oder <action -> impactful result>"
)

# Strict JSON Schema for gemini to avoid hallucinations and stick to our convention
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


def build_user_prompt(profile_min_json:str, jd_text:str, region_rules:dict, selected_bullets_json:str, schema_json:str)-> str:
    return (
        f"REGION_RULES:\n{json.dumps(region_rules, ensure_ascii=False)}\n\n"
        f"PROFILE_MIN:\n{profile_min_json}\n\n"
        f"JD_TEXT:\n{jd_text}\n\n"
        f"PRESELECTED_PROFILE_BULLETS:\n{selected_bullets_json}\n\n"
        f"SCHEMA (immutable):\n{schema_json}\n\n"
        "Return JSON only."
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

        logger.info(f"Configuring generation settings: model=gemini-2.5-flash, temp=0.2, max_tokens=4000")
        cfg = GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=OUTPUT_JSON_SCHEMA,
            temperature=0.2,
            top_p=0.9,
            candidate_count=1,
            max_output_tokens=4000,
        )

        logger.info(f"Sending request to Gemini API...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
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
