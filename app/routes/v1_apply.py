"""
Application queue endpoints — UmukoziHR Tailor v2.5
Manage the application queue and form-fill review.
IMPORTANT: This service NEVER auto-submits. Users review and submit manually.
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth.auth import get_current_user
from app.db.database import get_db
from app.db.models_pipeline import ApplicationQueue, DiscoveredJob, JobEvaluation

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _queue_item_to_dict(item: ApplicationQueue, db: Session) -> dict:
    """Build a queue item dict with related job and evaluation info."""
    job = db.query(DiscoveredJob).filter(DiscoveredJob.id == item.discovered_job_id).first()
    evaluation = None
    if item.evaluation_id:
        ev = db.query(JobEvaluation).filter(JobEvaluation.id == item.evaluation_id).first()
        if ev:
            evaluation = {
                "id": str(ev.id),
                "archetype": ev.archetype,
                "score_global": ev.score_global,
                "recommendation": ev.recommendation,
                "application_draft": ev.application_draft,
                "keywords": ev.keywords,
            }

    return {
        "id": str(item.id),
        "status": item.status,
        "form_url": item.form_url,
        "filled_fields": item.filled_fields or [],
        "notes": item.notes,
        "queued_at": item.queued_at.isoformat() if item.queued_at else None,
        "filled_at": item.filled_at.isoformat() if item.filled_at else None,
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "job": {
            "id": str(job.id) if job else None,
            "company": job.company if job else None,
            "title": job.title if job else None,
            "url": job.url if job else None,
            "platform": job.platform if job else None,
        } if job else None,
        "evaluation": evaluation,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/apply/queue/{job_id}")
async def queue_job_for_application(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST /api/v1/apply/queue/{job_id} — add a job to the application queue and analyze the form."""
    from app.db.models import Profile as DBProfile
    from app.core.job_applicator import analyze_application_form

    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    # Verify the job exists and belongs to this user
    job = db.query(DiscoveredJob).filter(
        DiscoveredJob.id == UUID(job_id),
        DiscoveredJob.user_id == user_uuid,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if already queued
    existing = db.query(ApplicationQueue).filter(
        ApplicationQueue.discovered_job_id == job.id,
        ApplicationQueue.user_id == user_uuid,
        ApplicationQueue.status.in_(["queued", "form_filled", "needs_review"]),
    ).first()
    if existing:
        return {"success": False, "message": "This job is already in your application queue", "queue_id": str(existing.id)}

    # Find the latest evaluation for this job
    evaluation = db.query(JobEvaluation).filter(
        JobEvaluation.discovered_job_id == job.id,
        JobEvaluation.user_id == user_uuid,
    ).order_by(desc(JobEvaluation.created_at)).first()

    evaluation_data = None
    if evaluation:
        evaluation_data = {
            "application_draft": evaluation.application_draft,
            "keywords": evaluation.keywords,
        }

    # Get user profile for form filling
    profile_row = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()
    profile_data = profile_row.profile_data if profile_row else {}

    # The application URL for Ashby/Greenhouse/Lever is usually the job URL
    form_url = job.url

    # Analyze the form
    form_result = await analyze_application_form(
        form_url=form_url,
        profile_data=profile_data,
        evaluation_data=evaluation_data,
    )

    # Create queue entry
    queue_item = ApplicationQueue(
        user_id=user_uuid,
        discovered_job_id=job.id,
        evaluation_id=evaluation.id if evaluation else None,
        status="form_filled" if form_result.filled_fields else "queued",
        form_url=form_url,
        filled_fields=[
            {
                "field_name": f.field_name,
                "field_type": f.field_type,
                "value": f.value,
                "confidence": f.confidence,
                "profile_path": f.profile_path,
            }
            for f in form_result.filled_fields
        ],
        notes=form_result.notes,
        filled_at=datetime.utcnow() if form_result.filled_fields else None,
    )
    db.add(queue_item)
    job.status = "queued"
    db.commit()
    db.refresh(queue_item)

    return {
        "success": True,
        "queue_id": str(queue_item.id),
        "fields_pre_filled": len(form_result.filled_fields),
        "fields_manual": len(form_result.unfilled_fields),
        "platform_detected": form_result.platform_detected,
        "notes": form_result.notes,
        "message": "Reviewed pre-filled fields below. Open the job URL to apply manually.",
    }


@router.get("/apply/queue")
def get_application_queue(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/v1/apply/queue — list all queued applications."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    query = db.query(ApplicationQueue).filter(ApplicationQueue.user_id == user_uuid)
    if status:
        query = query.filter(ApplicationQueue.status == status)

    items = query.order_by(desc(ApplicationQueue.queued_at)).all()
    return {
        "queue": [_queue_item_to_dict(item, db) for item in items],
        "total": len(items),
    }


@router.get("/apply/queue/{queue_id}/form-fields")
def get_form_fields(
    queue_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/v1/apply/queue/{id}/form-fields — get pre-analyzed form fields for review."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    item = db.query(ApplicationQueue).filter(
        ApplicationQueue.id == UUID(queue_id),
        ApplicationQueue.user_id == user_uuid,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    return _queue_item_to_dict(item, db)


@router.post("/apply/queue/{queue_id}/confirm")
def confirm_application(
    queue_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST /api/v1/apply/queue/{id}/confirm — user confirms they manually submitted the application."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    item = db.query(ApplicationQueue).filter(
        ApplicationQueue.id == UUID(queue_id),
        ApplicationQueue.user_id == user_uuid,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    item.status = "submitted"
    item.submitted_at = datetime.utcnow()

    # Update the discovered job status
    job = db.query(DiscoveredJob).filter(DiscoveredJob.id == item.discovered_job_id).first()
    if job:
        job.status = "applied"

    db.commit()
    return {"success": True, "queue_id": queue_id, "status": "submitted", "submitted_at": item.submitted_at.isoformat()}


@router.delete("/apply/queue/{queue_id}")
def remove_from_queue(
    queue_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """DELETE /api/v1/apply/queue/{id} — remove a job from the queue."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    item = db.query(ApplicationQueue).filter(
        ApplicationQueue.id == UUID(queue_id),
        ApplicationQueue.user_id == user_uuid,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    # Revert job status to evaluated if it was queued
    if item.status in ("queued", "form_filled", "needs_review"):
        job = db.query(DiscoveredJob).filter(DiscoveredJob.id == item.discovered_job_id).first()
        if job and job.status == "queued":
            job.status = "evaluated"

    db.delete(item)
    db.commit()
    return {"success": True, "queue_id": queue_id}
