"""
History and regeneration endpoints for v1.3
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from uuid import UUID

from app.models import HistoryResponse, HistoryItem, RegenerateResponse
from app.db.database import get_db
from app.db.models import Run as DBRun, Job as DBJob, Profile as DBProfile
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
                region=job.region,
                status=run.status,
                profile_version=run.profile_version,
                artifacts_urls=run.artifacts_urls or {},
                created_at=run.created_at.isoformat()
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
