"""
History and regeneration endpoints for v1.3
Job Landing Celebration endpoints for v1.5
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from uuid import UUID
from urllib.parse import quote

from app.models import HistoryResponse, HistoryItem, RegenerateResponse, JobLandedRequest, JobLandedResponse, LandedStatsResponse, LandedJobItem
from app.db.database import get_db
from app.db.models import Run as DBRun, Job as DBJob, Profile as DBProfile, User as DBUser
from app.auth.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/history", response_model=HistoryResponse)
def get_history(
    page: int = 1,
    page_size: int = 10,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/history
    List past runs with pagination
    """
    user_id = current_user["user_id"]
    logger.info(f"Fetching history for user: {user_id}, page: {page}")

    # Convert string UUID to UUID object for database query
    try:
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Calculate offset
    offset = (page - 1) * page_size

    # Query runs with joins to get job details
    runs_query = (
        db.query(DBRun, DBJob)
        .join(DBJob, DBRun.job_id == DBJob.id)
        .filter(DBRun.user_id == user_uuid)
        .order_by(desc(DBRun.created_at))
    )

    # Get total count
    total = runs_query.count()

    # Get paginated results
    results = runs_query.offset(offset).limit(page_size).all()

    # Build response items
    history_items = []
    for run, job in results:
        history_items.append(
            HistoryItem(
                run_id=str(run.id),
                job_id=str(job.id),
                company=job.company,
                title=job.title,
                job_title=job.title,  # Alias for frontend
                region=job.region,
                status=run.status,
                profile_version=run.profile_version,
                artifacts_urls=run.artifacts_urls or {},
                created_at=run.created_at.isoformat(),
                job_landed=run.job_landed or False,
                landed_at=run.landed_at.isoformat() if run.landed_at else None
            )
        )

    return HistoryResponse(
        runs=history_items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/history/{run_id}/regenerate", response_model=RegenerateResponse)
def regenerate_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/history/{run_id}/regenerate
    Re-run generation for a past job using current profile
    """
    user_id = current_user["user_id"]
    logger.info(f"Regenerating run: {run_id} for user: {user_id}")

    # Convert string UUID to UUID object for database query
    try:
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Find the original run
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format")

    original_run = db.query(DBRun).filter(
        DBRun.id == run_uuid,
        DBRun.user_id == user_uuid
    ).first()

    if not original_run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get the job details
    job = db.query(DBJob).filter(DBJob.id == original_run.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Associated job not found")

    # Get current profile
    profile = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Please complete onboarding.")

    # Import generate logic (avoid circular imports)
    from app.routes.v1_generate import run_generation_for_job

    try:
        # Create new run with current profile
        new_run = run_generation_for_job(
            db=db,
            user_id=user_id,
            job=job,
            profile_data=profile.profile_data,
            profile_version=profile.version
        )

        logger.info(f"Regeneration successful. New run_id: {new_run.id}")

        return RegenerateResponse(
            success=True,
            new_run_id=str(new_run.id),
            message=f"Successfully regenerated with profile version {profile.version}"
        )

    except Exception as e:
        logger.error(f"Regeneration failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Regeneration failed: {str(e)}"
        )


# ============================================
# JOB LANDING CELEBRATION ENDPOINTS (v1.5)
# ============================================

@router.post("/history/{run_id}/landed", response_model=JobLandedResponse)
def mark_job_landed(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/history/{run_id}/landed
    Mark a job application as landed (user got the job!)
    """
    user_id = current_user["user_id"]
    logger.info(f"Marking job as landed: {run_id} for user: {user_id}")

    # Convert string UUID to UUID object
    try:
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    # Find the run
    run = db.query(DBRun).filter(
        DBRun.id == run_uuid,
        DBRun.user_id == user_uuid
    ).first()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Check if already landed
    if run.job_landed:
        raise HTTPException(status_code=400, detail="This job has already been marked as landed")

    # Get the job details
    job = db.query(DBJob).filter(DBJob.id == run.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Associated job not found")

    # Get the user
    user = db.query(DBUser).filter(DBUser.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Mark as landed
    now = datetime.utcnow()
    run.job_landed = True
    run.landed_at = now

    # Update user stats
    user.landed_job_count = (user.landed_job_count or 0) + 1
    user.latest_landed_company = job.company
    user.latest_landed_title = job.title
    user.latest_landed_at = now

    db.commit()

    logger.info(f"Job landed! User {user_id} got job at {job.company} as {job.title}")

    # Generate LinkedIn share content
    share_text = f"🎉 Excited to share that I've landed a new role as {job.title} at {job.company}! Thanks to everyone who supported my journey. #NewJob #CareerGrowth #Hired"
    linkedin_share_url = f"https://www.linkedin.com/sharing/share-offsite/?url=https://tailor.umukozihr.com&title={quote(share_text)}"

    return JobLandedResponse(
        success=True,
        company=job.company,
        title=job.title,
        landed_at=now.isoformat(),
        total_landed=user.landed_job_count,
        message=f"Congratulations! You landed the {job.title} role at {job.company}! 🎉",
        linkedin_share_url=linkedin_share_url,
        linkedin_share_text=share_text
    )


@router.get("/history/landed", response_model=LandedStatsResponse)
def get_landed_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/history/landed
    Get user's job landing statistics and history
    """
    user_id = current_user["user_id"]
    logger.info(f"Fetching landed stats for user: {user_id}")

    # Convert string UUID to UUID object
    try:
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Get user
    user = db.query(DBUser).filter(DBUser.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all landed jobs
    landed_runs = (
        db.query(DBRun, DBJob)
        .join(DBJob, DBRun.job_id == DBJob.id)
        .filter(DBRun.user_id == user_uuid, DBRun.job_landed == True)
        .order_by(desc(DBRun.landed_at))
        .all()
    )

    # Build landed jobs list
    landed_jobs = []
    for run, job in landed_runs:
        landed_jobs.append(
            LandedJobItem(
                run_id=str(run.id),
                job_id=str(job.id),
                company=job.company,
                title=job.title,
                region=job.region,
                landed_at=run.landed_at.isoformat() if run.landed_at else "",
                created_at=run.created_at.isoformat() if run.created_at else ""
            )
        )

    return LandedStatsResponse(
        total_landed=user.landed_job_count or 0,
        latest_company=user.latest_landed_company,
        latest_title=user.latest_landed_title,
        latest_landed_at=user.latest_landed_at.isoformat() if user.latest_landed_at else None,
        landed_jobs=landed_jobs
    )
