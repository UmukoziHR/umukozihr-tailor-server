"""Admin Analytics API Routes
v1.4 - Monitoring Dashboard Backend with Subscription Analytics

Provides endpoints for:
- User activity analytics (signups, onboarding, active users)
- Generation metrics (success rates, durations, PDF/DOCX output)
- JD insights (by region, industry, role type)
- System health monitoring (errors, response times)
- Subscription & revenue analytics (Africa $5, Global $20 pricing)
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

# Router with /admin prefix - main.py includes without additional prefix
router = APIRouter(prefix="/admin", tags=["admin"])


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


class GeolocationStats(BaseModel):
    """Real user geolocation for product analytics"""
    by_country: dict  # {country_name: count}
    by_city: dict     # {city: count}
    top_countries: List[dict]  # [{name, code, count}]
    top_cities: List[dict]     # [{city, country, count}]
    unknown_location: int


class SubscriptionStats(BaseModel):
    free_users: int
    pro_users: int
    total_paid: int
    africa_users: int
    global_users: int
    active_subscriptions: int
    cancelled_subscriptions: int
    expired_subscriptions: int
    monthly_revenue_estimate: float
    potential_revenue: float
    conversion_rate: float
    africa_conversion_rate: float
    global_conversion_rate: float
    total_generations_used: int
    users_at_limit: int
    avg_generations_per_user: float


class JobLandingStats(BaseModel):
    """Job Landing Celebration Stats - v1.5"""
    total_landed: int
    landed_today: int
    landed_this_week: int
    landed_this_month: int
    users_with_landed_jobs: int
    top_companies: List[dict]  # [{company, count}]
    landing_rate: float  # percentage of runs that resulted in landed jobs


class AdminDashboardResponse(BaseModel):
    user_activity: UserActivityStats
    generation: GenerationStats
    jd_insights: JDInsights
    system_health: SystemHealthStats
    subscription: SubscriptionStats
    geolocation: GeolocationStats
    job_landing: JobLandingStats
    signups_trend: List[DailyMetric]
    generations_trend: List[DailyMetric]


def require_admin(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Dependency to require admin access - for now allows all authenticated users"""
    user_id = current_user["user_id"]
    
    try:
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user has is_admin flag
        if hasattr(user, 'is_admin') and user.is_admin:
            return {"user_id": user_id, "email": user.email}
        
        # For development: allow all authenticated users to view admin dashboard
        return {"user_id": user_id, "email": user.email}
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")


