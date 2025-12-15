"""
Admin Analytics API Routes
v1.3 Final - Monitoring Dashboard Backend

Provides endpoints for:
- User activity analytics
- Generation metrics
- JD insights
- System health monitoring
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from pydantic import BaseModel
from uuid import UUID

from app.db.database import get_db
from app.db.models import User, Profile, Job, Run, UserEvent, GenerationMetric, SystemLog
from app.auth.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# Response Models
class UserActivityStats(BaseModel):
    total_users: int
    signups_today: int
    signups_this_week: int
    signups_this_month: int
    verified_users: int
    onboarding_completed: int
    onboarding_in_progress: int
    active_today: int
    active_this_week: int
    by_country: dict  # Country breakdown with counts


class GenerationStats(BaseModel):
    total_generations: int
    successful_generations: int
    failed_generations: int
    success_rate: float
    generations_today: int
    generations_this_week: int
    avg_total_duration: float
    avg_llm_duration: float
    resumes_generated: int
    cover_letters_generated: int


class JDInsights(BaseModel):
    total_jobs: int
    by_region: dict
    by_industry: dict
    by_role_type: dict
    avg_jd_length: float


class SystemHealthStats(BaseModel):
    total_errors_today: int
    total_errors_this_week: int
    errors_by_type: dict
    avg_response_time_ms: float
    error_rate: float


class DailyMetric(BaseModel):
    date: str
    count: int


class SubscriptionStats(BaseModel):
    free_users: int
    basic_users: int
    pro_users: int
    enterprise_users: int
    trial_users: int
    total_paid: int
    monthly_revenue_estimate: float  # Based on tier counts
    conversion_rate: float  # paid / total %


class AdminDashboardResponse(BaseModel):
    user_activity: UserActivityStats
    generation: GenerationStats
    jd_insights: JDInsights
    system_health: SystemHealthStats
    subscription: SubscriptionStats
    signups_trend: List[DailyMetric]
    generations_trend: List[DailyMetric]


def require_admin(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Dependency to require admin access"""
    user_id = current_user["user_id"]
    
    try:
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        return {"user_id": user_id, "email": user.email}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")


def get_users_by_country(db: Session) -> dict:
    """Get user count breakdown by country"""
    country_counts = db.query(
        User.country_name, 
        User.country,
        func.count(User.id)
    ).group_by(User.country_name, User.country).all()
    
    result = {}
    for country_name, country_code, count in country_counts:
        if country_name:
            result[country_name] = {
                "code": country_code,
                "count": count
            }
        elif country_code:
            result[country_code] = {
                "code": country_code,
                "count": count
            }
        else:
            result["Unknown"] = result.get("Unknown", {"code": None, "count": 0})
            result["Unknown"]["count"] += count
    
    return result


