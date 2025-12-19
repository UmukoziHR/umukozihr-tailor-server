"""
Subscription API Routes
v1.4 - Payment Infrastructure

Endpoints for:
- Getting available plans
- User subscription status
- Usage tracking
- Upgrade/downgrade intents (Paystack/Stripe integration placeholder)
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from uuid import UUID

from app.db.database import get_db
from app.db.models import User
from app.auth.auth import get_current_user
from app.core.subscription import (
    SUBSCRIPTION_LIVE,
    SubscriptionTier,
    get_all_plans,
    get_tier_limits,
    get_tier_pricing,
    get_user_price,
    check_generation_limit,
    is_african_user,
    is_payment_configured
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/subscription", tags=["subscription"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================
class SubscriptionStatusResponse(BaseModel):
    is_live: bool  # Whether subscription system is active
    tier: str
    status: str
    is_pro: bool
    started_at: Optional[str]
    expires_at: Optional[str]
    # Usage
    generations_used: int
    generations_limit: int
    generations_remaining: int
    can_generate: bool
    usage_resets_at: Optional[str]
    # Features
    features: dict
    # Upgrade prompt
    should_show_upgrade: bool
    upgrade_reason: Optional[str]


class PlansResponse(BaseModel):
    is_live: bool
    payment_configured: bool
    plans: list
    user_region: str
    is_regional_pricing: bool


class UpgradeIntentResponse(BaseModel):
    success: bool
    redirect_url: Optional[str]
    message: str
    requires_payment_setup: bool


# =============================================================================
# ENDPOINTS
# =============================================================================
@router.get("/status", response_model=SubscriptionStatusResponse)
def get_subscription_status(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/subscription/status
    Get current user's subscription status and usage
    """
    user_id = current_user["user_id"]
    
    try:
        user_uuid = UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        tier = user.subscription_tier or "free"
        limits = get_tier_limits(tier)
        
        # Check if usage should reset (monthly)
        now = datetime.utcnow()
        if user.usage_reset_at and user.usage_reset_at <= now:
            # Reset usage
            user.monthly_generations_used = 0
            user.usage_reset_at = now + timedelta(days=30)
            db.commit()
        
        # Calculate usage
        used = user.monthly_generations_used or 0
        limit = limits.monthly_generations if SUBSCRIPTION_LIVE else -1
        
        if limit == -1:
            remaining = -1
            can_generate = True
        else:
            remaining = max(0, limit - used)
            can_generate = remaining > 0
        
        # Determine if we should show upgrade prompt
        should_show_upgrade = False
        upgrade_reason = None
        
        if SUBSCRIPTION_LIVE and tier == "free":
            if limit != -1 and remaining <= 2:
                should_show_upgrade = True
                upgrade_reason = f"Only {remaining} generations left this month"
            elif used >= 3:
                should_show_upgrade = True
                upgrade_reason = "Unlock unlimited generations"
        
        # Feature access
        features = {
            "batch_upload": limits.batch_jd_upload or not SUBSCRIPTION_LIVE,
            "zip_download": limits.zip_download or not SUBSCRIPTION_LIVE,
            "priority_queue": limits.priority_generation or not SUBSCRIPTION_LIVE,
            "profile_sharing": limits.profile_sharing,
            "ats_keywords": limits.ats_keywords,
            "cover_letter": limits.cover_letter,
            "unlimited_generations": limit == -1 or not SUBSCRIPTION_LIVE,
        }
        
        return SubscriptionStatusResponse(
            is_live=SUBSCRIPTION_LIVE,
            tier=tier,
            status=user.subscription_status or "active",
            is_pro=tier == "pro",
            started_at=user.subscription_started_at.isoformat() if user.subscription_started_at else None,
            expires_at=user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
            generations_used=used,
            generations_limit=limit,
            generations_remaining=remaining,
            can_generate=can_generate,
            usage_resets_at=user.usage_reset_at.isoformat() if user.usage_reset_at else None,
            features=features,
            should_show_upgrade=should_show_upgrade,
            upgrade_reason=upgrade_reason
        )
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")


