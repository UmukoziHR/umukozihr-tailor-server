from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict
from datetime import datetime

# v1.3: Comprehensive profile schema (LinkedIn-style)

class Basics(BaseModel):
    full_name: str = ""
    headline: str = ""
    summary: str = ""
    location: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    links: List[str] = []

class Skill(BaseModel):
    name: str
    level: Optional[Literal["beginner", "intermediate", "expert"]] = "intermediate"
    keywords: List[str] = []

class Experience(BaseModel):
    title: str
    company: str
    location: Optional[str] = ""
    start: str  # YYYY-MM format
    end: str = "present"  # YYYY-MM or "present"
    employment_type: Optional[str] = "full-time"
    bullets: List[str] = []

class Education(BaseModel):
    school: str
    degree: str = ""
    start: Optional[str] = ""
    end: Optional[str] = ""
    gpa: Optional[str] = None

class Project(BaseModel):
    name: str
    url: Optional[str] = ""
    stack: List[str] = []
    bullets: List[str] = []

class Certification(BaseModel):
    name: str
    issuer: str
    date: Optional[str] = ""

class Award(BaseModel):
    name: str
    by: str
    date: Optional[str] = ""

class Language(BaseModel):
    name: str
    level: Optional[str] = ""  # e.g., C2, Native, Fluent

class Preferences(BaseModel):
    regions: List[Literal["US", "EU", "GL"]] = ["US"]
    templates: List[str] = ["minimal"]

class ProfileV3(BaseModel):
    """v1.3 comprehensive profile schema"""
    basics: Basics = Basics()
    skills: List[Skill] = []
    experience: List[Experience] = []
    education: List[Education] = []
    projects: List[Project] = []
    certifications: List[Certification] = []
    awards: List[Award] = []
    languages: List[Language] = []
    preferences: Preferences = Preferences()
    version: Optional[int] = 1
    updated_at: Optional[str] = None

# Legacy models (for backward compatibility with v1.2)
class Contact(BaseModel):
    email: Optional[str] = ""
    phone: Optional[str] = ""
    location: Optional[str] = ""
    links: List[str] = []

class Role(BaseModel):
    title: str
    company: str
    start: Optional[str] = ""
    end: Optional[str] = ""
    bullets: List[str] = []

class Profile(BaseModel):
    """Legacy v1.2 profile (kept for backward compatibility)"""
    name: str
    contacts: Contact = Contact()
    summary: str = ""
    skills: List[str] = []
    experience: List[Role] = []
    education: List[Education] = []
    projects: List[Project] = []

class JobJD(BaseModel):
    id: Optional[str] = None
    # "GL" here is Global region... later we may add other regions
    region: Literal["US", "EU", "GL"] = "US"
    company: str
    title: str
    jd_text: str

class GenerateRequest(BaseModel):
    profile: Optional[Profile] = None  # Optional for authenticated users (loaded from DB)
    jobs: List[JobJD]
    prefs: Dict = {}

# LLM output schema -- let's use gemini or a grq model with tool use...
class OutRole(BaseModel):
    title: str
    company: str
    start: Optional[str] = ""
    end: Optional[str] = ""
    bullets: List[str]

class OutResume(BaseModel):
    summary: str
    skills_line: List[str]
    experience: List[OutRole]
    projects: List[Project] = []
    education: List[Education] = []

class OutCoverLetter(BaseModel):
    address: str
    intro: str
    why_you: str
    evidence: List[str]
    why_them: str
    close: str

class OutATS(BaseModel):
    jd_keywords_matched: List[str] = []
    risks: List[str] = []

class LLMOutput(BaseModel):
    resume: OutResume
    cover_letter: OutCoverLetter
    ats: OutATS

# v1.3 API Request/Response models

class ProfileResponse(BaseModel):
    """Response for GET /api/v1/profile"""
    profile: ProfileV3
    version: int
    completeness: float
    updated_at: str

class ProfileUpdateRequest(BaseModel):
    """Request for PUT /api/v1/profile"""
    profile: ProfileV3

class ProfileUpdateResponse(BaseModel):
    """Response for PUT /api/v1/profile"""
    success: bool
    version: int
    completeness: float
    message: str

class CompletenessResponse(BaseModel):
    """Response for GET /api/v1/me/completeness"""
    completeness: float
    breakdown: Dict[str, float]
    missing_fields: List[str]

class JDFetchRequest(BaseModel):
    """Request for POST /api/v1/jd/fetch"""
    url: str

class JDFetchResponse(BaseModel):
    """Response for POST /api/v1/jd/fetch"""
    success: bool
    jd_text: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    region: Optional[str] = None
    message: str

class HistoryItem(BaseModel):
    """Single history item"""
    run_id: str
    job_id: str
    company: str
    title: str
    region: str
    status: str
    profile_version: Optional[int] = None
    artifacts_urls: Dict
    created_at: str

class HistoryResponse(BaseModel):
    """Response for GET /api/v1/history"""
    runs: List[HistoryItem]
    total: int
    page: int
    page_size: int

class RegenerateRequest(BaseModel):
    """Request for POST /api/v1/history/{run_id}/regenerate"""
    pass  # No body needed, uses run_id from path

class RegenerateResponse(BaseModel):
    """Response for regenerate endpoint"""
    success: bool
    new_run_id: str
    message: str
