"""
Subscription and billing routes.
"""
import logging
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.auth import get_current_user
from app.core.paystack import (
    create_subscription as paystack_create_subscription,
    verify_webhook_signature,
)
from app.core.subscription import (
    SUBSCRIPTION_LIVE,
    SubscriptionTier,
    SubscriptionStatus,
    apply_subscription_purchase,
    ensure_usage_window,
    evaluate_generation_access,
    get_all_plans,
    get_payment_config,
    get_subscription_features,
    get_tier_limits,
    is_african_user,
    is_payment_configured,
    normalize_tier_name,
    record_generation_usage,
    sync_user_subscription,
    tier_rank,
)
from app.db.database import get_db
from app.db.models import User
from app.routes.v1_auth import get_client_ip, get_location_from_ip
from app.utils.analytics import EventType, track_event

logger = logging.getLogger(__name__)

PAYMENT_CALLBACK_URL = os.getenv("PAYMENT_CALLBACK_URL", "https://tailor.umukozihr.com/settings")

router = APIRouter(prefix="/api/v1/subscription", tags=["subscription"])


class SubscriptionStatusResponse(BaseModel):
    is_live: bool
    tier: str
    status: str
    is_verified: bool
    started_at: Optional[str]
    expires_at: Optional[str]
    generations_used: int
    generations_limit: int
    generations_remaining: int
    can_generate: bool
    usage_resets_at: Optional[str]
    features: dict
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


class AnalyticsEventResponse(BaseModel):
    success: bool
    message: str


class UpgradeImpressionRequest(BaseModel):
    trigger: str
    remaining: Optional[int] = None


def _load_user(db: Session, user_id: str) -> User:
    try:
        user_uuid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid user ID") from exc

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _persist_user_subscription_state(db: Session, user: User) -> None:
    changed = sync_user_subscription(user)
    changed = ensure_usage_window(user) or changed
    if changed:
        db.commit()
        db.refresh(user)


def _build_upgrade_prompt(user: User, can_generate: bool, remaining: int) -> tuple[bool, Optional[str]]:
    tier = normalize_tier_name(user.subscription_tier)

    if user.auth_provider == "email" and not user.is_verified:
        return False, "Verify your email to unlock document generation."

    if tier == SubscriptionTier.FREE.value and not can_generate:
        return True, "Upgrade to Launch or Bounty to continue generating this month."

    if tier == SubscriptionTier.LAUNCH.value and not can_generate:
        return True, "Upgrade to Bounty for unlimited generations and batch tools."

    if tier == SubscriptionTier.FREE.value and remaining == 1:
        return True, "Free includes 1 generation every 30 days."

    return False, None


