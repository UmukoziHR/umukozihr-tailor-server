"""
Email Scheduler for UmukoziHR Resume Tailor
Scheduled jobs for automated engagement emails using APScheduler

Jobs:
- check_inactive_users: Every 6 hours - 48h inactivity nudge
- check_onboarding_incomplete: Every 12 hours - 24h onboarding nudge
- send_weekly_digest: Monday 9am UTC - Weekly progress recap
- check_winback_users: Daily - 7-day win-back emails
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import User, Profile, Run

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


def get_db() -> Session:
    """Get database session for scheduled jobs"""
    db = SessionLocal()
    try:
        return db
    except:
        db.close()
        raise


def should_send_email(user: User, min_hours_between: int = 24) -> bool:
    """Check if we should send an email to this user (rate limiting)"""
    if user.unsubscribed:
        return False
    
    if user.last_email_sent_at:
        hours_since = (datetime.utcnow() - user.last_email_sent_at).total_seconds() / 3600
        if hours_since < min_hours_between:
            return False
    
    return True


def mark_email_sent(db: Session, user: User):
    """Mark that we sent an email to this user"""
    user.last_email_sent_at = datetime.utcnow()
    db.commit()


# =============================================================================
# SCHEDULED JOBS
# =============================================================================

async def check_inactive_users():
    """
    Check for users inactive for 48 hours and send nudge email.
    Runs every 6 hours.
    """
    logger.info("Running check_inactive_users job...")
    db = get_db()
    
    try:
        # Import here to avoid circular imports
        from app.core.email_service import send_inactivity_48h_email
        
        now = datetime.utcnow()
        inactive_threshold = now - timedelta(hours=48)
        recent_threshold = now - timedelta(hours=72)  # Don't email if inactive > 72h (use winback instead)
        
        # Find users who:
        # 1. Last login was 48-72 hours ago
        # 2. Have not been emailed in 24 hours
        # 3. Have completed onboarding
        # 4. Are not unsubscribed
        inactive_users = db.query(User).filter(
            and_(
                User.last_login_at <= inactive_threshold,
                User.last_login_at > recent_threshold,
                User.onboarding_completed == True,
                User.unsubscribed == False,
                or_(
                    User.last_email_sent_at == None,
                    User.last_email_sent_at < now - timedelta(hours=24)
                )
            )
        ).limit(50).all()  # Process in batches
        
        sent_count = 0
        for user in inactive_users:
            # Get profile completeness
            profile = db.query(Profile).filter(Profile.user_id == user.id).first()
            completeness = int(profile.completeness * 100) if profile and profile.completeness else 50
            
            # Get user name from profile
            name = "there"
            if profile and profile.profile_data:
                name = profile.profile_data.get("name", "there")
            
            result = send_inactivity_48h_email(
                email=user.email,
                name=name,
                user_id=str(user.id),
                completeness=completeness
            )
            
            if result:
                mark_email_sent(db, user)
                sent_count += 1
        
        logger.info(f"Sent {sent_count} inactivity nudge emails")
        
    except Exception as e:
        logger.error(f"Error in check_inactive_users: {e}")
    finally:
        db.close()


async def check_onboarding_incomplete():
    """
    Check for users who signed up 24+ hours ago but haven't completed onboarding.
    Runs every 12 hours.
    """
    logger.info("Running check_onboarding_incomplete job...")
    db = get_db()
    
    try:
        from app.core.email_service import send_onboarding_nudge_email
        
        now = datetime.utcnow()
        signup_threshold = now - timedelta(hours=24)
        max_age_threshold = now - timedelta(hours=72)  # Don't nudge if > 3 days old
        
        # Find users who:
        # 1. Signed up 24-72 hours ago
        # 2. Haven't completed onboarding
        # 3. Haven't been emailed in 24 hours
        incomplete_users = db.query(User).filter(
            and_(
                User.created_at <= signup_threshold,
                User.created_at > max_age_threshold,
                User.onboarding_completed == False,
                User.unsubscribed == False,
                or_(
                    User.last_email_sent_at == None,
                    User.last_email_sent_at < now - timedelta(hours=24)
                )
            )
        ).limit(50).all()
        
        sent_count = 0
        for user in incomplete_users:
            # Calculate rough completeness based on onboarding step
            completeness = min(user.onboarding_step * 20, 80)  # 0-80% based on steps
            
            # Extract name from email as fallback
            name = user.email.split("@")[0].replace(".", " ").title()
            
            result = send_onboarding_nudge_email(
                email=user.email,
                name=name,
                user_id=str(user.id),
                completeness=completeness
            )
            
            if result:
                mark_email_sent(db, user)
                sent_count += 1
        
        logger.info(f"Sent {sent_count} onboarding nudge emails")
        
    except Exception as e:
        logger.error(f"Error in check_onboarding_incomplete: {e}")
    finally:
        db.close()


async def check_winback_users():
    """
    Check for users inactive for 7+ days and send win-back email.
    Runs daily at 10am UTC.
    """
    logger.info("Running check_winback_users job...")
    db = get_db()
    
    try:
        from app.core.email_service import send_winback_7day_email
        
        now = datetime.utcnow()
        inactive_threshold = now - timedelta(days=7)
        max_inactive_threshold = now - timedelta(days=30)  # Don't email if > 30 days
        
        # Find users who:
        # 1. Last login was 7-30 days ago
        # 2. Haven't been emailed in 7 days
        # 3. Not unsubscribed
        winback_users = db.query(User).filter(
            and_(
                User.last_login_at <= inactive_threshold,
                User.last_login_at > max_inactive_threshold,
                User.unsubscribed == False,
                or_(
                    User.last_email_sent_at == None,
                    User.last_email_sent_at < now - timedelta(days=7)
                )
            )
        ).limit(30).all()
        
        sent_count = 0
        for user in winback_users:
            # Count their generations
            generations = db.query(Run).filter(Run.user_id == user.id).count()
            
            # Get name from profile
            profile = db.query(Profile).filter(Profile.user_id == user.id).first()
            name = "there"
            if profile and profile.profile_data:
                name = profile.profile_data.get("name", "there")
            
            result = send_winback_7day_email(
                email=user.email,
                name=name,
                user_id=str(user.id),
                generations=generations
            )
            
            if result:
                mark_email_sent(db, user)
                sent_count += 1
        
        logger.info(f"Sent {sent_count} win-back emails")
        
    except Exception as e:
        logger.error(f"Error in check_winback_users: {e}")
    finally:
        db.close()


async def send_weekly_digest():
    """
    Send weekly digest to all active users.
    Runs Monday at 9am UTC.
    """
    logger.info("Running send_weekly_digest job...")
    db = get_db()
    
    try:
        from app.core.email_service import send_weekly_digest_email
        
        now = datetime.utcnow()
        week_start = now - timedelta(days=7)
        
        # Get users who want digest emails
        # Include users who were active in last 30 days
        active_threshold = now - timedelta(days=30)
        
        digest_users = db.query(User).filter(
            and_(
                User.unsubscribed == False,
                User.onboarding_completed == True,
                or_(
                    User.last_login_at >= active_threshold,
                    User.created_at >= active_threshold
                )
            )
        ).all()
        
        sent_count = 0
        for user in digest_users:
            # Check email preferences
            prefs = user.email_preferences or {}
            if not prefs.get("digest", True):
                continue
            
            # Count generations this week
            generations_this_week = db.query(Run).filter(
                and_(
                    Run.user_id == user.id,
                    Run.created_at >= week_start
                )
            ).count()
            
            # Get name from profile
            profile = db.query(Profile).filter(Profile.user_id == user.id).first()
            name = "there"
            if profile and profile.profile_data:
                name = profile.profile_data.get("name", "there")
            
            # Get achievements unlocked this week
            new_achievements = []  # Could track this if we store achievement dates
            
            result = send_weekly_digest_email(
                email=user.email,
                name=name,
                user_id=str(user.id),
                generations_this_week=generations_this_week,
                streak=user.current_streak_days or 0,
                xp=user.total_xp or 0,
                new_achievements=new_achievements
            )
            
            if result:
                mark_email_sent(db, user)
                sent_count += 1
        
        logger.info(f"Sent {sent_count} weekly digest emails")
        
    except Exception as e:
        logger.error(f"Error in send_weekly_digest: {e}")
    finally:
        db.close()


# =============================================================================
# SCHEDULER MANAGEMENT
# =============================================================================

def init_scheduler() -> AsyncIOScheduler:
    """Initialize and configure the scheduler"""
    global scheduler
    
    scheduler = AsyncIOScheduler()
    
    # Add jobs
    # 1. Check inactive users every 6 hours
    scheduler.add_job(
        check_inactive_users,
        IntervalTrigger(hours=6),
        id="check_inactive_users",
        name="Check 48h inactive users",
        replace_existing=True
    )
    
    # 2. Check incomplete onboarding every 12 hours
    scheduler.add_job(
        check_onboarding_incomplete,
        IntervalTrigger(hours=12),
        id="check_onboarding_incomplete",
        name="Check incomplete onboarding",
        replace_existing=True
    )
    
    # 3. Win-back emails daily at 10am UTC
    scheduler.add_job(
        check_winback_users,
        CronTrigger(hour=10, minute=0),
        id="check_winback_users",
        name="Check 7-day inactive users",
        replace_existing=True
    )
    
    # 4. Weekly digest Monday 9am UTC
    scheduler.add_job(
        send_weekly_digest,
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="send_weekly_digest",
        name="Send weekly digest",
        replace_existing=True
    )
    
    logger.info("Email scheduler initialized with 4 jobs")
    return scheduler


def start_scheduler():
    """Start the scheduler"""
    global scheduler
    
    if scheduler is None:
        scheduler = init_scheduler()
    
    if not scheduler.running:
        scheduler.start()
        logger.info("Email scheduler started")


def stop_scheduler():
    """Stop the scheduler"""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Email scheduler stopped")


def get_scheduler_status() -> dict:
    """Get scheduler status and job info"""
    global scheduler
    
    if scheduler is None:
        return {"status": "not_initialized", "jobs": []}
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None
        })
    
    return {
        "status": "running" if scheduler.running else "stopped",
        "jobs": jobs
    }
