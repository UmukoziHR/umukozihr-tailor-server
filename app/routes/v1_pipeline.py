"""
Pipeline management endpoints — UmukoziHR Tailor v2.5
Full pipeline view: evaluations, scoring, status tracking.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth.auth import get_current_user
from app.db.database import get_db
from app.db.models_pipeline import DiscoveredJob, JobEvaluation

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ManualEvaluateRequest(BaseModel):
    jd_text: str
    company: Optional[str] = None
    title: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    status: str  # new, evaluating, evaluated, queued, applied, dismissed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _evaluation_to_dict(ev: JobEvaluation) -> dict:
    return {
        "id": str(ev.id),
        "archetype": ev.archetype,
        "archetype_confidence": ev.archetype_confidence,
        "block_a": ev.block_a,
        "block_b": ev.block_b,
        "block_c": ev.block_c,
        "block_d": ev.block_d,
        "block_e": ev.block_e,
        "block_f": ev.block_f,
        "scores": {
            "cv_match": ev.score_cv_match,
            "north_star": ev.score_north_star,
            "comp": ev.score_comp,
            "cultural": ev.score_cultural,
            "red_flags": ev.score_red_flags,
            "global": ev.score_global,
        },
        "recommendation": ev.recommendation,
        "keywords": ev.keywords,
        "application_draft": ev.application_draft,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


def _job_with_evaluation(job: DiscoveredJob, db: Session) -> dict:
    """Build a job dict with its latest evaluation attached."""
    evaluation = db.query(JobEvaluation).filter(
        JobEvaluation.discovered_job_id == job.id
    ).order_by(desc(JobEvaluation.created_at)).first()

    result = {
        "id": str(job.id),
        "company": job.company,
        "title": job.title,
        "url": job.url,
        "platform": job.platform,
        "status": job.status,
        "discovered_at": job.discovered_at.isoformat() if job.discovered_at else None,
        "evaluation": _evaluation_to_dict(evaluation) if evaluation else None,
    }
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/pipeline/jobs")
def list_pipeline_jobs(
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    recommendation: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/v1/pipeline/jobs — all pipeline jobs with evaluations."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    query = db.query(DiscoveredJob).filter(
        DiscoveredJob.user_id == user_uuid,
        DiscoveredJob.status != "dismissed",
    )
    if status:
        query = query.filter(DiscoveredJob.status == status)

    total = query.count()
    jobs = query.order_by(desc(DiscoveredJob.discovered_at)).offset(offset).limit(limit).all()

    job_dicts = [_job_with_evaluation(j, db) for j in jobs]

    # Filter by score/recommendation if requested (post-join filter)
    if min_score is not None:
        job_dicts = [
            j for j in job_dicts
            if j["evaluation"] and (j["evaluation"]["scores"]["global"] or 0) >= min_score
        ]
    if recommendation:
        job_dicts = [
            j for j in job_dicts
            if j["evaluation"] and j["evaluation"]["recommendation"] == recommendation
        ]

    # Sort by score descending if evaluations exist
    job_dicts.sort(
        key=lambda j: j["evaluation"]["scores"]["global"] if j["evaluation"] else 0,
        reverse=True,
    )

    return {"jobs": job_dicts, "total": total, "limit": limit, "offset": offset}


@router.get("/pipeline/jobs/{job_id}")
def get_pipeline_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/v1/pipeline/jobs/{id} — single job with full evaluation + application status."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    job = db.query(DiscoveredJob).filter(
        DiscoveredJob.id == UUID(job_id),
        DiscoveredJob.user_id == user_uuid,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = _job_with_evaluation(job, db)
    result["jd_text"] = job.jd_text
    return result


@router.get("/pipeline/evaluations/{job_id}")
def get_job_evaluation(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/v1/pipeline/evaluations/{job_id} — full evaluation for a job."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    evaluation = db.query(JobEvaluation).filter(
        JobEvaluation.discovered_job_id == UUID(job_id),
        JobEvaluation.user_id == user_uuid,
    ).order_by(desc(JobEvaluation.created_at)).first()

    if not evaluation:
        raise HTTPException(status_code=404, detail="No evaluation found for this job")

    return _evaluation_to_dict(evaluation)


@router.post("/pipeline/evaluate")
async def evaluate_manual_jd(
    body: ManualEvaluateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST /api/v1/pipeline/evaluate — evaluate a manually-pasted JD (no scanner job needed)."""
    from app.db.models import Profile as DBProfile
    from app.db.models_pipeline import PortalConfig
    from app.core.job_evaluator import evaluate_job

    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    if len(body.jd_text.strip()) < 100:
        raise HTTPException(status_code=400, detail="JD text is too short to evaluate")

    profile_row = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()
    profile_data = profile_row.profile_data if profile_row else {}

    config = db.query(PortalConfig).filter(PortalConfig.user_id == user_uuid).first()
    target_roles = config.role_filters_positive if config else []

    evaluation = await evaluate_job(body.jd_text, profile_data, target_roles)

    db_eval = JobEvaluation(
        user_id=user_uuid,
        discovered_job_id=None,  # No scanner job — manual evaluation
        archetype=evaluation.archetype,
        archetype_confidence=evaluation.archetype_confidence,
        block_a=evaluation.block_a,
        block_b=evaluation.block_b,
        block_c=evaluation.block_c,
        block_d=evaluation.block_d,
        block_e=evaluation.block_e,
        block_f=evaluation.block_f,
        score_cv_match=evaluation.score_cv_match,
        score_north_star=evaluation.score_north_star,
        score_comp=evaluation.score_comp,
        score_cultural=evaluation.score_cultural,
        score_red_flags=evaluation.score_red_flags,
        score_global=evaluation.score_global,
        recommendation=evaluation.recommendation,
        keywords=evaluation.keywords,
        application_draft=evaluation.application_draft,
        jd_text_snapshot=evaluation.jd_text_snapshot,
    )
    db.add(db_eval)
    db.commit()
    db.refresh(db_eval)

    return _evaluation_to_dict(db_eval)


