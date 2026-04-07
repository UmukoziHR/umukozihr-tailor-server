"""
Portal configuration endpoints — UmukoziHR Tailor v2.5
Manage user's target company list and role filters for portal scanning.
"""
import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.auth.auth import get_current_user
from app.core.job_scanner import DEFAULT_COMPANIES
from app.db.database import get_db
from app.db.models_pipeline import PortalConfig

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CompanyItem(BaseModel):
    name: str
    url: str
    platform: str = "custom"
    api_slug: Optional[str] = None
    enabled: bool = True


class PortalConfigRequest(BaseModel):
    companies: Optional[list[CompanyItem]] = None
    role_filters_positive: Optional[list[str]] = None
    role_filters_negative: Optional[list[str]] = None
    seniority_boost: Optional[list[str]] = None
    scan_schedule: Optional[str] = None  # manual, daily, weekly


class PortalConfigResponse(BaseModel):
    id: str
    companies: list
    role_filters_positive: list
    role_filters_negative: list
    seniority_boost: list
    scan_schedule: str
    last_scan_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_config(user_id: UUID, db: Session) -> PortalConfig:
    config = db.query(PortalConfig).filter(PortalConfig.user_id == user_id).first()
    if not config:
        # Create default config with the CareerOps default companies
        config = PortalConfig(
            user_id=user_id,
            companies=DEFAULT_COMPANIES[:10],  # Start with top 10 defaults
            role_filters_positive=["Engineer", "AI", "ML", "Product"],
            role_filters_negative=["Marketing", "Sales", "Intern", "Unpaid"],
            seniority_boost=["Senior", "Staff", "Lead", "Principal", "Head"],
            scan_schedule="manual",
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _config_to_response(config: PortalConfig) -> dict:
    return {
        "id": str(config.id),
        "companies": config.companies or [],
        "role_filters_positive": config.role_filters_positive or [],
        "role_filters_negative": config.role_filters_negative or [],
        "seniority_boost": config.seniority_boost or [],
        "scan_schedule": config.scan_schedule or "manual",
        "last_scan_at": config.last_scan_at.isoformat() if config.last_scan_at else None,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/portals/config")
def get_portal_config(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /api/v1/portals/config — get user's portal configuration."""
    user_id = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]
    config = _get_or_create_config(user_id, db)
    return _config_to_response(config)


@router.post("/portals/config")
def save_portal_config(
    body: PortalConfigRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST /api/v1/portals/config — create or update portal configuration."""
    user_id = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]
    config = _get_or_create_config(user_id, db)

    if body.companies is not None:
        config.companies = [c.model_dump() for c in body.companies]
    if body.role_filters_positive is not None:
        config.role_filters_positive = body.role_filters_positive
    if body.role_filters_negative is not None:
        config.role_filters_negative = body.role_filters_negative
    if body.seniority_boost is not None:
        config.seniority_boost = body.seniority_boost
    if body.scan_schedule is not None:
        if body.scan_schedule not in ("manual", "daily", "weekly"):
            raise HTTPException(status_code=400, detail="scan_schedule must be: manual, daily, or weekly")
        config.scan_schedule = body.scan_schedule

    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)
    return _config_to_response(config)


@router.get("/portals/defaults")
def get_default_companies():
    """GET /api/v1/portals/defaults — list pre-configured CareerOps companies."""
    return {"companies": DEFAULT_COMPANIES, "total": len(DEFAULT_COMPANIES)}


@router.post("/portals/config/company")
def add_company(
    company: CompanyItem,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST /api/v1/portals/config/company — add a company to user's portal list."""
    user_id = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]
    config = _get_or_create_config(user_id, db)

    companies = list(config.companies or [])
    # Prevent duplicates by name
    if any(c.get("name") == company.name for c in companies):
        raise HTTPException(status_code=409, detail=f"Company '{company.name}' already in your list")

    companies.append(company.model_dump())
    config.companies = companies
    config.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "company": company.model_dump(), "total": len(companies)}


@router.delete("/portals/config/company/{company_name}")
def remove_company(
    company_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """DELETE /api/v1/portals/config/company/{name} — remove a company."""
    user_id = UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"]
    config = _get_or_create_config(user_id, db)

    companies = [c for c in (config.companies or []) if c.get("name") != company_name]
    config.companies = companies
    config.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "removed": company_name, "total": len(companies)}
