"""
Resume Upload API - POST /api/v1/profile/upload
LinkedIn Scrape API - POST /api/v1/profile/linkedin

Handles resume file uploads (PDF, DOCX, TXT) and LinkedIn URL scraping.
"""
import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from app.auth.auth import get_current_user
from app.db.database import get_db
from app.core.resume_parser import parse_resume
from app.core.linkedin_scraper import scrape_linkedin_profile

router = APIRouter(tags=["upload"])
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_CONTENT_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
]
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".doc", ".txt"]


class UploadResponse(BaseModel):
    success: bool
    profile: Optional[dict] = None
    extraction_confidence: float = 0.0
    warnings: List[str] = []
    message: str


@router.post("/profile/upload", response_model=UploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a resume file (PDF, DOCX, TXT) and extract profile data.
    
    - Requires authentication
    - Max file size: 10MB
    - Returns extracted ProfileV3 structure
    - User reviews and saves via PUT /api/v1/profile
    """
    logger.info(f"Resume upload from user {current_user['user_id']}: {file.filename} ({file.content_type})")
    
    # Validate file extension
    filename = file.filename or "unknown"
    file_ext = filename.lower().split(".")[-1] if "." in filename else ""
    if f".{file_ext}" not in ALLOWED_EXTENSIONS:
        logger.warning(f"Invalid file extension: {file_ext}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: PDF, DOCX, TXT"
        )
    
    # Validate content type (with flexibility for browser variations)
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES and not content_type.startswith("application/"):
        # Some browsers send different content types, fall back to extension check
        if f".{file_ext}" not in ALLOWED_EXTENSIONS:
            logger.warning(f"Invalid content type: {content_type}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: PDF, DOCX, TXT"
            )
    
    # Read file content
    try:
        file_bytes = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(status_code=400, detail="Failed to read uploaded file")
    
    # Validate file size
    if len(file_bytes) > MAX_FILE_SIZE:
        logger.warning(f"File too large: {len(file_bytes)} bytes")
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: 10MB"
        )
    
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    
    logger.info(f"Processing file: {filename} ({len(file_bytes)} bytes)")
    
    # Parse resume
    result = parse_resume(file_bytes, content_type, filename)
    
    if not result["success"]:
        logger.error(f"Resume parsing failed: {result['message']}")
        # Return structured error (not 500) so frontend can handle gracefully
        return UploadResponse(
            success=False,
            profile=None,
            extraction_confidence=0.0,
            warnings=result.get("warnings", []),
            message=result["message"]
        )
    
    logger.info(f"Resume parsed successfully. Confidence: {result['extraction_confidence']}")
    
    return UploadResponse(
        success=True,
        profile=result["profile"],
        extraction_confidence=result["extraction_confidence"],
        warnings=result.get("warnings", []),
        message=result["message"]
    )


class LinkedInRequest(BaseModel):
    linkedin_url: str


@router.post("/profile/linkedin", response_model=UploadResponse)
async def extract_from_linkedin(
    request: LinkedInRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Extract profile data from a LinkedIn URL.
    
    - Requires authentication
    - Accepts LinkedIn profile URL (e.g., linkedin.com/in/username)
    - Returns extracted ProfileV3 structure
    - User reviews and saves via PUT /api/v1/profile
    
    Cost: ~$0.004 per profile (via Apify HarvestAPI)
    """
    logger.info(f"LinkedIn extraction from user {current_user['user_id']}: {request.linkedin_url}")
    
    if not request.linkedin_url or len(request.linkedin_url.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid LinkedIn URL"
        )
    
    # Scrape LinkedIn profile
    result = scrape_linkedin_profile(request.linkedin_url)
    
    if not result["success"]:
        logger.warning(f"LinkedIn scrape failed: {result['message']}")
        return UploadResponse(
            success=False,
            profile=None,
            extraction_confidence=0.0,
            warnings=[],
            message=result["message"]
        )
    
    logger.info(f"LinkedIn profile scraped successfully")
    
    return UploadResponse(
        success=True,
        profile=result["profile"],
        extraction_confidence=result.get("extraction_confidence", 0.95),
        warnings=["Email and phone need to be added manually (not available from LinkedIn)"],
        message=result["message"]
    )
