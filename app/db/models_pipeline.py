from sqlalchemy import Column, String, Text, JSON, DateTime, ForeignKey, Float, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from .database import Base


class PortalConfig(Base):
    """User's portal configuration — target companies and role filters."""
    __tablename__ = "portal_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    # List of {name, url, platform: ashby|greenhouse|lever|custom, api_slug, enabled}
    companies = Column(JSON, default=[])
    role_filters_positive = Column(JSON, default=["Engineer", "AI", "ML"])
    role_filters_negative = Column(JSON, default=["Marketing", "Sales", "Intern"])
    seniority_boost = Column(JSON, default=["Senior", "Staff", "Lead", "Principal"])
    scan_schedule = Column(String, default="manual")  # manual, daily, weekly
    last_scan_at = Column(DateTime, nullable=True)
    scan_log = Column(JSON, nullable=True)  # last scan result summary
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DiscoveredJob(Base):
    """A job discovered by the portal scanner."""
    __tablename__ = "discovered_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    company = Column(String, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    platform = Column(String, nullable=True)  # ashby, greenhouse, lever, custom
    jd_text = Column(Text, nullable=True)  # fetched lazily
    jd_fetched = Column(Boolean, default=False)
    # new → evaluating → evaluated → queued → applied → dismissed
    status = Column(String, default="new")
    discovered_at = Column(DateTime, default=datetime.utcnow)
    scan_source = Column(String, nullable=True)  # playwright, api, websearch

    __table_args__ = (
        # Fast lookup by user + status for filtering
        Index("ix_discovered_jobs_user_status", "user_id", "status"),
        # Deduplication: same user should not have the same URL twice
        Index("ix_discovered_jobs_user_url", "user_id", "url"),
    )


class JobEvaluation(Base):
    """Gemini 6-block evaluation result for a discovered or manually-pasted job."""
    __tablename__ = "job_evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    # nullable — can evaluate manually pasted JDs without a scanner job
    discovered_job_id = Column(UUID(as_uuid=True), ForeignKey("discovered_jobs.id"), nullable=True)
    # nullable — linked to a tailoring run if one was done
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=True)

    archetype = Column(String, nullable=True)  # ai_platform, agentic, technical_pm, solutions_architect, forward_deployed, transformation
    archetype_confidence = Column(String, nullable=True)  # e.g. "primary" or "hybrid: ai_platform + agentic"

    # 6 evaluation blocks stored as structured JSON
    block_a = Column(JSON, nullable=True)  # role summary table
    block_b = Column(JSON, nullable=True)  # cv match + gaps
    block_c = Column(JSON, nullable=True)  # level strategy
    block_d = Column(JSON, nullable=True)  # comp research (may be empty if no web access)
    block_e = Column(JSON, nullable=True)  # personalization plan (top 5 CV + LinkedIn changes)
    block_f = Column(JSON, nullable=True)  # interview prep (STAR+R stories)

    # Individual dimension scores (1-5 scale)
    score_cv_match = Column(Float, nullable=True)
    score_north_star = Column(Float, nullable=True)
    score_comp = Column(Float, default=3.0)  # defaults to neutral when no data
    score_cultural = Column(Float, nullable=True)
    score_red_flags = Column(Float, nullable=True)  # 5=no flags, 1=many red flags
    score_global = Column(Float, nullable=True)  # weighted average

    # apply_now (>=4.5), worth_applying (>=4.0), consider (>=3.5), skip (<3.5)
    recommendation = Column(String, nullable=True)

    keywords = Column(JSON, nullable=True)  # JD keywords extracted for ATS matching
    # Application draft answers — only populated if score >= 4.5
    application_draft = Column(JSON, nullable=True)

    # The raw JD text that was evaluated (snapshot at evaluation time)
    jd_text_snapshot = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_job_evaluations_user_score", "user_id", "score_global"),
    )


class ApplicationQueue(Base):
    """Jobs queued for automated form filling. User reviews and manually submits."""
    __tablename__ = "application_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    discovered_job_id = Column(UUID(as_uuid=True), ForeignKey("discovered_jobs.id"))
    evaluation_id = Column(UUID(as_uuid=True), ForeignKey("job_evaluations.id"), nullable=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=True)

    # queued → form_filled → needs_review → submitted → error
    status = Column(String, default="queued")
    form_url = Column(String, nullable=True)  # direct URL to the application form page

    # Pre-analyzed form fields: [{field_name, field_type, value, confidence}]
    filled_fields = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)  # observations from form analysis

    queued_at = Column(DateTime, default=datetime.utcnow)
    filled_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_application_queue_user_status", "user_id", "status"),
    )
