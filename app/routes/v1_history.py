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

from app.models import HistoryResponse, HistoryItem, RegenerateResponse, JobLandedRequest, JobLandedResponse, LandedStatsResponse, LandedJobItem, MarkInterviewRequest, MarkOfferRequest, MarkMilestoneResponse, Achievement
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
                landed_at=run.landed_at.isoformat() if run.landed_at else None,
                got_interview=run.got_interview or False,
                interview_at=run.interview_at.isoformat() if run.interview_at else None,
                got_offer=run.got_offer or False,
                offer_at=run.offer_at.isoformat() if run.offer_at else None
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

    # Send job landed celebration email
    try:
        from app.core.email_service import send_job_landed_email
        # Get user's name from profile or email
        profile = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()
        name = user.email.split("@")[0].replace(".", " ").title()
        if profile and profile.profile_data:
            name = profile.profile_data.get("basics", {}).get("name", name)
        send_job_landed_email(
            email=user.email,
            name=name,
            user_id=str(user.id),
            company=job.company,
            title=job.title
        )
    except Exception as email_error:
        logger.warning(f"Failed to send job landed email: {email_error}")

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


# ============================================
# GAMIFICATION: INTERVIEW & OFFER ENDPOINTS (v1.6)
# ============================================

@router.post("/history/{run_id}/interview", response_model=MarkMilestoneResponse)
def mark_got_interview(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/history/{run_id}/interview
    Mark that user got an interview for this job application
    """
    user_id = current_user["user_id"]
    logger.info(f"Marking interview received: {run_id} for user: {user_id}")

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

    # Check if already marked
    if run.got_interview:
        raise HTTPException(status_code=400, detail="This job has already been marked as interview received")

    # Get the job details
    job = db.query(DBJob).filter(DBJob.id == run.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Associated job not found")

    # Get the user
    user = db.query(DBUser).filter(DBUser.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Mark as interview received
    now = datetime.utcnow()
    run.got_interview = True
    run.interview_at = now

    # Update user stats
    user.interviews_count = (user.interviews_count or 0) + 1

    # Check for new achievements
    from app.core.achievements import get_user_stats, check_achievements, unlock_achievements, update_streak
    
    # Update streak
    update_streak(db, str(user_uuid))
    
    db.commit()

    # Get updated stats and check achievements
    stats = get_user_stats(db, str(user_uuid))
    newly_unlocked, xp_earned = check_achievements(stats)
    
    new_achievements = []
    if newly_unlocked:
        achievement_ids = [a["id"] for a in newly_unlocked]
        unlock_achievements(db, str(user_uuid), achievement_ids, xp_earned)
        # Convert to response format
        new_achievements = [
            Achievement(
                id=a["id"],
                name=a["name"],
                description=a["description"],
                icon=a["icon"],
                tier=a["tier"].value if hasattr(a["tier"], 'value') else a["tier"],
                xp=a["xp"],
                color=a["color"],
                unlocked=True,
                unlocked_at=now.isoformat(),
                pro_only=a.get("pro_only", False)
            ) for a in newly_unlocked
        ]

    logger.info(f"Interview received! User {user_id} got interview at {job.company} for {job.title}")

    # Send interview celebration email
    try:
        from app.core.email_service import send_interview_celebration_email
        # Get user's name from profile or email
        profile = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()
        name = user.email.split("@")[0].replace(".", " ").title()
        if profile and profile.profile_data:
            name = profile.profile_data.get("basics", {}).get("name", name)
        send_interview_celebration_email(
            email=user.email,
            name=name,
            user_id=str(user.id),
            company=job.company,
            title=job.title
        )
    except Exception as email_error:
        logger.warning(f"Failed to send interview celebration email: {email_error}")

    # Generate LinkedIn share content
    share_text = f"📞 Exciting news! I just got an interview call for {job.title} at {job.company}! The job hunt continues... #JobSearch #Interview #CareerProgress"
    linkedin_share_url = f"https://www.linkedin.com/sharing/share-offsite/?url=https://tailor.umukozihr.com&title={quote(share_text)}"

    return MarkMilestoneResponse(
        success=True,
        company=job.company,
        title=job.title,
        milestone_type="interview",
        marked_at=now.isoformat(),
        total_count=user.interviews_count,
        new_achievements=new_achievements,
        xp_earned=xp_earned,
        message=f"Amazing! You got an interview for {job.title} at {job.company}! 📞",
        linkedin_share_url=linkedin_share_url,
        linkedin_share_text=share_text
    )


@router.post("/history/{run_id}/offer", response_model=MarkMilestoneResponse)
def mark_got_offer(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/history/{run_id}/offer
    Mark that user received a job offer for this application
    """
    user_id = current_user["user_id"]
    logger.info(f"Marking offer received: {run_id} for user: {user_id}")

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

    # Check if already marked
    if run.got_offer:
        raise HTTPException(status_code=400, detail="This job has already been marked as offer received")

    # Get the job details
    job = db.query(DBJob).filter(DBJob.id == run.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Associated job not found")

    # Get the user
    user = db.query(DBUser).filter(DBUser.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Mark as offer received
    now = datetime.utcnow()
    run.got_offer = True
    run.offer_at = now

    # Update user stats
    user.offers_count = (user.offers_count or 0) + 1

    # Check for new achievements
    from app.core.achievements import get_user_stats, check_achievements, unlock_achievements, update_streak
    
    # Update streak
    update_streak(db, str(user_uuid))
    
    db.commit()

    # Get updated stats and check achievements
    stats = get_user_stats(db, str(user_uuid))
    newly_unlocked, xp_earned = check_achievements(stats)
    
    new_achievements = []
    if newly_unlocked:
        achievement_ids = [a["id"] for a in newly_unlocked]
        unlock_achievements(db, str(user_uuid), achievement_ids, xp_earned)
        # Convert to response format
        new_achievements = [
            Achievement(
                id=a["id"],
                name=a["name"],
                description=a["description"],
                icon=a["icon"],
                tier=a["tier"].value if hasattr(a["tier"], 'value') else a["tier"],
                xp=a["xp"],
                color=a["color"],
                unlocked=True,
                unlocked_at=now.isoformat(),
                pro_only=a.get("pro_only", False)
            ) for a in newly_unlocked
        ]

    logger.info(f"Offer received! User {user_id} got offer from {job.company} for {job.title}")

    # Generate LinkedIn share content
    share_text = f"🎁 I just received a job offer for {job.title} at {job.company}! Grateful for this opportunity. #JobOffer #CareerWin #Blessed"
    linkedin_share_url = f"https://www.linkedin.com/sharing/share-offsite/?url=https://tailor.umukozihr.com&title={quote(share_text)}"

    return MarkMilestoneResponse(
        success=True,
        company=job.company,
        title=job.title,
        milestone_type="offer",
        marked_at=now.isoformat(),
        total_count=user.offers_count,
        new_achievements=new_achievements,
        xp_earned=xp_earned,
        message=f"Incredible! You received an offer for {job.title} at {job.company}! 🎁",
        linkedin_share_url=linkedin_share_url,
        linkedin_share_text=share_text
    )
