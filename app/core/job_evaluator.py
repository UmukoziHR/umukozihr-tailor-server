"""
Job Evaluation Engine — UmukoziHR Tailor v2.5
Gemini-powered 6-block evaluation adapted from CareerOps evaluation logic.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.core.llm import call_llm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Archetype definitions (from CareerOps _shared.md)
# ---------------------------------------------------------------------------

ARCHETYPES = {
    "ai_platform": {
        "label": "AI Platform / LLMOps",
        "signals": ["observability", "evals", "pipeline", "monitoring", "reliability", "llmops", "mlops"],
    },
    "agentic": {
        "label": "Agentic / Automation",
        "signals": ["agent", "hitl", "orchestration", "workflow", "multi-agent", "automation", "agentic"],
    },
    "technical_pm": {
        "label": "Technical AI PM",
        "signals": ["prd", "roadmap", "discovery", "stakeholder", "product manager", "product management"],
    },
    "solutions_architect": {
        "label": "AI Solutions Architect",
        "signals": ["architecture", "enterprise", "integration", "design", "systems design", "solution"],
    },
    "forward_deployed": {
        "label": "AI Forward Deployed Engineer",
        "signals": ["client-facing", "client facing", "deploy", "prototype", "fast delivery", "field engineer", "pre-sales"],
    },
    "transformation": {
        "label": "AI Transformation Lead",
        "signals": ["change management", "adoption", "enablement", "transformation", "org", "upskilling"],
    },
}

# ---------------------------------------------------------------------------
# Output schema for Gemini structured JSON
# ---------------------------------------------------------------------------

EVALUATION_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "archetype": {"type": "string"},
        "archetype_confidence": {"type": "string"},
        "block_a": {
            "type": "object",
            "properties": {
                "role_summary": {"type": "string"},
                "domain": {"type": "string"},
                "function": {"type": "string"},
                "seniority": {"type": "string"},
                "remote_policy": {"type": "string"},
                "team_size": {"type": "string"},
            },
        },
        "block_b": {
            "type": "object",
            "properties": {
                "requirements_match": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "requirement": {"type": "string"},
                            "cv_match": {"type": "string"},
                            "match_quality": {"type": "string"},
                        },
                    },
                },
                "gaps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "gap": {"type": "string"},
                            "is_blocker": {"type": "boolean"},
                            "mitigation": {"type": "string"},
                        },
                    },
                },
            },
        },
        "block_c": {
            "type": "object",
            "properties": {
                "jd_level": {"type": "string"},
                "strategy": {"type": "string"},
                "downlevel_plan": {"type": "string"},
            },
        },
        "block_e": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "current": {"type": "string"},
                    "change": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
        "block_f": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "jd_requirement": {"type": "string"},
                    "situation": {"type": "string"},
                    "task": {"type": "string"},
                    "action": {"type": "string"},
                    "result": {"type": "string"},
                    "reflection": {"type": "string"},
                },
            },
        },
        "scores": {
            "type": "object",
            "properties": {
                "cv_match": {"type": "number"},
                "north_star": {"type": "number"},
                "comp": {"type": "number"},
                "cultural": {"type": "number"},
                "red_flags": {"type": "number"},
                "global": {"type": "number"},
            },
        },
        "recommendation": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "application_draft": {
            "type": "object",
            "properties": {
                "why_role": {"type": "string"},
                "why_company": {"type": "string"},
                "relevant_experience": {"type": "string"},
                "good_fit": {"type": "string"},
            },
        },
    },
    "required": ["archetype", "block_a", "block_b", "block_c", "block_e", "block_f", "scores", "recommendation", "keywords"],
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

EVALUATION_SYSTEM_PROMPT = """You are a career advisor evaluating a job posting against a candidate's profile.
Your goal is to assess fit quality honestly and help the candidate decide whether to invest time applying.

ARCHETYPE DETECTION — classify into ONE of:
- "ai_platform": signals — observability, evals, pipelines, monitoring, reliability, LLMOps, MLOps
- "agentic": signals — agent, HITL, orchestration, workflow, multi-agent, automation
- "technical_pm": signals — PRD, roadmap, discovery, stakeholder management, product manager
- "solutions_architect": signals — architecture, enterprise integrations, systems design
- "forward_deployed": signals — client-facing, prototype, fast delivery, field engineer
- "transformation": signals — change management, adoption, enablement, organizational scaling
If the role is a hybrid of two, set archetype_confidence to "hybrid: X + Y".

