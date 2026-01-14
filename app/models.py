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

# LinkedIn-specific talent data (enriches UmukoziHR talent database)
class Volunteering(BaseModel):
    organization: str
    role: str
    cause: Optional[str] = ""
    start: Optional[str] = ""
    end: Optional[str] = ""
    description: Optional[str] = ""

class Publication(BaseModel):
    title: str
    publisher: Optional[str] = ""
    date: Optional[str] = ""
    url: Optional[str] = ""
    description: Optional[str] = ""

class Course(BaseModel):
    name: str
    number: Optional[str] = ""
    associated_with: Optional[str] = ""  # School or org

class LinkedInMeta(BaseModel):
    """LinkedIn-specific metadata for talent intelligence"""
    linkedin_url: Optional[str] = ""
    linkedin_id: Optional[str] = ""
    photo_url: Optional[str] = ""
    open_to_work: Optional[bool] = False
    hiring: Optional[bool] = False
    premium: Optional[bool] = False
    verified: Optional[bool] = False
    influencer: Optional[bool] = False
    connections_count: Optional[int] = 0
    followers_count: Optional[int] = 0
    registered_at: Optional[str] = ""
    current_company: Optional[str] = ""
    industry: Optional[str] = ""

class ProfileV3(BaseModel):
    """v2.0 comprehensive profile schema - UmukoziHR Talent Rich!"""
    basics: Basics = Basics()
    skills: List[Skill] = []
    experience: List[Experience] = []
    education: List[Education] = []
    projects: List[Project] = []
    certifications: List[Certification] = []
    awards: List[Award] = []
    languages: List[Language] = []
    # LinkedIn-enriched sections
    volunteering: List[Volunteering] = []
    publications: List[Publication] = []
    courses: List[Course] = []
    linkedin_meta: Optional[LinkedInMeta] = None
    # Standard fields
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
    # v1.3: Full profile fields for complete context
    certifications: List[Certification] = []
    awards: List[Award] = []
    languages: List[Language] = []

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


# v1.4 Shareable Profiles

class PublicProfileResponse(BaseModel):
    """Response for public profile viewing"""
    username: str
    profile: ProfileV3
    completeness: float
    profile_views: int
    member_since: str
    is_available_for_hire: bool = True
    avatar_url: Optional[str] = None


class ShareSettingsRequest(BaseModel):
    """Request for updating share/privacy settings"""
    is_public: bool


class ShareSettingsResponse(BaseModel):
    """Response with share settings and profile URL"""
    success: bool
    is_public: bool
    username: str
    profile_url: str
    message: str


class ShareLinksResponse(BaseModel):
    """Response with pre-formatted share links for all platforms"""
    profile_url: str
    linkedin: str
    twitter: str
    whatsapp: str
    telegram: str
    email_subject: str
    email_body: str
    copy_text: str
