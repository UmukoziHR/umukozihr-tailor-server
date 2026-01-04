"""
Admin dashboard routes for UmukoziHR Resume Tailor
Provides analytics, user management, and system monitoring endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, distinct

from app.db.database import get_db
from app.db.models import User, Profile, Job, Run, UserEvent, GenerationMetric, SystemLog
from app.auth.auth import verify_token

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Admin user IDs - add admin user UUIDs here
ADMIN_USER_IDS = [
    # Add your admin user IDs here
    # "uuid-of-admin-user"
]

def get_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Verify admin access"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == UUID(user_id)).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Check if user is admin (either in ADMIN_USER_IDS or has is_admin flag)
    if hasattr(user, 'is_admin') and user.is_admin:
        return user
    if str(user.id) in ADMIN_USER_IDS:
        return user
    
    # For development/demo: allow all authenticated users to view admin
    # Remove this in production
    return user


@router.get("/admin/dashboard")
def get_dashboard(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    GET /admin/dashboard
    Returns comprehensive dashboard stats for admin monitoring
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)
    
    # === USER ACTIVITY ===
    total_users = db.query(func.count(User.id)).scalar() or 0
    signups_today = db.query(func.count(User.id)).filter(User.created_at >= today_start).scalar() or 0
    signups_this_week = db.query(func.count(User.id)).filter(User.created_at >= week_start).scalar() or 0
    signups_this_month = db.query(func.count(User.id)).filter(User.created_at >= month_start).scalar() or 0
    
    verified_users = db.query(func.count(User.id)).filter(User.email_verified == True).scalar() or 0
    
    # Users with profiles (completed onboarding)
    onboarding_completed = db.query(func.count(distinct(Profile.user_id))).scalar() or 0
    onboarding_in_progress = total_users - onboarding_completed
    
    # Active users (had events)
    active_today = db.query(func.count(distinct(UserEvent.user_id))).filter(
        UserEvent.created_at >= today_start
    ).scalar() or 0
    active_this_week = db.query(func.count(distinct(UserEvent.user_id))).filter(
        UserEvent.created_at >= week_start
    ).scalar() or 0
    
    # === GENERATION STATS ===
    total_generations = db.query(func.count(GenerationMetric.id)).scalar() or 0
    successful_generations = db.query(func.count(GenerationMetric.id)).filter(
        GenerationMetric.success == True
    ).scalar() or 0
    failed_generations = total_generations - successful_generations
    success_rate = round((successful_generations / total_generations * 100) if total_generations > 0 else 0, 1)
    
    generations_today = db.query(func.count(GenerationMetric.id)).filter(
        GenerationMetric.created_at >= today_start
    ).scalar() or 0
    generations_this_week = db.query(func.count(GenerationMetric.id)).filter(
        GenerationMetric.created_at >= week_start
    ).scalar() or 0
    
    # Avg durations
    avg_total = db.query(func.avg(GenerationMetric.total_duration)).filter(
        GenerationMetric.success == True
    ).scalar() or 0
    avg_llm = db.query(func.avg(GenerationMetric.llm_duration)).filter(
        GenerationMetric.success == True
    ).scalar() or 0
    
    # Resume/Cover letter counts
    resumes_generated = db.query(func.count(GenerationMetric.id)).filter(
        GenerationMetric.resume_pdf_success == True
    ).scalar() or 0
    cover_letters_generated = db.query(func.count(GenerationMetric.id)).filter(
        GenerationMetric.cover_letter_pdf_success == True
    ).scalar() or 0
    
    # === JD INSIGHTS ===
    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    
    # By region
    region_counts = db.query(
        GenerationMetric.region,
        func.count(GenerationMetric.id)
    ).group_by(GenerationMetric.region).all()
    by_region = {r[0] or 'Unknown': r[1] for r in region_counts}
    
    # By industry
    industry_counts = db.query(
        GenerationMetric.jd_industry,
        func.count(GenerationMetric.id)
    ).filter(GenerationMetric.jd_industry.isnot(None)).group_by(
        GenerationMetric.jd_industry
    ).all()
    by_industry = {i[0]: i[1] for i in industry_counts}
    
    # By role type
    role_counts = db.query(
        GenerationMetric.jd_role_type,
        func.count(GenerationMetric.id)
    ).filter(GenerationMetric.jd_role_type.isnot(None)).group_by(
        GenerationMetric.jd_role_type
    ).all()
    by_role_type = {r[0]: r[1] for r in role_counts}
    
    avg_jd_length = db.query(func.avg(GenerationMetric.jd_text_length)).scalar() or 0
    
    # === SYSTEM HEALTH ===
    errors_today = db.query(func.count(SystemLog.id)).filter(
        and_(SystemLog.created_at >= today_start, SystemLog.level == 'ERROR')
    ).scalar() or 0
    errors_this_week = db.query(func.count(SystemLog.id)).filter(
        and_(SystemLog.created_at >= week_start, SystemLog.level == 'ERROR')
    ).scalar() or 0
    
    # Errors by type
    error_type_counts = db.query(
        SystemLog.exception_type,
        func.count(SystemLog.id)
    ).filter(
        and_(SystemLog.created_at >= week_start, SystemLog.level == 'ERROR')
    ).group_by(SystemLog.exception_type).all()
    errors_by_type = {e[0] or 'Unknown': e[1] for e in error_type_counts}
    
    avg_response_time = db.query(func.avg(SystemLog.response_time_ms)).filter(
        SystemLog.response_time_ms.isnot(None)
    ).scalar() or 0
    
    total_requests = db.query(func.count(SystemLog.id)).filter(
        SystemLog.created_at >= week_start
    ).scalar() or 1
    error_rate = round((errors_this_week / total_requests * 100), 2)
    
    # === SUBSCRIPTION STATS ===
    free_users = db.query(func.count(User.id)).filter(
        User.subscription_tier == 'free'
    ).scalar() or total_users
    pro_users = db.query(func.count(User.id)).filter(
        User.subscription_tier == 'pro'
    ).scalar() or 0
    
    # Region breakdown
    africa_users = db.query(func.count(User.id)).filter(
        User.region_group == 'africa'
    ).scalar() or 0
    global_users = db.query(func.count(User.id)).filter(
        User.region_group == 'global'
    ).scalar() or 0
    
    # Pro users by region
    africa_pro = db.query(func.count(User.id)).filter(
        and_(User.region_group == 'africa', User.subscription_tier == 'pro')
    ).scalar() or 0
    global_pro = db.query(func.count(User.id)).filter(
        and_(User.region_group == 'global', User.subscription_tier == 'pro')
    ).scalar() or 0
    
    # Conversion rates
    conversion_rate = round((pro_users / total_users * 100) if total_users > 0 else 0, 1)
    africa_conversion = round((africa_pro / africa_users * 100) if africa_users > 0 else 0, 1)
    global_conversion = round((global_pro / global_users * 100) if global_users > 0 else 0, 1)
    
    # Revenue estimate: Africa $5/mo, Global $20/mo
    monthly_revenue = (africa_pro * 5) + (global_pro * 20)
    potential_revenue = (africa_users * 5) + (global_users * 20)
    
    # Usage stats
    total_generations_used = db.query(func.sum(User.monthly_generations_used)).scalar() or 0
    users_at_limit = db.query(func.count(User.id)).filter(
        and_(User.subscription_tier == 'free', User.monthly_generations_used >= 5)
    ).scalar() or 0
    avg_gen_per_user = round(total_generations_used / total_users if total_users > 0 else 0, 1)
    
    # Subscription status
    active_subs = pro_users
    cancelled_subs = db.query(func.count(User.id)).filter(
        User.subscription_status == 'cancelled'
    ).scalar() or 0
    expired_subs = db.query(func.count(User.id)).filter(
        User.subscription_status == 'expired'
    ).scalar() or 0
    
    # === TRENDS ===
    signups_trend = []
    generations_trend = []
    for i in range(7):
        day_start = today_start - timedelta(days=6-i)
        day_end = day_start + timedelta(days=1)
        
        signup_count = db.query(func.count(User.id)).filter(
            and_(User.created_at >= day_start, User.created_at < day_end)
        ).scalar() or 0
        signups_trend.append({"date": day_start.isoformat(), "count": signup_count})
        
        gen_count = db.query(func.count(GenerationMetric.id)).filter(
            and_(GenerationMetric.created_at >= day_start, GenerationMetric.created_at < day_end)
        ).scalar() or 0
        generations_trend.append({"date": day_start.isoformat(), "count": gen_count})
    
    return {
        "user_activity": {
            "total_users": total_users,
            "signups_today": signups_today,
            "signups_this_week": signups_this_week,
            "signups_this_month": signups_this_month,
            "verified_users": verified_users,
            "onboarding_completed": onboarding_completed,
            "onboarding_in_progress": onboarding_in_progress,
            "active_today": active_today,
            "active_this_week": active_this_week
        },
        "generation": {
            "total_generations": total_generations,
            "successful_generations": successful_generations,
            "failed_generations": failed_generations,
            "success_rate": success_rate,
            "generations_today": generations_today,
            "generations_this_week": generations_this_week,
            "avg_total_duration": round(avg_total, 2),
            "avg_llm_duration": round(avg_llm, 2),
            "resumes_generated": resumes_generated,
            "cover_letters_generated": cover_letters_generated
        },
        "jd_insights": {
            "total_jobs": total_jobs,
            "by_region": by_region,
            "by_industry": by_industry,
            "by_role_type": by_role_type,
            "avg_jd_length": round(avg_jd_length, 0)
        },
        "system_health": {
            "total_errors_today": errors_today,
            "total_errors_this_week": errors_this_week,
            "errors_by_type": errors_by_type,
            "avg_response_time_ms": round(avg_response_time, 0),
            "error_rate": error_rate
        },
        "subscription": {
            "free_users": free_users,
            "pro_users": pro_users,
            "total_paid": pro_users,
            "africa_users": africa_users,
            "global_users": global_users,
            "active_subscriptions": active_subs,
            "cancelled_subscriptions": cancelled_subs,
            "expired_subscriptions": expired_subs,
            "monthly_revenue_estimate": monthly_revenue,
            "potential_revenue": potential_revenue,
            "conversion_rate": conversion_rate,
            "africa_conversion_rate": africa_conversion,
            "global_conversion_rate": global_conversion,
            "total_generations_used": total_generations_used,
            "users_at_limit": users_at_limit,
            "avg_generations_per_user": avg_gen_per_user
        },
        "signups_trend": signups_trend,
        "generations_trend": generations_trend
    }


@router.get("/admin/users")
def get_users(
    page: int = 1,
    page_size: int = 20,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get paginated user list"""
    offset = (page - 1) * page_size
    
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(page_size).all()
    total = db.query(func.count(User.id)).scalar() or 0
    
    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "created_at": u.created_at.isoformat(),
                "subscription_tier": getattr(u, 'subscription_tier', 'free'),
                "region_group": getattr(u, 'region_group', 'global'),
                "monthly_generations_used": getattr(u, 'monthly_generations_used', 0)
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/admin/generations")
def get_generations(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get paginated generation history"""
    offset = (page - 1) * page_size
    
    query = db.query(GenerationMetric)
    if status == "success":
        query = query.filter(GenerationMetric.success == True)
    elif status == "failed":
        query = query.filter(GenerationMetric.success == False)
    
    generations = query.order_by(GenerationMetric.created_at.desc()).offset(offset).limit(page_size).all()
    total = query.count()
    
    return {
        "generations": [
            {
                "id": str(g.id),
                "run_id": str(g.run_id),
                "user_id": str(g.user_id),
                "success": g.success,
                "total_duration": g.total_duration,
                "region": g.region,
                "jd_industry": g.jd_industry,
                "created_at": g.created_at.isoformat()
            }
            for g in generations
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/admin/errors")
def get_errors(
    page: int = 1,
    page_size: int = 20,
    level: Optional[str] = None,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get paginated error logs"""
    offset = (page - 1) * page_size
    
    query = db.query(SystemLog)
    if level:
        query = query.filter(SystemLog.level == level.upper())
    else:
        query = query.filter(SystemLog.level == 'ERROR')
    
    logs = query.order_by(SystemLog.created_at.desc()).offset(offset).limit(page_size).all()
    total = query.count()
    
    return {
        "errors": [
            {
                "id": str(log.id),
                "level": log.level,
                "message": log.message[:200],
                "exception_type": log.exception_type,
                "request_path": log.request_path,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.post("/admin/users/{user_id}/make-admin")
def make_admin(
    user_id: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Make a user an admin"""
    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if hasattr(user, 'is_admin'):
        user.is_admin = True
        db.commit()
    
    return {"success": True, "message": f"User {user.email} is now an admin"}