@router.get("/status", response_model=SubscriptionStatusResponse)
def get_subscription_status(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = _load_user(db, current_user["user_id"])
    _persist_user_subscription_state(db, user)

    decision = evaluate_generation_access(user, planned_jobs=1)
    should_show_upgrade, upgrade_reason = _build_upgrade_prompt(
        user=user,
        can_generate=decision.allowed,
        remaining=decision.remaining,
    )

    return SubscriptionStatusResponse(
        is_live=SUBSCRIPTION_LIVE,
        tier=normalize_tier_name(user.subscription_tier),
        status=user.subscription_status or SubscriptionStatus.ACTIVE.value,
        is_verified=bool(user.is_verified),
        started_at=user.subscription_started_at.isoformat() if user.subscription_started_at else None,
        expires_at=user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
        generations_used=decision.used,
        generations_limit=decision.limit,
        generations_remaining=decision.remaining,
        can_generate=decision.allowed,
        usage_resets_at=user.usage_reset_at.isoformat() if user.usage_reset_at else None,
        features=get_subscription_features(user.subscription_tier),
        should_show_upgrade=should_show_upgrade,
        upgrade_reason=upgrade_reason,
    )


@router.get("/plans", response_model=PlansResponse)
def get_plans(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = _load_user(db, current_user["user_id"])

    country_code = user.country
    if not country_code:
        client_ip = get_client_ip(request)
        if client_ip and client_ip != "unknown":
            location = get_location_from_ip(client_ip)
            country_code = location.get("country")
            if country_code:
                user.country = country_code
                user.country_name = location.get("country_name")
                user.city = location.get("city")
                user.region_group = "africa" if is_african_user(country_code) else "global"
                db.commit()

    is_africa = is_african_user(country_code)
    return PlansResponse(
        is_live=SUBSCRIPTION_LIVE,
        payment_configured=is_payment_configured(),
        plans=get_all_plans(country_code),
        user_region="africa" if is_africa else "global",
        is_regional_pricing=False,
    )


@router.post("/upgrade-intent", response_model=UpgradeIntentResponse)
async def create_upgrade_intent(
    request: Request,
    tier: str = Query(SubscriptionTier.LAUNCH.value, description="Target tier"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_tier = normalize_tier_name(tier)
    if target_tier not in {
        SubscriptionTier.LAUNCH.value,
        SubscriptionTier.BOUNTY.value,
    }:
        raise HTTPException(status_code=400, detail="Invalid target tier")

    user = _load_user(db, current_user["user_id"])
    _persist_user_subscription_state(db, user)

    current_tier = normalize_tier_name(user.subscription_tier)
    if tier_rank(current_tier) >= tier_rank(target_tier):
        plan_name = "Bounty" if current_tier == SubscriptionTier.BOUNTY.value else "Launch"
        return UpgradeIntentResponse(
            success=False,
            redirect_url=None,
            message=f"You are already on {plan_name} or a higher plan.",
            requires_payment_setup=False,
        )

    track_event(
        db=db,
        event_type=EventType.CHECKOUT_STARTED,
        user_id=str(user.id),
        event_data={"target_tier": target_tier},
        request=request,
    )

    if not is_payment_configured():
        return UpgradeIntentResponse(
            success=False,
            redirect_url=None,
            message="Payments are temporarily unavailable. Please try again later.",
            requires_payment_setup=True,
        )

    country_code = user.country
    if not country_code:
        client_ip = get_client_ip(request)
        if client_ip and client_ip != "unknown":
            location = get_location_from_ip(client_ip)
            country_code = location.get("country")
            if country_code:
                user.country = country_code
                user.country_name = location.get("country_name")
                user.city = location.get("city")
                user.region_group = "africa" if is_african_user(country_code) else "global"
                db.commit()

    payment_config = get_payment_config(target_tier)
    result = await paystack_create_subscription(
        email=user.email,
        user_id=str(user.id),
        tier=target_tier,
        country_code=country_code,
        callback_url=PAYMENT_CALLBACK_URL,
    )

    if result.get("status") and result.get("data"):
        return UpgradeIntentResponse(
            success=True,
            redirect_url=result["data"].get("authorization_url"),
            message=f"Redirecting to payment for {payment_config.display_price}/month",
            requires_payment_setup=False,
        )

    return UpgradeIntentResponse(
        success=False,
        redirect_url=None,
        message=result.get("message", "Payment initialization failed"),
        requires_payment_setup=False,
    )


@router.post("/record-usage")
def record_usage(
    count: int = Query(1, description="Number of successful generations to record"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not SUBSCRIPTION_LIVE:
        return {"recorded": False, "reason": "Subscription system not active"}

    user = _load_user(db, current_user["user_id"])
    sync_user_subscription(user)
    record_generation_usage(user, count=max(0, count))
    db.commit()
    db.refresh(user)

    return {
        "recorded": True,
        "new_total": user.monthly_generations_used or 0,
        "resets_at": user.usage_reset_at.isoformat() if user.usage_reset_at else None,
    }


@router.get("/can-generate")
def can_generate(
    count: int = Query(1, description="Number of generations planned"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = _load_user(db, current_user["user_id"])
    _persist_user_subscription_state(db, user)

    decision = evaluate_generation_access(user, planned_jobs=max(1, count))
    return {
        "can_generate": decision.allowed,
        "is_limited": decision.limit != -1,
        "remaining": decision.remaining,
        "message": decision.message,
        "reason_code": decision.reason_code,
        "upgrade_target": decision.upgrade_target,
        "is_verified": bool(user.is_verified),
    }


@router.post("/upgrade-impression", response_model=AnalyticsEventResponse)
def record_upgrade_impression(
    payload: UpgradeImpressionRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = _load_user(db, current_user["user_id"])
    track_event(
        db=db,
        event_type=EventType.UPGRADE_MODAL_IMPRESSION,
        user_id=str(user.id),
        event_data={"trigger": payload.trigger, "remaining": payload.remaining},
        request=request,
    )
    return AnalyticsEventResponse(success=True, message="Upgrade impression tracked")


@router.post("/webhooks/paystack")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

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
            return await handle_charge_success(data, db)
        if event == "subscription.create":
            return await handle_subscription_created(data, db)
        if event == "subscription.disable":
            return await handle_subscription_cancelled(data, db)
        if event == "invoice.payment_failed":
            return await handle_payment_failed(data, db)

        return {"status": "ok", "message": f"Event {event} acknowledged"}

    except Exception as exc:
        logger.error(f"Paystack webhook error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook processing failed") from exc


async def handle_charge_success(data: dict, db: Session):
    metadata = data.get("metadata", {}) or {}
    user_id = metadata.get("user_id")
    target_tier = normalize_tier_name(metadata.get("tier"))
    customer_code = data.get("customer", {}).get("customer_code")

    if not user_id:
        logger.warning("charge.success without user_id in metadata")
        return {"status": "ok", "message": "No user_id in metadata"}

    if target_tier not in {SubscriptionTier.LAUNCH.value, SubscriptionTier.BOUNTY.value}:
        logger.error(f"charge.success: invalid tier in metadata: {target_tier!r}")
        return {"status": "error", "message": f"Invalid tier: {target_tier}"}

    try:
        user = _load_user(db, user_id)
        applied_tier = apply_subscription_purchase(user, target_tier)
        user.paystack_customer_code = customer_code
        db.commit()

        track_event(
            db=db,
            event_type=EventType.SUBSCRIPTION_CONVERTED,
            user_id=str(user.id),
            event_data={"tier": applied_tier},
        )

        logger.info(f"User upgraded via webhook: {user.email} -> {applied_tier}")
        return {"status": "ok", "message": f"User upgraded to {applied_tier}"}
    except HTTPException as exc:
        logger.error(f"Webhook upgrade user not found: {user_id}")
        return {"status": "error", "message": exc.detail}
    except Exception as exc:
        logger.error(f"Error upgrading user: {exc}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(exc)}


async def handle_subscription_created(data: dict, db: Session):
    subscription_code = data.get("subscription_code")
    customer = data.get("customer", {}) or {}
    customer_code = customer.get("customer_code")
    email = customer.get("email")

    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.paystack_subscription_code = subscription_code
            user.paystack_customer_code = customer_code
            db.commit()

    return {"status": "ok", "message": "Subscription created"}


async def handle_subscription_cancelled(data: dict, db: Session):
    subscription_code = data.get("subscription_code")
    user = db.query(User).filter(User.paystack_subscription_code == subscription_code).first()

    if user:
        user.subscription_status = SubscriptionStatus.CANCELLED.value
        db.commit()

    return {"status": "ok", "message": "Subscription cancelled"}


async def handle_payment_failed(data: dict, db: Session):
    customer = data.get("customer", {}) or {}
    email = customer.get("email")

    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.subscription_status = SubscriptionStatus.PAST_DUE.value
            db.commit()

    return {"status": "ok", "message": "Payment failure recorded"}


@router.post("/webhooks/stripe")
async def stripe_webhook():
    return {"status": "ok", "message": "Using Paystack for all payments"}
