"""
Portal scanner endpoints — UmukoziHR Tailor v2.5
Trigger scans, list discovered jobs, and manage job status.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.auth import get_current_user
from app.core.job_scanner import scan_portals, fetch_jd_text
from app.db.database import get_db
from app.db.models_pipeline import DiscoveredJob, PortalConfig

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-memory flag to prevent concurrent scans per user
_scans_in_progress: set[str] = set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job_to_dict(job: DiscoveredJob) -> dict:
    return {
        "id": str(job.id),
        "company": job.company,
        "title": job.title,
        "url": job.url,
        "platform": job.platform,
        "jd_fetched": job.jd_fetched,
        "status": job.status,
        "discovered_at": job.discovered_at.isoformat() if job.discovered_at else None,
        "scan_source": job.scan_source,
    }


async def _run_scan_background(user_id: str):
    """Background task: run portal scan and persist results."""
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        user_uuid = UUID(user_id)
        config = db.query(PortalConfig).filter(PortalConfig.user_id == user_uuid).first()
        if not config:
            logger.warning(f"No portal config for user {user_id} — scan skipped")
            return

        portal_config_dict = {
            "companies": config.companies or [],
            "role_filters_positive": config.role_filters_positive or [],
            "role_filters_negative": config.role_filters_negative or [],
        }

        # Collect existing URLs for dedup
        existing = db.query(DiscoveredJob.url).filter(DiscoveredJob.user_id == user_uuid).all()
        existing_urls = {row[0] for row in existing}

        new_jobs, scan_result = await scan_portals(portal_config_dict, existing_urls)

        # Persist new jobs
        for job_data in new_jobs:
            db_job = DiscoveredJob(
                user_id=user_uuid,
                company=job_data.company,
                title=job_data.title,
                url=job_data.url,
                platform=job_data.platform,
                scan_source=job_data.scan_source,
                status="new",
            )
            db.add(db_job)

        # Update scan log on portal config
        config.last_scan_at = datetime.utcnow()
        config.scan_log = {
            "new_jobs": scan_result.new_jobs,
            "total_found": scan_result.total_found,
            "skipped_duplicates": scan_result.skipped_duplicates,
            "errors": scan_result.errors,
            "completed_at": datetime.utcnow().isoformat(),
        }
        db.commit()
        logger.info(f"Scan completed for user {user_id}: {scan_result.new_jobs} new jobs")

    except Exception as e:
        logger.error(f"Background scan failed for user {user_id}: {e}", exc_info=True)
    finally:
        _scans_in_progress.discard(user_id)
        db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/scanner/scan")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST /api/v1/scanner/scan — trigger a portal scan in the background."""
    user_id = current_user["user_id"]

    if user_id in _scans_in_progress:
        return {"success": False, "message": "Scan already in progress for your account"}

    # Verify user has a portal config
    user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
    config = db.query(PortalConfig).filter(PortalConfig.user_id == user_uuid).first()
    if not config or not config.companies:
        raise HTTPException(
            status_code=400,
            detail="No portal configuration found. Configure target companies first at /api/v1/portals/config"
        )

    _scans_in_progress.add(user_id)
    background_tasks.add_task(_run_scan_background, user_id)

    return {
        "success": True,
        "message": f"Scan started for {len(config.companies)} configured companies",
        "scanning_companies": len([c for c in config.companies if c.get("enabled", True)]),
    }


