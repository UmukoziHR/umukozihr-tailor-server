from sqlalchemy import Column, String, Text, JSON, DateTime, ForeignKey, Integer, Float, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from .database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    onboarding_step = Column(Integer, default=0)
    # Location tracking
    country = Column(String, nullable=True)  # 2-letter ISO code (e.g., 'GH', 'US')
    country_name = Column(String, nullable=True)  # Full country name
    city = Column(String, nullable=True)
    signup_ip = Column(String, nullable=True)
    # Shareable profiles (v1.4)
    username = Column(String, unique=True, nullable=True)
    is_public = Column(Boolean, default=True, nullable=False)
    profile_views = Column(Integer, default=0)
    # Subscription & Payment (v1.4 prep)
    subscription_tier = Column(String, default="free")  # free, basic, pro, enterprise
    subscription_status = Column(String, default="active")  # active, cancelled, expired, trial
    subscription_started_at = Column(DateTime, nullable=True)
    subscription_expires_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True)  # For Stripe integration
    # Usage tracking
    monthly_generations_used = Column(Integer, default=0)
    monthly_generations_limit = Column(Integer, default=5)  # Free tier: 5/month
    usage_reset_at = Column(DateTime, nullable=True)  # When to reset monthly count
    created_at = Column(DateTime, default=datetime.utcnow)

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    profile_data = Column(JSON, nullable=False)
    version = Column(Integer, default=1)
    completeness = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    company = Column(String)
    title = Column(String)
    jd_text = Column(Text)
    region = Column(String)
    url = Column(String, nullable=True)
    is_fetched = Column(Boolean, default=False)
    fetch_status = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Run(Base):
    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    status = Column(String, default="pending")  # pending, processing, completed, failed
    profile_version = Column(Integer, nullable=True)
    llm_output = Column(JSON)
    artifacts_urls = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================
# Analytics & Monitoring Tables (v1.3 Final)
# ============================================

class UserEvent(Base):
    """Track user activity events for analytics"""
    __tablename__ = "user_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # nullable for anonymous events
    event_type = Column(String, nullable=False)  # signup, login, logout, onboarding_start, onboarding_step, onboarding_complete, profile_update, generation_start, generation_complete, generation_error, download
    event_data = Column(JSON, nullable=True)  # Additional event-specific data
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_user_events_user_id', 'user_id'),
        Index('ix_user_events_event_type', 'event_type'),
        Index('ix_user_events_created_at', 'created_at'),
    )


class GenerationMetric(Base):
    """Track generation performance and success metrics"""
    __tablename__ = "generation_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Timing metrics (in seconds)
    total_duration = Column(Float, nullable=True)
    llm_duration = Column(Float, nullable=True)
    tex_render_duration = Column(Float, nullable=True)
    pdf_compile_duration = Column(Float, nullable=True)
    
    # Success/failure tracking
    success = Column(Boolean, default=True)
    error_type = Column(String, nullable=True)  # llm_error, validation_error, compile_error, etc.
    error_message = Column(Text, nullable=True)
    
    # JD insights
    jd_text_length = Column(Integer, nullable=True)
    jd_industry = Column(String, nullable=True)  # detected or inferred
    jd_role_type = Column(String, nullable=True)  # tech, admin, finance, etc.
    
    # Output info
    region = Column(String, nullable=True)
    resume_pdf_success = Column(Boolean, default=False)
    cover_letter_pdf_success = Column(Boolean, default=False)
    keywords_matched_count = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_generation_metrics_user_id', 'user_id'),
        Index('ix_generation_metrics_created_at', 'created_at'),
        Index('ix_generation_metrics_success', 'success'),
    )


class SystemLog(Base):
    """Structured system logs for monitoring and debugging"""
    __tablename__ = "system_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    level = Column(String, nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    logger_name = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    
    # Context
    user_id = Column(UUID(as_uuid=True), nullable=True)
    request_path = Column(String, nullable=True)
    request_method = Column(String, nullable=True)
    
    # Performance
    response_time_ms = Column(Float, nullable=True)
    status_code = Column(Integer, nullable=True)
    
    # Error details
    exception_type = Column(String, nullable=True)
    exception_message = Column(Text, nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_system_logs_level', 'level'),
        Index('ix_system_logs_created_at', 'created_at'),
    )