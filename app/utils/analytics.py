"""
Analytics utilities for event tracking and metrics collection
v1.3 Final - Admin Monitoring System
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import Request

from app.db.models import UserEvent, GenerationMetric, SystemLog

logger = logging.getLogger(__name__)


# Event Types (for consistency)
class EventType:
    # User lifecycle
    SIGNUP = "signup"
    LOGIN = "login"
    LOGOUT = "logout"
    
    # Onboarding
    ONBOARDING_START = "onboarding_start"
    ONBOARDING_STEP = "onboarding_step"
    ONBOARDING_COMPLETE = "onboarding_complete"
    ONBOARDING_SKIP = "onboarding_skip"
    
    # Profile
    PROFILE_UPDATE = "profile_update"
    PROFILE_VIEW = "profile_view"
    
    # Generation
    GENERATION_START = "generation_start"
    GENERATION_COMPLETE = "generation_complete"
    GENERATION_ERROR = "generation_error"
    
    # Downloads
    DOWNLOAD_PDF = "download_pdf"
    DOWNLOAD_TEX = "download_tex"
    DOWNLOAD_ZIP = "download_zip"
    
    # Admin
    ADMIN_LOGIN = "admin_login"


def track_event(
    db: Session,
    event_type: str,
    user_id: Optional[str] = None,
    event_data: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
) -> Optional[UserEvent]:
    """
    Track a user event in the database
    
    Args:
        db: Database session
        event_type: Type of event (use EventType constants)
        user_id: Optional user ID (string or UUID)
        event_data: Optional JSON data for the event
        request: Optional FastAPI request for IP/user agent extraction
    """
    try:
        # Extract request info
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "")[:500]  # Truncate
        
        # Convert user_id to UUID if provided
        user_uuid = None
        if user_id:
            try:
                user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
            except ValueError:
                logger.warning(f"Invalid user_id format for event tracking: {user_id}")
        
        event = UserEvent(
            user_id=user_uuid,
            event_type=event_type,
            event_data=event_data,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow()
        )
        
        db.add(event)
        db.commit()
        
        logger.debug(f"Event tracked: {event_type} for user {user_id}")
        return event
        
    except Exception as e:
        logger.error(f"Failed to track event {event_type}: {e}")
        db.rollback()
        return None


def track_generation_metric(
    db: Session,
    run_id: str,
    user_id: str,
    total_duration: float,
    llm_duration: float,
    tex_render_duration: float,
    pdf_compile_duration: float,
    success: bool,
    region: str,
    resume_pdf_success: bool,
    cover_letter_pdf_success: bool,
    jd_text_length: int,
    keywords_matched_count: int = 0,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    jd_industry: Optional[str] = None,
    jd_role_type: Optional[str] = None
) -> Optional[GenerationMetric]:
    """
    Track generation performance metrics
    """
    try:
        metric = GenerationMetric(
            run_id=UUID(run_id) if isinstance(run_id, str) else run_id,
            user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
            total_duration=total_duration,
            llm_duration=llm_duration,
            tex_render_duration=tex_render_duration,
            pdf_compile_duration=pdf_compile_duration,
            success=success,
            error_type=error_type,
            error_message=error_message,
            jd_text_length=jd_text_length,
            jd_industry=jd_industry,
            jd_role_type=jd_role_type,
            region=region,
            resume_pdf_success=resume_pdf_success,
            cover_letter_pdf_success=cover_letter_pdf_success,
            keywords_matched_count=keywords_matched_count,
            created_at=datetime.utcnow()
        )
        
        db.add(metric)
        db.commit()
        
        logger.debug(f"Generation metric tracked: run_id={run_id}, success={success}")
        return metric
        
    except Exception as e:
        logger.error(f"Failed to track generation metric: {e}")
        db.rollback()
        return None


def log_system_event(
    db: Session,
    level: str,
    message: str,
    logger_name: Optional[str] = None,
    user_id: Optional[str] = None,
    request_path: Optional[str] = None,
    request_method: Optional[str] = None,
    response_time_ms: Optional[float] = None,
    status_code: Optional[int] = None,
    exception_type: Optional[str] = None,
    exception_message: Optional[str] = None,
    stack_trace: Optional[str] = None
) -> Optional[SystemLog]:
    """
    Log a structured system event
    """
    try:
        # Convert user_id to UUID if provided
        user_uuid = None
        if user_id:
            try:
                user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
            except ValueError:
                pass
        
        log_entry = SystemLog(
            level=level,
            logger_name=logger_name,
            message=message[:2000],  # Truncate
            user_id=user_uuid,
            request_path=request_path,
            request_method=request_method,
            response_time_ms=response_time_ms,
            status_code=status_code,
            exception_type=exception_type,
            exception_message=exception_message[:2000] if exception_message else None,
            stack_trace=stack_trace[:5000] if stack_trace else None,
            created_at=datetime.utcnow()
        )
        
        db.add(log_entry)
        db.commit()
        
        return log_entry
        
    except Exception as e:
        logger.error(f"Failed to log system event: {e}")
        db.rollback()
        return None


def detect_jd_industry(jd_text: str) -> Optional[str]:
    """
    Simple heuristic to detect JD industry from text
    """
    jd_lower = jd_text.lower()
    
    industry_keywords = {
        "tech": ["software", "developer", "engineer", "programming", "api", "cloud", "data", "machine learning", "ai", "devops"],
        "finance": ["banking", "financial", "investment", "trading", "accounting", "audit", "hedge fund"],
        "healthcare": ["hospital", "medical", "healthcare", "clinical", "patient", "nursing", "pharmaceutical"],
        "marketing": ["marketing", "brand", "digital marketing", "seo", "content", "social media", "advertising"],
        "hr": ["human resources", "recruiting", "talent", "hr", "people operations"],
        "operations": ["operations", "logistics", "supply chain", "warehouse", "procurement"],
        "sales": ["sales", "business development", "account executive", "revenue"],
        "legal": ["legal", "attorney", "lawyer", "compliance", "regulatory"],
        "education": ["teacher", "professor", "education", "curriculum", "academic"],
    }
    
    for industry, keywords in industry_keywords.items():
        matches = sum(1 for kw in keywords if kw in jd_lower)
        if matches >= 2:
            return industry
    
    return "other"


def detect_jd_role_type(jd_text: str, title: str) -> Optional[str]:
    """
    Detect role type from JD and title
    """
    combined = f"{title} {jd_text}".lower()
    
    role_keywords = {
        "executive": ["ceo", "cto", "cfo", "vp", "vice president", "director", "head of"],
        "manager": ["manager", "lead", "supervisor", "team lead"],
        "senior": ["senior", "sr.", "principal", "staff"],
        "mid": ["mid-level", "experienced"],
        "junior": ["junior", "jr.", "entry", "associate", "intern"],
    }
    
    for role_type, keywords in role_keywords.items():
        for kw in keywords:
            if kw in combined:
                return role_type
    
    return "mid"  # Default