@router.get("/pipeline/stats")
def get_pipeline_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/v1/pipeline/stats — summary statistics for the user's pipeline."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    total_discovered = db.query(DiscoveredJob).filter(DiscoveredJob.user_id == user_uuid).count()
    total_evaluated = db.query(DiscoveredJob).filter(
        DiscoveredJob.user_id == user_uuid,
        DiscoveredJob.status.in_(["evaluated", "queued", "applied"]),
    ).count()
    total_queued = db.query(DiscoveredJob).filter(
        DiscoveredJob.user_id == user_uuid,
        DiscoveredJob.status == "queued",
    ).count()
    total_applied = db.query(DiscoveredJob).filter(
        DiscoveredJob.user_id == user_uuid,
        DiscoveredJob.status == "applied",
    ).count()

    # Count strong and good matches from evaluations
    strong_matches = db.query(JobEvaluation).filter(
        JobEvaluation.user_id == user_uuid,
        JobEvaluation.score_global >= 4.5,
    ).count()
    good_matches = db.query(JobEvaluation).filter(
        JobEvaluation.user_id == user_uuid,
        JobEvaluation.score_global >= 4.0,
        JobEvaluation.score_global < 4.5,
    ).count()

    return {
        "total_discovered": total_discovered,
        "total_evaluated": total_evaluated,
        "strong_matches": strong_matches,
        "good_matches": good_matches,
        "total_queued": total_queued,
        "total_applied": total_applied,
    }


@router.patch("/pipeline/jobs/{job_id}/status")
def update_job_status(
    job_id: str,
    body: UpdateStatusRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PATCH /api/v1/pipeline/jobs/{id}/status — update job status manually."""
    valid_statuses = {"new", "evaluating", "evaluated", "queued", "applied", "dismissed"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]
    job = db.query(DiscoveredJob).filter(
        DiscoveredJob.id == UUID(job_id),
        DiscoveredJob.user_id == user_uuid,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = body.status
    db.commit()
    return {"success": True, "job_id": job_id, "status": body.status}