@router.get("/plans", response_model=PlansResponse)
def get_plans(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/subscription/plans
    Get available subscription plans with regional pricing
    """
    user_id = current_user["user_id"]
    
    try:
        user_uuid = UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
        
        country_code = user.country if user else None
        is_africa = is_african_user(country_code)
        
        plans = get_all_plans(country_code)
        
        return PlansResponse(
            is_live=SUBSCRIPTION_LIVE,
            payment_configured=is_payment_configured(),
            plans=plans,
            user_region="africa" if is_africa else "global",
            is_regional_pricing=is_africa
        )
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")


@router.post("/upgrade-intent")
def create_upgrade_intent(
    tier: str = Query("pro", description="Target tier"),
    billing_cycle: str = Query("monthly", description="monthly or yearly"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/subscription/upgrade-intent
    Create an intent to upgrade subscription
    
    When payment is configured:
    - Creates Paystack/Stripe checkout session
    - Returns redirect URL
    
    When payment is NOT configured:
    - Returns placeholder response
    """
    user_id = current_user["user_id"]
    
    try:
        user_uuid = UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if already on this tier
        if user.subscription_tier == tier:
            return UpgradeIntentResponse(
                success=False,
                redirect_url=None,
                message=f"You are already on the {tier} plan",
                requires_payment_setup=False
            )
        
        # Check if payment is configured
        if not is_payment_configured():
            logger.info(f"Upgrade intent for user {user_id}: {tier} ({billing_cycle}) - Payment not configured")
            return UpgradeIntentResponse(
                success=False,
                redirect_url=None,
                message="Payment system coming soon! We'll notify you when it's ready.",
                requires_payment_setup=True
            )
        
        # TODO: Implement Paystack/Stripe checkout session creation
        # For now, return placeholder
        country_code = user.country
        price = get_user_price(tier, country_code, billing_cycle)
        
        logger.info(f"Upgrade intent: user={user_id}, tier={tier}, cycle={billing_cycle}, price=${price}")
        
        # Placeholder - will be replaced with actual payment URL
        return UpgradeIntentResponse(
            success=True,
            redirect_url=None,  # Will be Paystack/Stripe URL
            message=f"Upgrade to {tier.title()} for ${price}/{billing_cycle.replace('ly', '')}",
            requires_payment_setup=False
        )
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")


@router.post("/record-usage")
def record_generation_usage(
    count: int = Query(1, description="Number of generations to record"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/subscription/record-usage
    Record generation usage (called after successful generation)
    """
    if not SUBSCRIPTION_LIVE:
        return {"recorded": False, "reason": "Subscription system not active"}
    
    user_id = current_user["user_id"]
    
    try:
        user_uuid = UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Initialize usage reset date if not set
        if not user.usage_reset_at:
            user.usage_reset_at = datetime.utcnow() + timedelta(days=30)
        
        # Reset if past reset date
        now = datetime.utcnow()
        if user.usage_reset_at <= now:
            user.monthly_generations_used = 0
            user.usage_reset_at = now + timedelta(days=30)
        
        # Record usage
        user.monthly_generations_used = (user.monthly_generations_used or 0) + count
        db.commit()
        
        return {
            "recorded": True,
            "new_total": user.monthly_generations_used,
            "resets_at": user.usage_reset_at.isoformat()
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")


@router.get("/can-generate")
def check_can_generate(
    count: int = Query(1, description="Number of generations planned"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/subscription/can-generate
    Quick check if user can generate (for UI gating)
    """
    if not SUBSCRIPTION_LIVE:
        return {
            "can_generate": True,
            "is_limited": False,
            "remaining": -1,
            "message": None
        }
    
    user_id = current_user["user_id"]
    
    try:
        user_uuid = UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        tier = user.subscription_tier or "free"
        used = user.monthly_generations_used or 0
        
        result = check_generation_limit(tier, used)
        
        # Check if they have enough remaining
        if result["limit"] != -1:
            can_generate = result["remaining"] >= count
        else:
            can_generate = True
        
        message = None
        if not can_generate:
            message = "You've reached your monthly limit. Upgrade to Pro for unlimited generations."
        elif result["remaining"] != -1 and result["remaining"] <= 2:
            message = f"Only {result['remaining']} generations left this month."
        
        return {
            "can_generate": can_generate,
            "is_limited": result["limit"] != -1,
            "remaining": result["remaining"],
            "message": message
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")


# =============================================================================
# WEBHOOK PLACEHOLDERS
# =============================================================================
@router.post("/webhooks/paystack")
async def paystack_webhook():
    """
    POST /api/v1/subscription/webhooks/paystack
    Handle Paystack payment webhooks
    
    TODO: Implement when Paystack is configured
    """
    logger.info("Paystack webhook received (not implemented)")
    return {"status": "ok", "message": "Webhook endpoint ready, implementation pending"}


@router.post("/webhooks/stripe")
async def stripe_webhook():
    """
    POST /api/v1/subscription/webhooks/stripe
    Handle Stripe payment webhooks
    
    TODO: Implement when Stripe is configured
    """
    logger.info("Stripe webhook received (not implemented)")
    return {"status": "ok", "message": "Webhook endpoint ready, implementation pending"}