SCORING DIMENSIONS (1-5 scale, where 5 is best):
- cv_match: How well the candidate's skills/experience match JD requirements
- north_star: How well the role fits the candidate's stated target roles
- comp: Compensation alignment (default 3.0 if no salary data in JD)
- cultural: Company culture signals from JD text (growth, stability, values alignment)
- red_flags: 5=no red flags, 1=many serious red flags (e.g., unpaid, visa issues, tech mismatch)
- global: Weighted average — cv_match×30% + north_star×25% + comp×15% + cultural×15% + red_flags×15%

RECOMMENDATION thresholds:
- global >= 4.5 → "apply_now"
- global >= 4.0 → "worth_applying"
- global >= 3.5 → "consider"
- global < 3.5 → "skip"

BLOCK B (CV Match):
- For each key requirement in the JD, cite the closest matching line from the candidate's profile
- match_quality: "strong" (direct match), "partial" (adjacent experience), "gap" (not present)
- For gaps: assess if it's a hard blocker and provide a concrete mitigation strategy
- Never invent experience. Only cite what is actually in the profile.

BLOCK E (Personalization):
- Top 5 specific changes to the CV to maximize keyword alignment with this JD
- Reframe EXISTING experience using JD vocabulary — never add fabricated experience
- Focus on summary rewrite, bullet reordering, and keyword injection

BLOCK F (Interview Prep):
- 6-8 STAR+R stories mapped to specific JD requirements
- Draw stories ONLY from the candidate's actual experience sections
- Reflection column: what was learned / what would be done differently (signals seniority)

APPLICATION DRAFT (only include if scores.global >= 4.5):
- why_role: 2-3 sentences, references something specific in the JD
- why_company: 1-2 sentences, references something real about the company
- relevant_experience: 1 proof point with metric from the candidate's profile
- good_fit: 1 sentence on the intersection of candidate skills and role requirements

KEYWORDS: Extract 10-20 keywords from the JD that should appear in the CV for ATS matching.

CRITICAL RULES:
- Never invent metrics, companies, dates, or achievements not in the profile
- Use candidate's actual job titles and companies verbatim
- Be direct and honest — a "skip" recommendation is more valuable than false encouragement
- No corporate speak: never use "passionate about", "leveraged", "synergies", "robust", "seamless"
"""


def _build_evaluation_prompt(jd_text: str, profile_data: dict, target_roles: list[str]) -> str:
    """Build the user-facing evaluation prompt."""
    target_str = ", ".join(target_roles) if target_roles else "Not specified"
    profile_json = json.dumps(profile_data, indent=2, default=str)
    return f"""Evaluate this job posting against the candidate's profile.

## Candidate's Target Roles
{target_str}

## Candidate's Profile
```json
{profile_json}
```

## Job Description
{jd_text}

