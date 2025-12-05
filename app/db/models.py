from sqlalchemy import Column, String, Text, JSON, DateTime, ForeignKey, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
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