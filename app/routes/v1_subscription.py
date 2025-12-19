"""
Subscription API Routes
v1.4 - Payment Infrastructure with Paystack Integration

Endpoints for:
- Getting available plans
- User subscription status
- Usage tracking
- Upgrade/downgrade intents (Paystack integration)
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
from app.core.paystack import (
    create_subscription as paystack_create_subscription,
    verify_transaction,
    verify_webhook_signature
)

logger = logging.getLogger(__name__)

# Get callback URL from environment
PAYMENT_CALLBACK_URL = os.getenv("PAYMENT_CALLBACK_URL", "https://tailor.umukozihr.com/settings")

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
async def create_upgrade_intent(
    tier: str = Query("pro", description="Target tier"),
    billing_cycle: str = Query("monthly", description="monthly or yearly"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/subscription/upgrade-intent
    Create an intent to upgrade subscription
    
    When payment is configured:
    - Creates Paystack checkout session
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
        
        # Create Paystack checkout session
        country_code = user.country
        price = get_user_price(tier, country_code, billing_cycle)
        
        logger.info(f"Creating Paystack checkout: user={user_id}, tier={tier}, cycle={billing_cycle}, price=${price}")
        
        result = await paystack_create_subscription(
            email=user.email,
            user_id=user_id,
            country_code=country_code,
            billing_cycle=billing_cycle,
            callback_url=PAYMENT_CALLBACK_URL
        )
        
        if result.get("status") and result.get("data"):
            authorization_url = result["data"].get("authorization_url")
            logger.info(f"Paystack checkout created: {result['data'].get('reference')}")
            return UpgradeIntentResponse(
                success=True,
                redirect_url=authorization_url,
                message=f"Redirecting to payment for ${price}/{billing_cycle.replace('ly', '')}",
                requires_payment_setup=False
            )
        else:
            logger.error(f"Paystack checkout failed: {result.get('message')}")
            return UpgradeIntentResponse(
                success=False,
                redirect_url=None,
                message=result.get("message", "Payment initialization failed"),
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
# WEBHOOKS
# =============================================================================
@router.post("/webhooks/paystack")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    """
    POST /api/v1/subscription/webhooks/paystack
    Handle Paystack payment webhooks
    
    Events handled:
    - charge.success: Payment completed
    - subscription.create: New subscription created
    - subscription.disable: Subscription cancelled
    - invoice.payment_failed: Payment failed
    """
    # Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    
    # Verify webhook signature
    if not verify_webhook_signature(body, signature):
        logger.warning("Invalid Paystack webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    try:
        import json
        payload = json.loads(body)
        event = payload.get("event")
        data = payload.get("data", {})
        
        logger.info(f"Paystack webhook received: {event}")
        
        if event == "charge.success":
            # Payment completed - upgrade user
            return await handle_charge_success(data, db)
        
        elif event == "subscription.create":
            # Subscription created
            return await handle_subscription_created(data, db)
        
        elif event == "subscription.disable":
            # Subscription cancelled
            return await handle_subscription_cancelled(data, db)
        
        elif event == "invoice.payment_failed":
            # Payment failed
            return await handle_payment_failed(data, db)
        
        else:
            logger.info(f"Unhandled Paystack event: {event}")
            return {"status": "ok", "message": f"Event {event} acknowledged"}
            
    except Exception as e:
        logger.error(f"Paystack webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook processing failed")


async def handle_charge_success(data: dict, db: Session):
    """Handle successful payment - upgrade user to Pro"""
    metadata = data.get("metadata", {})
    user_id = metadata.get("user_id")
    customer_code = data.get("customer", {}).get("customer_code")
    
    if not user_id:
        logger.warning("charge.success without user_id in metadata")
        return {"status": "ok", "message": "No user_id in metadata"}
    
    try:
        user_uuid = UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            logger.error(f"User not found for charge.success: {user_id}")
            return {"status": "error", "message": "User not found"}
        
        # Upgrade user to Pro
        now = datetime.utcnow()
        billing_cycle = metadata.get("billing_cycle", "monthly")
        
        if billing_cycle == "yearly":
            expires_at = now + timedelta(days=365)
        else:
            expires_at = now + timedelta(days=30)
        
        user.subscription_tier = "pro"
        user.subscription_status = "active"
        user.subscription_started_at = now
        user.subscription_expires_at = expires_at
        user.paystack_customer_code = customer_code
        user.monthly_generations_limit = -1  # Unlimited
        
        db.commit()
        
        logger.info(f"User upgraded to Pro: {user_id}, expires: {expires_at}")
        return {"status": "ok", "message": "User upgraded to Pro"}
        
    except Exception as e:
        logger.error(f"Error upgrading user: {e}")
        db.rollback()
        return {"status": "error", "message": str(e)}


async def handle_subscription_created(data: dict, db: Session):
    """Handle new subscription creation"""
    subscription_code = data.get("subscription_code")
    customer = data.get("customer", {})
    customer_code = customer.get("customer_code")
    email = customer.get("email")
    
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.paystack_subscription_code = subscription_code
            user.paystack_customer_code = customer_code
            db.commit()
            logger.info(f"Subscription code saved for user: {email}")
    
    return {"status": "ok", "message": "Subscription created"}


async def handle_subscription_cancelled(data: dict, db: Session):
    """Handle subscription cancellation"""
    subscription_code = data.get("subscription_code")
    
    user = db.query(User).filter(User.paystack_subscription_code == subscription_code).first()
    
    if user:
        user.subscription_status = "cancelled"
        # Keep Pro until expiry date
        db.commit()
        logger.info(f"Subscription cancelled for user: {user.email}")
    
    return {"status": "ok", "message": "Subscription cancelled"}


async def handle_payment_failed(data: dict, db: Session):
    """Handle failed payment"""
    customer = data.get("customer", {})
    email = customer.get("email")
    
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.subscription_status = "past_due"
            db.commit()
            logger.warning(f"Payment failed for user: {email}")
    
    return {"status": "ok", "message": "Payment failure recorded"}


@router.post("/webhooks/stripe")
async def stripe_webhook():
    """
    POST /api/v1/subscription/webhooks/stripe
    Handle Stripe payment webhooks
    
    Not implemented - using Paystack for all payments
    """
    logger.info("Stripe webhook received (not used - using Paystack)")
    return {"status": "ok", "message": "Using Paystack for all payments"}