Provide a complete 6-block evaluation in JSON format following the schema.
"""


def _compute_global_score(scores: dict) -> float:
    """Compute weighted global score from component scores."""
    weights = {
        "cv_match": 0.30,
        "north_star": 0.25,
        "comp": 0.15,
        "cultural": 0.15,
        "red_flags": 0.15,
    }
    total = sum(scores.get(dim, 3.0) * weight for dim, weight in weights.items())
    return round(min(5.0, max(1.0, total)), 2)


def _score_to_recommendation(global_score: float) -> str:
    if global_score >= 4.5:
        return "apply_now"
    elif global_score >= 4.0:
        return "worth_applying"
    elif global_score >= 3.5:
        return "consider"
    return "skip"


@dataclass
class EvaluationResult:
    archetype: str
    archetype_confidence: str
    block_a: dict
    block_b: dict
    block_c: dict
    block_d: dict
    block_e: list
    block_f: list
    score_cv_match: float
    score_north_star: float
    score_comp: float
    score_cultural: float
    score_red_flags: float
    score_global: float
    recommendation: str
    keywords: list
    application_draft: Optional[dict] = None
    jd_text_snapshot: Optional[str] = None
    error: Optional[str] = None


def _mock_evaluation(jd_text: str) -> EvaluationResult:
    """Return a placeholder evaluation when LLM is unavailable (dev/testing mode)."""
    return EvaluationResult(
        archetype="agentic",
        archetype_confidence="primary",
        block_a={
            "role_summary": "[Mock] AI Engineer role requiring strong Python skills",
            "domain": "platform",
            "function": "build",
            "seniority": "Senior",
            "remote_policy": "Remote",
            "team_size": "Not specified",
        },
        block_b={
            "requirements_match": [
                {"requirement": "Python", "cv_match": "5+ years Python experience", "match_quality": "strong"}
            ],
            "gaps": [],
        },
        block_c={
            "jd_level": "Senior",
            "strategy": "Emphasize production AI systems experience",
            "downlevel_plan": "Negotiate review at 6 months with clear promotion criteria",
        },
        block_d={},
        block_e=[
            {
                "section": "Summary",
                "current": "Current summary",
                "change": "Rewrite to lead with AI agent orchestration experience",
                "reason": "JD emphasizes agentic systems",
            }
        ],
        block_f=[
            {
                "jd_requirement": "Build production AI systems",
                "situation": "[From profile]",
                "task": "Lead development of X",
                "action": "Built Y using Z",
                "result": "Achieved W metric",
                "reflection": "Would have added observability earlier",
            }
        ],
        score_cv_match=4.0,
        score_north_star=4.0,
        score_comp=3.0,
        score_cultural=3.5,
        score_red_flags=4.5,
        score_global=3.9,
        recommendation="worth_applying",
        keywords=["Python", "LLM", "agent", "orchestration", "AI"],
        application_draft=None,
        jd_text_snapshot=jd_text[:500] if jd_text else None,
        error="mock_mode",
    )


async def evaluate_job(
    jd_text: str,
    profile_data: dict,
    target_roles: list[str] | None = None,
    mock_mode: bool = False,
) -> EvaluationResult:
    """
    Run a 6-block Gemini evaluation of a job posting against a candidate's profile.

    Args:
        jd_text: Full job description text.
        profile_data: ProfileV3 data dict from the database.
        target_roles: User's target role keywords from portal config.
        mock_mode: If True, return dummy data without calling Gemini.

    Returns:
        EvaluationResult with all 6 blocks, scores, and recommendation.
    """
    if mock_mode or not jd_text:
        return _mock_evaluation(jd_text or "")

    prompt = _build_evaluation_prompt(jd_text, profile_data, target_roles or [])

    try:
        raw = call_llm(
            system_prompt=EVALUATION_SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=EVALUATION_OUTPUT_SCHEMA,
        )

        scores = raw.get("scores", {})
        # Let Gemini compute global, but recalculate if it's missing or out of range
        global_score = scores.get("global")
        if not global_score or not (1.0 <= global_score <= 5.0):
            global_score = _compute_global_score(scores)

        recommendation = raw.get("recommendation") or _score_to_recommendation(global_score)

        return EvaluationResult(
            archetype=raw.get("archetype", "unknown"),
            archetype_confidence=raw.get("archetype_confidence", "primary"),
            block_a=raw.get("block_a", {}),
            block_b=raw.get("block_b", {}),
            block_c=raw.get("block_c", {}),
            block_d=raw.get("block_d", {}),  # comp research — may be empty
            block_e=raw.get("block_e", []),
            block_f=raw.get("block_f", []),
            score_cv_match=float(scores.get("cv_match", 3.0)),
            score_north_star=float(scores.get("north_star", 3.0)),
            score_comp=float(scores.get("comp", 3.0)),
            score_cultural=float(scores.get("cultural", 3.0)),
            score_red_flags=float(scores.get("red_flags", 3.0)),
            score_global=global_score,
            recommendation=recommendation,
            keywords=raw.get("keywords", []),
            application_draft=raw.get("application_draft"),
            jd_text_snapshot=jd_text[:2000],
        )

    except Exception as e:
        logger.error(f"Job evaluation failed: {e}", exc_info=True)
        result = _mock_evaluation(jd_text)
        result.error = str(e)
        return result