@router.get("/scanner/scan/status")
def get_scan_status(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/v1/scanner/scan/status — check if a scan is running + last scan info."""
    user_id = current_user["user_id"]
    user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

    is_scanning = user_id in _scans_in_progress

    config = db.query(PortalConfig).filter(PortalConfig.user_id == user_uuid).first()
    last_scan_at = None
    scan_log = None
    if config:
        last_scan_at = config.last_scan_at.isoformat() if config.last_scan_at else None
        scan_log = config.scan_log

    return {
        "is_scanning": is_scanning,
        "last_scan_at": last_scan_at,
        "last_scan_result": scan_log,
    }


@router.get("/scanner/jobs")
def list_discovered_jobs(
    status: Optional[str] = None,
    company: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/v1/scanner/jobs — list discovered jobs with optional filters."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    query = db.query(DiscoveredJob).filter(DiscoveredJob.user_id == user_uuid)

    if status:
        query = query.filter(DiscoveredJob.status == status)
    if company:
        query = query.filter(DiscoveredJob.company.ilike(f"%{company}%"))

    total = query.count()
    jobs = query.order_by(DiscoveredJob.discovered_at.desc()).offset(offset).limit(limit).all()

    return {
        "jobs": [_job_to_dict(j) for j in jobs],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/scanner/jobs/{job_id}")
def get_discovered_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/v1/scanner/jobs/{id} — get a single discovered job."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]
    job = db.query(DiscoveredJob).filter(
        DiscoveredJob.id == UUID(job_id),
        DiscoveredJob.user_id == user_uuid,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = _job_to_dict(job)
    result["jd_text"] = job.jd_text  # Include full JD text if fetched
    return result


@router.post("/scanner/jobs/{job_id}/dismiss")
def dismiss_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST /api/v1/scanner/jobs/{id}/dismiss — mark job as dismissed."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]
    job = db.query(DiscoveredJob).filter(
        DiscoveredJob.id == UUID(job_id),
        DiscoveredJob.user_id == user_uuid,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "dismissed"
    db.commit()
    return {"success": True, "job_id": job_id, "status": "dismissed"}


@router.post("/scanner/jobs/{job_id}/fetch-jd")
async def fetch_job_jd(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST /api/v1/scanner/jobs/{id}/fetch-jd — fetch the full JD text for a job."""
    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]
    job = db.query(DiscoveredJob).filter(
        DiscoveredJob.id == UUID(job_id),
        DiscoveredJob.user_id == user_uuid,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.jd_fetched and job.jd_text:
        return {"success": True, "jd_text": job.jd_text, "cached": True}

    jd_text = await fetch_jd_text(job.url)
    if jd_text:
        job.jd_text = jd_text
        job.jd_fetched = True
        db.commit()
        return {"success": True, "jd_text": jd_text, "cached": False}
    else:
        raise HTTPException(status_code=422, detail="Could not extract JD text from this URL")


@router.post("/scanner/jobs/{job_id}/evaluate")
async def trigger_job_evaluation(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST /api/v1/scanner/jobs/{id}/evaluate — trigger evaluation for a discovered job."""
    from app.db.models_pipeline import JobEvaluation
    from app.db.models import Profile as DBProfile
    from app.core.job_evaluator import evaluate_job
    from app.db.models_pipeline import PortalConfig

    user_uuid = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]

    job = db.query(DiscoveredJob).filter(
        DiscoveredJob.id == UUID(job_id),
        DiscoveredJob.user_id == user_uuid,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Fetch JD if not already done
    if not job.jd_text:
        jd_text = await fetch_jd_text(job.url)
        if jd_text:
            job.jd_text = jd_text
            job.jd_fetched = True
            db.commit()

    if not job.jd_text:
        raise HTTPException(status_code=422, detail="Cannot evaluate without JD text. Try fetching the JD first.")

    # Get user's profile
    profile_row = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()
    profile_data = profile_row.profile_data if profile_row else {}

    # Get target roles from portal config
    config = db.query(PortalConfig).filter(PortalConfig.user_id == user_uuid).first()
    target_roles = config.role_filters_positive if config else []

    # Mark job as evaluating
    job.status = "evaluating"
    db.commit()

    # Run evaluation
    evaluation = await evaluate_job(job.jd_text, profile_data, target_roles)

    # Persist evaluation
    db_eval = JobEvaluation(
        user_id=user_uuid,
        discovered_job_id=job.id,
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
    job.status = "evaluated"
    db.commit()
    db.refresh(db_eval)

    return {
        "success": True,
        "evaluation_id": str(db_eval.id),
        "score": evaluation.score_global,
        "recommendation": evaluation.recommendation,
        "archetype": evaluation.archetype,
    }