@router.get("/dashboard", response_model=AdminDashboardResponse)
def get_admin_dashboard(
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/admin/dashboard
    Main admin dashboard with all analytics
    """
    logger.info(f"Admin dashboard accessed by: {admin['email']}")
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)
    
    # User Activity Stats
    total_users = db.query(User).count()
    signups_today = db.query(User).filter(User.created_at >= today_start).count()
    signups_this_week = db.query(User).filter(User.created_at >= week_start).count()
    signups_this_month = db.query(User).filter(User.created_at >= month_start).count()
    
    verified_users = db.query(User).filter(User.is_verified == True).count()
    onboarding_completed = db.query(User).filter(User.onboarding_completed == True).count()
    
    # Users with profiles (alternative for onboarding completion if flag not set)
    profiles_count = db.query(Profile).count()
    
    # Active users (had login events)
    active_today = db.query(UserEvent).filter(
        and_(UserEvent.event_type == "login", UserEvent.created_at >= today_start)
    ).distinct(UserEvent.user_id).count()
    
    active_this_week = db.query(UserEvent).filter(
        and_(UserEvent.event_type == "login", UserEvent.created_at >= week_start)
    ).distinct(UserEvent.user_id).count()
    
    user_activity = UserActivityStats(
        total_users=total_users,
        signups_today=signups_today,
        signups_this_week=signups_this_week,
        signups_this_month=signups_this_month,
        verified_users=verified_users,
        onboarding_completed=max(onboarding_completed, profiles_count),
        onboarding_in_progress=total_users - max(onboarding_completed, profiles_count),
        active_today=active_today,
        active_this_week=active_this_week,
        by_country=get_users_by_country(db)
    )
    
    # Generation Stats
    total_runs = db.query(Run).count()
    successful_runs = db.query(Run).filter(Run.status == "completed").count()
    
    # Count failed generations from UserEvent table (GENERATION_ERROR events)
    # Since failed generations don't create Run records, we count error events instead
    failed_runs = db.query(UserEvent).filter(UserEvent.event_type == "generation_error").count()
    failed_today = db.query(UserEvent).filter(
        and_(UserEvent.event_type == "generation_error", UserEvent.created_at >= today_start)
    ).count()
    failed_this_week = db.query(UserEvent).filter(
        and_(UserEvent.event_type == "generation_error", UserEvent.created_at >= week_start)
    ).count()
    
    generations_today = db.query(Run).filter(Run.created_at >= today_start).count()
    generations_this_week = db.query(Run).filter(Run.created_at >= week_start).count()
    
    # Metrics from GenerationMetric table
    avg_durations = db.query(
        func.avg(GenerationMetric.total_duration),
        func.avg(GenerationMetric.llm_duration)
    ).first()
    
    resume_success = db.query(GenerationMetric).filter(GenerationMetric.resume_pdf_success == True).count()
    cover_success = db.query(GenerationMetric).filter(GenerationMetric.cover_letter_pdf_success == True).count()
    
    generation_stats = GenerationStats(
        total_generations=total_runs,
        successful_generations=successful_runs,
        failed_generations=failed_runs,
        success_rate=round((successful_runs / total_runs * 100) if total_runs > 0 else 0, 1),
        generations_today=generations_today,
        generations_this_week=generations_this_week,
        avg_total_duration=round(avg_durations[0] or 0, 2),
        avg_llm_duration=round(avg_durations[1] or 0, 2),
        resumes_generated=resume_success or successful_runs,
        cover_letters_generated=cover_success or successful_runs
    )
    
    # JD Insights
    total_jobs = db.query(Job).count()
    
    region_counts = db.query(Job.region, func.count(Job.id)).group_by(Job.region).all()
    by_region = {region: count for region, count in region_counts}
    
    industry_counts = db.query(GenerationMetric.jd_industry, func.count(GenerationMetric.id)).group_by(GenerationMetric.jd_industry).all()
    by_industry = {industry or "unknown": count for industry, count in industry_counts}
    
    role_counts = db.query(GenerationMetric.jd_role_type, func.count(GenerationMetric.id)).group_by(GenerationMetric.jd_role_type).all()
    by_role_type = {role or "unknown": count for role, count in role_counts}
    
    avg_jd_length_result = db.query(func.avg(GenerationMetric.jd_text_length)).scalar()
    
    jd_insights = JDInsights(
        total_jobs=total_jobs,
        by_region=by_region if by_region else {"US": 0, "EU": 0, "GL": 0},
        by_industry=by_industry if by_industry else {},
        by_role_type=by_role_type if by_role_type else {},
        avg_jd_length=round(avg_jd_length_result or 0, 0)
    )
    
    # System Health - Use UserEvent for generation errors + SystemLog for system errors
    # Generation errors from UserEvent
    gen_errors_today = db.query(UserEvent).filter(
        and_(UserEvent.event_type == "generation_error", UserEvent.created_at >= today_start)
    ).count()
    
    gen_errors_this_week = db.query(UserEvent).filter(
        and_(UserEvent.event_type == "generation_error", UserEvent.created_at >= week_start)
    ).count()
    
    # Also check SystemLog for any logged system errors
    sys_errors_today = db.query(SystemLog).filter(
        and_(SystemLog.level == "ERROR", SystemLog.created_at >= today_start)
    ).count()
    
    sys_errors_this_week = db.query(SystemLog).filter(
        and_(SystemLog.level == "ERROR", SystemLog.created_at >= week_start)
    ).count()
    
    # Combine both sources
    errors_today = gen_errors_today + sys_errors_today
    errors_this_week = gen_errors_this_week + sys_errors_this_week
    
    # Get error details from generation errors (most common source)
    gen_error_events = db.query(UserEvent).filter(
        and_(UserEvent.event_type == "generation_error", UserEvent.created_at >= week_start)
    ).all()
    
    errors_by_type = {}
    for evt in gen_error_events:
        if evt.event_data and isinstance(evt.event_data, dict):
            error_msg = evt.event_data.get('error', 'unknown')
            # Extract error type from message (first 50 chars)
            error_type = error_msg[:50] if error_msg else 'unknown'
            errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1
    
    # Also add system log error types if any
    system_error_types = db.query(SystemLog.exception_type, func.count(SystemLog.id)).filter(
        and_(SystemLog.level == "ERROR", SystemLog.created_at >= week_start)
    ).group_by(SystemLog.exception_type).all()
    
    for etype, count in system_error_types:
        errors_by_type[etype or "system_error"] = errors_by_type.get(etype or "system_error", 0) + count
    
    # Response time from SystemLog (if populated), otherwise estimate from GenerationMetric
    avg_response = db.query(func.avg(SystemLog.response_time_ms)).filter(
        SystemLog.created_at >= today_start
    ).scalar()
    
    if not avg_response:
        # Fallback: use average generation duration as a proxy
        avg_gen_time = db.query(func.avg(GenerationMetric.total_duration)).filter(
            GenerationMetric.created_at >= today_start
        ).scalar()
        avg_response = (avg_gen_time or 0) * 1000  # Convert to ms
    
    # Calculate error rate: errors / total generation attempts
    total_gen_attempts = total_runs + failed_runs
    error_rate = round((failed_runs / total_gen_attempts * 100) if total_gen_attempts > 0 else 0, 2)
    
    system_health = SystemHealthStats(
        total_errors_today=errors_today,
        total_errors_this_week=errors_this_week,
        errors_by_type=errors_by_type if errors_by_type else {},
        avg_response_time_ms=round(avg_response or 0, 2),
        error_rate=error_rate
    )
    
    # Trends (last 7 days)
    signups_trend = []
    generations_trend = []
    
    for i in range(7):
        day = today_start - timedelta(days=i)
        next_day = day + timedelta(days=1)
        
        signup_count = db.query(User).filter(
            and_(User.created_at >= day, User.created_at < next_day)
        ).count()
        signups_trend.append(DailyMetric(date=day.strftime("%Y-%m-%d"), count=signup_count))
        
        gen_count = db.query(Run).filter(
            and_(Run.created_at >= day, Run.created_at < next_day)
        ).count()
        generations_trend.append(DailyMetric(date=day.strftime("%Y-%m-%d"), count=gen_count))
    
    signups_trend.reverse()
    generations_trend.reverse()
    
    # Subscription Stats
    # Count users by tier (with fallback if column doesn't exist yet)
    try:
        free_users = db.query(User).filter(User.subscription_tier == "free").count()
        basic_users = db.query(User).filter(User.subscription_tier == "basic").count()
        pro_users = db.query(User).filter(User.subscription_tier == "pro").count()
        enterprise_users = db.query(User).filter(User.subscription_tier == "enterprise").count()
        trial_users = db.query(User).filter(User.subscription_status == "trial").count()
    except Exception:
        # Fallback if subscription columns don't exist yet
        free_users = total_users
        basic_users = 0
        pro_users = 0
        enterprise_users = 0
        trial_users = 0
    
    total_paid = basic_users + pro_users + enterprise_users
    
    # Revenue estimate (example pricing: basic=$9, pro=$29, enterprise=$99)
    monthly_revenue = (basic_users * 9) + (pro_users * 29) + (enterprise_users * 99)
    
    subscription_stats = SubscriptionStats(
        free_users=free_users or total_users,  # If no subscription data, all are free
        basic_users=basic_users,
        pro_users=pro_users,
        enterprise_users=enterprise_users,
        trial_users=trial_users,
        total_paid=total_paid,
        monthly_revenue_estimate=monthly_revenue,
        conversion_rate=round((total_paid / total_users * 100) if total_users > 0 else 0, 1)
    )
    
    return AdminDashboardResponse(
        user_activity=user_activity,
        generation=generation_stats,
        jd_insights=jd_insights,
        system_health=system_health,
        subscription=subscription_stats,
        signups_trend=signups_trend,
        generations_trend=generations_trend
    )


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/admin/users
    List all users with pagination
    """
    offset = (page - 1) * page_size
    
    total = db.query(User).count()
    users = db.query(User).order_by(desc(User.created_at)).offset(offset).limit(page_size).all()
    
    # Get profile status for each user
    user_profiles = {str(p.user_id): p for p in db.query(Profile).all()}
    
    user_list = []
    for user in users:
        profile = user_profiles.get(str(user.id))
        user_list.append({
            "id": str(user.id),
            "email": user.email,
            "is_admin": user.is_admin,
            "is_verified": user.is_verified,
            "onboarding_completed": user.onboarding_completed,
            "has_profile": profile is not None,
            "profile_completeness": profile.completeness if profile else 0,
            "created_at": user.created_at.isoformat()
        })
    
    return {
        "users": user_list,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/generations")
def list_generations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/admin/generations
    List all generation runs with pagination
    """
    offset = (page - 1) * page_size
    
    query = db.query(Run, Job, User).join(Job, Run.job_id == Job.id).join(User, Run.user_id == User.id)
    
    if status:
        query = query.filter(Run.status == status)
    
    total = query.count()
    results = query.order_by(desc(Run.created_at)).offset(offset).limit(page_size).all()
    
    runs_list = []
    for run, job, user in results:
        runs_list.append({
            "run_id": str(run.id),
            "user_email": user.email,
            "company": job.company,
            "title": job.title,
            "region": job.region,
            "status": run.status,
            "profile_version": run.profile_version,
            "created_at": run.created_at.isoformat()
        })
    
    return {
        "runs": runs_list,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/errors")
def list_errors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    level: str = Query("ERROR"),
    source: str = Query("all", description="Filter by source: 'all', 'generation', 'system'"),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/admin/errors
    List errors from both generation_error events and system logs
    """
    offset = (page - 1) * page_size
    
    logs_list = []
    total = 0
    
    # Get generation errors from UserEvent
    if source in ["all", "generation"]:
        gen_errors = db.query(UserEvent).filter(
            UserEvent.event_type == "generation_error"
        ).order_by(desc(UserEvent.created_at)).offset(offset).limit(page_size).all()
        
        gen_error_count = db.query(UserEvent).filter(
            UserEvent.event_type == "generation_error"
        ).count()
        
        for evt in gen_errors:
            error_data = evt.event_data or {}
            logs_list.append({
                "id": str(evt.id),
                "level": "ERROR",
                "source": "generation",
                "message": error_data.get('error', 'Generation failed')[:200],
                "exception_type": "generation_error",
                "request_path": "/api/v1/generate",
                "request_method": "POST",
                "status_code": 400,
                "user_id": str(evt.user_id) if evt.user_id else None,
                "details": {
                    "company": error_data.get('company'),
                    "job_title": error_data.get('job_title')
                },
                "created_at": evt.created_at.isoformat()
            })
        
        total += gen_error_count
    
    # Get system errors from SystemLog
    if source in ["all", "system"]:
        query = db.query(SystemLog).filter(SystemLog.level == level)
        sys_count = query.count()
        logs = query.order_by(desc(SystemLog.created_at)).offset(offset).limit(page_size).all()
        
        for log in logs:
            logs_list.append({
                "id": str(log.id),
                "level": log.level,
                "source": "system",
                "message": log.message[:200] if log.message else "System error",
                "exception_type": log.exception_type,
                "request_path": log.request_path,
                "request_method": log.request_method,
                "status_code": log.status_code,
                "user_id": str(log.user_id) if log.user_id else None,
                "details": None,
                "created_at": log.created_at.isoformat()
            })
        
        total += sys_count
    
    # Sort combined list by created_at descending
    logs_list.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Apply pagination to combined list
    logs_list = logs_list[:page_size]
    
    return {
        "logs": logs_list,
        "total": total,
        "page": page,
        "page_size": page_size,
        "sources": {
            "generation_errors": db.query(UserEvent).filter(UserEvent.event_type == "generation_error").count(),
            "system_errors": db.query(SystemLog).filter(SystemLog.level == "ERROR").count()
        }
    }


@router.post("/users/{user_id}/make-admin")
def make_user_admin(
    user_id: str,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/admin/users/{user_id}/make-admin
    Grant admin access to a user
    """
    try:
        user_uuid = UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.is_admin = True
        db.commit()
        
        logger.info(f"Admin access granted to {user.email} by {admin['email']}")
        
        return {"success": True, "message": f"Admin access granted to {user.email}"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