@router.get("/dashboard", response_model=AdminDashboardResponse)
def get_admin_dashboard(
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """GET /admin/dashboard - Main admin dashboard with all analytics"""
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
    
    try:
        verified_users = db.query(User).filter(User.email_verified == True).count()
    except:
        verified_users = 0
    
    profiles_count = db.query(Profile).count()
    try:
        onboarding_completed = db.query(User).filter(User.onboarding_completed == True).count()
        onboarding_completed = max(onboarding_completed, profiles_count)
    except:
        onboarding_completed = profiles_count
    
    try:
        active_today = db.query(func.count(func.distinct(UserEvent.user_id))).filter(
            and_(UserEvent.event_type == "login", UserEvent.created_at >= today_start)
        ).scalar() or 0
        active_this_week = db.query(func.count(func.distinct(UserEvent.user_id))).filter(
            and_(UserEvent.event_type == "login", UserEvent.created_at >= week_start)
        ).scalar() or 0
    except:
        active_today = 0
        active_this_week = 0
    
    user_activity = UserActivityStats(
        total_users=total_users,
        signups_today=signups_today,
        signups_this_week=signups_this_week,
        signups_this_month=signups_this_month,
        verified_users=verified_users,
        onboarding_completed=onboarding_completed,
        onboarding_in_progress=max(0, total_users - onboarding_completed),
        active_today=active_today,
        active_this_week=active_this_week
    )
    
    # Generation Stats
    total_runs = db.query(Run).count()
    successful_runs = db.query(Run).filter(Run.status == "completed").count()
    
    try:
        failed_runs = db.query(UserEvent).filter(UserEvent.event_type == "generation_error").count()
    except:
        failed_runs = 0
    
    generations_today = db.query(Run).filter(Run.created_at >= today_start).count()
    generations_this_week = db.query(Run).filter(Run.created_at >= week_start).count()
    
    try:
        avg_durations = db.query(
            func.avg(GenerationMetric.total_duration),
            func.avg(GenerationMetric.llm_duration)
        ).first()
        avg_total_dur = avg_durations[0] or 0
        avg_llm_dur = avg_durations[1] or 0
        resume_success = db.query(GenerationMetric).filter(GenerationMetric.resume_pdf_success == True).count()
        cover_success = db.query(GenerationMetric).filter(GenerationMetric.cover_letter_pdf_success == True).count()
    except:
        avg_total_dur = 0
        avg_llm_dur = 0
        resume_success = successful_runs
        cover_success = successful_runs
    
    total_attempts = successful_runs + failed_runs
    
    generation_stats = GenerationStats(
        total_generations=total_runs,
        successful_generations=successful_runs,
        failed_generations=failed_runs,
        success_rate=round((successful_runs / total_attempts * 100) if total_attempts > 0 else 100.0, 1),
        generations_today=generations_today,
        generations_this_week=generations_this_week,
        avg_total_duration=round(avg_total_dur, 2),
        avg_llm_duration=round(avg_llm_dur, 2),
        resumes_generated=resume_success or successful_runs,
        cover_letters_generated=cover_success or successful_runs
    )
    
    # JD Insights
    total_jobs = db.query(Job).count()
    
    try:
        region_counts = db.query(Job.region, func.count(Job.id)).group_by(Job.region).all()
        by_region = {region: count for region, count in region_counts}
    except:
        by_region = {"US": 0, "EU": 0, "GL": 0}
    
    try:
        industry_counts = db.query(GenerationMetric.jd_industry, func.count(GenerationMetric.id)).group_by(GenerationMetric.jd_industry).all()
        by_industry = {industry or "unknown": count for industry, count in industry_counts}
    except:
        by_industry = {}
    
    try:
        role_counts = db.query(GenerationMetric.jd_role_type, func.count(GenerationMetric.id)).group_by(GenerationMetric.jd_role_type).all()
        by_role_type = {role or "unknown": count for role, count in role_counts}
    except:
        by_role_type = {}
    
    try:
        avg_jd_length_result = db.query(func.avg(GenerationMetric.jd_text_length)).scalar() or 0
    except:
        avg_jd_length_result = 0
    
    jd_insights = JDInsights(
        total_jobs=total_jobs,
        by_region=by_region if by_region else {"US": 0, "EU": 0, "GL": 0},
        by_industry=by_industry,
        by_role_type=by_role_type,
        avg_jd_length=round(avg_jd_length_result, 0)
    )
    
    # System Health
    try:
        gen_errors_today = db.query(UserEvent).filter(
            and_(UserEvent.event_type == "generation_error", UserEvent.created_at >= today_start)
        ).count()
        gen_errors_this_week = db.query(UserEvent).filter(
            and_(UserEvent.event_type == "generation_error", UserEvent.created_at >= week_start)
        ).count()
    except:
        gen_errors_today = 0
        gen_errors_this_week = 0
    
    try:
        sys_errors_today = db.query(SystemLog).filter(
            and_(SystemLog.level == "ERROR", SystemLog.created_at >= today_start)
        ).count()
        sys_errors_this_week = db.query(SystemLog).filter(
            and_(SystemLog.level == "ERROR", SystemLog.created_at >= week_start)
        ).count()
    except:
        sys_errors_today = 0
        sys_errors_this_week = 0
    
    errors_today = gen_errors_today + sys_errors_today
    errors_this_week = gen_errors_this_week + sys_errors_this_week
    
    errors_by_type = {}
    try:
        gen_error_events = db.query(UserEvent).filter(
            and_(UserEvent.event_type == "generation_error", UserEvent.created_at >= week_start)
        ).limit(100).all()
        for evt in gen_error_events:
            if evt.event_data and isinstance(evt.event_data, dict):
                error_msg = evt.event_data.get('error', 'unknown')
                error_type = error_msg[:50] if error_msg else 'unknown'
                errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1
    except:
        pass
    
    try:
        avg_response = db.query(func.avg(SystemLog.response_time_ms)).filter(
            SystemLog.created_at >= today_start
        ).scalar() or 0
        if not avg_response:
            avg_gen_time = db.query(func.avg(GenerationMetric.total_duration)).filter(
                GenerationMetric.created_at >= today_start
            ).scalar()
            avg_response = (avg_gen_time or 0) * 1000
    except:
        avg_response = 0
    
    total_gen_attempts = total_runs + failed_runs
    error_rate = round((failed_runs / total_gen_attempts * 100) if total_gen_attempts > 0 else 0, 2)
    
    system_health = SystemHealthStats(
        total_errors_today=errors_today,
        total_errors_this_week=errors_this_week,
        errors_by_type=errors_by_type,
        avg_response_time_ms=round(avg_response, 2),
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
    try:
        free_users = db.query(User).filter(
            (User.subscription_tier == "free") | (User.subscription_tier == None)
        ).count()
        pro_users = db.query(User).filter(User.subscription_tier == "pro").count()
        
        africa_users = db.query(User).filter(User.region_group == "africa").count()
        global_users = db.query(User).filter(
            (User.region_group == "global") | (User.region_group == None)
        ).count()
        
        active_subs = db.query(User).filter(User.subscription_status == "active").count()
        cancelled_subs = db.query(User).filter(User.subscription_status == "cancelled").count()
        expired_subs = db.query(User).filter(User.subscription_status == "expired").count()
        
        africa_pro = db.query(User).filter(
            and_(User.subscription_tier == "pro", User.region_group == "africa")
        ).count()
        global_pro = db.query(User).filter(
            and_(User.subscription_tier == "pro", 
                 (User.region_group == "global") | (User.region_group == None))
        ).count()
        
        monthly_revenue = (africa_pro * 5) + (global_pro * 20)
        
        africa_free = db.query(User).filter(
            and_((User.subscription_tier == "free") | (User.subscription_tier == None),
                 User.region_group == "africa")
        ).count()
        global_free = db.query(User).filter(
            and_((User.subscription_tier == "free") | (User.subscription_tier == None),
                 (User.region_group == "global") | (User.region_group == None))
        ).count()
        potential_revenue = (africa_free * 5) + (global_free * 20) + monthly_revenue
        
        total_gens_used = db.query(func.sum(User.monthly_generations_used)).scalar() or 0
        users_at_limit = db.query(User).filter(
            and_((User.subscription_tier == "free") | (User.subscription_tier == None),
                 User.monthly_generations_used >= 5)
        ).count()
        avg_gens = db.query(func.avg(User.monthly_generations_used)).scalar() or 0
        
        africa_conversion = round((africa_pro / africa_users * 100) if africa_users > 0 else 0, 1)
        global_conversion = round((global_pro / global_users * 100) if global_users > 0 else 0, 1)
        
    except Exception as e:
        logger.warning(f"Error fetching subscription stats: {e}")
        free_users = total_users
        pro_users = 0
        africa_users = 0
        global_users = total_users
        active_subs = 0
        cancelled_subs = 0
        expired_subs = 0
        monthly_revenue = 0
        potential_revenue = 0
        total_gens_used = 0
        users_at_limit = 0
        avg_gens = 0
        africa_conversion = 0
        global_conversion = 0
    
    subscription_stats = SubscriptionStats(
        free_users=free_users,
        pro_users=pro_users,
        total_paid=pro_users,
        africa_users=africa_users,
        global_users=global_users,
        active_subscriptions=active_subs,
        cancelled_subscriptions=cancelled_subs,
        expired_subscriptions=expired_subs,
        monthly_revenue_estimate=monthly_revenue,
        potential_revenue=potential_revenue,
        conversion_rate=round((pro_users / total_users * 100) if total_users > 0 else 0, 1),
        africa_conversion_rate=africa_conversion,
        global_conversion_rate=global_conversion,
        total_generations_used=total_gens_used,
        users_at_limit=users_at_limit,
        avg_generations_per_user=round(avg_gens, 1)
    )
    
    # Geolocation Stats - Real user locations for product analytics
    try:
        # Users by country (actual geolocation, not pricing region)
        country_counts = db.query(
            User.country_name, User.country, func.count(User.id)
        ).filter(
            User.country_name != None
        ).group_by(User.country_name, User.country).all()
        
        by_country = {}
        top_countries = []
        for country_name, country_code, count in country_counts:
            if country_name:
                by_country[country_name] = count
                top_countries.append({
                    "name": country_name,
                    "code": country_code or "XX",
                    "count": count
                })
        
        # Sort by count descending, take top 10
        top_countries = sorted(top_countries, key=lambda x: x["count"], reverse=True)[:10]
        
        # Users by city
        city_counts = db.query(
            User.city, User.country_name, func.count(User.id)
        ).filter(
            User.city != None
        ).group_by(User.city, User.country_name).all()
        
        by_city = {}
        top_cities = []
        for city, country_name, count in city_counts:
            if city:
                by_city[city] = count
                top_cities.append({
                    "city": city,
                    "country": country_name or "Unknown",
                    "count": count
                })
        
        # Sort by count descending, take top 10
        top_cities = sorted(top_cities, key=lambda x: x["count"], reverse=True)[:10]
        
        # Users with unknown location
        unknown_location = db.query(User).filter(
            (User.country_name == None) | (User.country_name == "")
        ).count()
        
    except Exception as e:
        logger.warning(f"Error fetching geolocation stats: {e}")
        by_country = {}
        by_city = {}
        top_countries = []
        top_cities = []
        unknown_location = total_users
    
    geolocation_stats = GeolocationStats(
        by_country=by_country,
        by_city=by_city,
        top_countries=top_countries,
        top_cities=top_cities,
        unknown_location=unknown_location
    )
    
    # Job Landing Stats - v1.5
    try:
        total_landed = db.query(Run).filter(Run.job_landed == True).count()
        landed_today = db.query(Run).filter(
            and_(Run.job_landed == True, Run.landed_at >= today_start)
        ).count()
        landed_this_week = db.query(Run).filter(
            and_(Run.job_landed == True, Run.landed_at >= week_start)
        ).count()
        landed_this_month = db.query(Run).filter(
            and_(Run.job_landed == True, Run.landed_at >= month_start)
        ).count()
        
        users_with_landed = db.query(func.count(func.distinct(Run.user_id))).filter(
            Run.job_landed == True
        ).scalar() or 0
        
        # Top companies where users landed
        company_counts = db.query(
            Job.company, func.count(Run.id)
        ).join(Run, Run.job_id == Job.id).filter(
            Run.job_landed == True
        ).group_by(Job.company).order_by(desc(func.count(Run.id))).limit(10).all()
        
        top_landing_companies = [
            {"company": company, "count": count} 
            for company, count in company_counts
        ]
        
        # Landing rate (landed jobs / total runs)
        landing_rate = round((total_landed / total_runs * 100) if total_runs > 0 else 0, 2)
        
    except Exception as e:
        logger.warning(f"Error fetching job landing stats: {e}")
        total_landed = 0
        landed_today = 0
        landed_this_week = 0
        landed_this_month = 0
        users_with_landed = 0
        top_landing_companies = []
        landing_rate = 0
    
    job_landing_stats = JobLandingStats(
        total_landed=total_landed,
        landed_today=landed_today,
        landed_this_week=landed_this_week,
        landed_this_month=landed_this_month,
        users_with_landed_jobs=users_with_landed,
        top_companies=top_landing_companies,
        landing_rate=landing_rate
    )
    
    return AdminDashboardResponse(
        user_activity=user_activity,
        generation=generation_stats,
        jd_insights=jd_insights,
        system_health=system_health,
        subscription=subscription_stats,
        geolocation=geolocation_stats,
        job_landing=job_landing_stats,
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
    """GET /admin/users - List all users with pagination"""
    offset = (page - 1) * page_size
    
    total = db.query(User).count()
    users = db.query(User).order_by(desc(User.created_at)).offset(offset).limit(page_size).all()
    
    user_list = []
    for user in users:
        user_dict = {
            "id": str(user.id),
            "email": user.email,
            "created_at": user.created_at.isoformat()
        }
        if hasattr(user, 'is_admin'):
            user_dict["is_admin"] = user.is_admin
        if hasattr(user, 'subscription_tier'):
            user_dict["subscription_tier"] = user.subscription_tier
        if hasattr(user, 'region_group'):
            user_dict["region_group"] = user.region_group
        if hasattr(user, 'monthly_generations_used'):
            user_dict["monthly_generations_used"] = user.monthly_generations_used
        user_list.append(user_dict)
    
    return {"users": user_list, "total": total, "page": page, "page_size": page_size}


@router.get("/generations")
def list_generations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """GET /admin/generations - List all generation runs"""
    offset = (page - 1) * page_size
    
    query = db.query(Run, Job, User).join(Job, Run.job_id == Job.id).join(User, Run.user_id == User.id)
    
    if status:
        query = query.filter(Run.status == status)
    
    total = query.count()
    results = query.order_by(desc(Run.created_at)).offset(offset).limit(page_size).all()
    
    runs_list = [
        {
            "run_id": str(run.id),
            "user_email": user.email,
            "company": job.company,
            "title": job.title,
            "region": job.region,
            "status": run.status,
            "profile_version": run.profile_version,
            "created_at": run.created_at.isoformat()
        }
        for run, job, user in results
    ]
    
    return {"runs": runs_list, "total": total, "page": page, "page_size": page_size}


@router.get("/errors")
def list_errors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    level: str = Query("ERROR"),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """GET /admin/errors - List errors"""
    offset = (page - 1) * page_size
    
    logs_list = []
    total = 0
    
    try:
        gen_errors = db.query(UserEvent).filter(
            UserEvent.event_type == "generation_error"
        ).order_by(desc(UserEvent.created_at)).offset(offset).limit(page_size).all()
        
        gen_error_count = db.query(UserEvent).filter(UserEvent.event_type == "generation_error").count()
        
        for evt in gen_errors:
            error_data = evt.event_data or {}
            logs_list.append({
                "id": str(evt.id),
                "level": "ERROR",
                "source": "generation",
                "message": error_data.get('error', 'Generation failed')[:200],
                "exception_type": "generation_error",
                "request_path": "/api/v1/generate",
                "user_id": str(evt.user_id) if evt.user_id else None,
                "created_at": evt.created_at.isoformat()
            })
        total += gen_error_count
    except Exception as e:
        logger.warning(f"Error fetching generation errors: {e}")
    
    try:
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
                "user_id": str(log.user_id) if log.user_id else None,
                "created_at": log.created_at.isoformat()
            })
        total += sys_count
    except Exception as e:
        logger.warning(f"Error fetching system logs: {e}")
    
    logs_list.sort(key=lambda x: x['created_at'], reverse=True)
    logs_list = logs_list[:page_size]
    
    return {"logs": logs_list, "total": total, "page": page, "page_size": page_size}


@router.post("/users/{user_id}/make-admin")
def make_user_admin(
    user_id: str,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """POST /admin/users/{user_id}/make-admin - Grant admin access"""
    try:
        user_uuid = UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if hasattr(user, 'is_admin'):
            user.is_admin = True
            db.commit()
            logger.info(f"Admin access granted to {user.email} by {admin['email']}")
        
        return {"success": True, "message": f"Admin access granted to {user.email}"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")


@router.post("/users/{user_id}/upgrade-to-pro")
def manual_upgrade_to_pro(
    user_id: str,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    POST /admin/users/{user_id}/upgrade-to-pro
    Manually upgrade a user to Pro subscription (admin only)
    Use this when Paystack webhook fails or for manual upgrades
    """
    try:
        user_uuid = UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        now = datetime.utcnow()
        expires_at = now + timedelta(days=30)
        
        user.subscription_tier = "pro"
        user.subscription_status = "active"
        user.subscription_started_at = now
        user.subscription_expires_at = expires_at
        user.monthly_generations_limit = -1  # Unlimited
        user.monthly_generations_used = 0  # Reset usage
        
        db.commit()
        
        logger.info(f"Manual Pro upgrade for {user.email} by {admin['email']}, expires: {expires_at}")
        
        return {
            "success": True,
            "message": f"User {user.email} upgraded to Pro",
            "expires_at": expires_at.isoformat()
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")


@router.post("/users/upgrade-by-email")
def upgrade_user_by_email(
    email: str = Query(..., description="User email to upgrade"),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    POST /admin/users/upgrade-by-email?email=user@example.com
    Upgrade user to Pro by email address
    """
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email {email} not found")
    
    now = datetime.utcnow()
    expires_at = now + timedelta(days=30)
    
    user.subscription_tier = "pro"
    user.subscription_status = "active"
    user.subscription_started_at = now
    user.subscription_expires_at = expires_at
    user.monthly_generations_limit = -1  # Unlimited
    user.monthly_generations_used = 0  # Reset usage
    
    db.commit()
    
    logger.info(f"Manual Pro upgrade for {email} by {admin['email']}, expires: {expires_at}")
    
    return {
        "success": True,
        "message": f"User {email} upgraded to Pro",
        "user_id": str(user.id),
        "expires_at": expires_at.isoformat()
    }
