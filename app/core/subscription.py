"""
Subscription configuration and entitlement helpers.

Monetization V1 ships three tiers:
- free: 1 completed generation / rolling 30 days
- launch: configurable completed generations / rolling 30 days
- bounty: unlimited generations plus workflow extras
"""
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# RUNTIME FLAGS
# =============================================================================
SUBSCRIPTION_LIVE = os.getenv("SUBSCRIPTION_LIVE", "false").lower() == "true"
ALLOW_ANONYMOUS_GENERATION = os.getenv("ALLOW_ANONYMOUS_GENERATION", "false").lower() == "true"


def _read_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"Invalid {name}={raw!r}; falling back to {default}")
        return default
    return max(1, value)


FREE_MONTHLY_GENERATIONS = 1
LAUNCH_MONTHLY_GENERATIONS = _read_positive_int("LAUNCH_MONTHLY_GENERATIONS", 10)


# =============================================================================
# TIER DEFINITIONS
# =============================================================================
class SubscriptionTier(str, Enum):
    FREE = "free"
    LAUNCH = "launch"
    BOUNTY = "bounty"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"


LEGACY_TIER_ALIASES = {
    "pro": SubscriptionTier.BOUNTY.value,
    "premium": SubscriptionTier.BOUNTY.value,
}

TIER_ORDER = {
    SubscriptionTier.FREE.value: 0,
    SubscriptionTier.LAUNCH.value: 1,
    SubscriptionTier.BOUNTY.value: 2,
}


@dataclass
class TierLimits:
    monthly_generations: int  # -1 = unlimited
    batch_jd_upload: bool
    zip_download: bool
    priority_generation: bool
    profile_sharing: bool
    ats_keywords: bool
    cover_letter: bool
    resume_templates: int
    ai_suggestions: bool


@dataclass
class TierPricing:
    tier: SubscriptionTier
    monthly_usd: float
    display_name: str
    description: str
    features: List[str]


@dataclass
class PaymentConfig:
    tier: str
    display_currency: str
    display_price: str
    usd_amount: float
    paystack_currency: str
    paystack_amount: int


@dataclass
class GenerationAccessDecision:
    allowed: bool
    tier: str
    used: int
    limit: int
    remaining: int
    reason_code: Optional[str] = None
    message: Optional[str] = None
    upgrade_target: Optional[str] = None


TIER_LIMITS = {
    SubscriptionTier.FREE: TierLimits(
        monthly_generations=FREE_MONTHLY_GENERATIONS,
        batch_jd_upload=False,
        zip_download=False,
        priority_generation=False,
        profile_sharing=True,
        ats_keywords=True,
        cover_letter=True,
        resume_templates=1,
        ai_suggestions=True,
    ),
    SubscriptionTier.LAUNCH: TierLimits(
        monthly_generations=LAUNCH_MONTHLY_GENERATIONS,
        batch_jd_upload=False,
        zip_download=False,
        priority_generation=False,
        profile_sharing=True,
        ats_keywords=True,
        cover_letter=True,
        resume_templates=1,
        ai_suggestions=True,
    ),
    SubscriptionTier.BOUNTY: TierLimits(
        monthly_generations=-1,
        batch_jd_upload=True,
        zip_download=True,
        priority_generation=True,
        profile_sharing=True,
        ats_keywords=True,
        cover_letter=True,
        resume_templates=5,
        ai_suggestions=True,
    ),
}

TIER_PRICING = {
    SubscriptionTier.FREE: TierPricing(
        tier=SubscriptionTier.FREE,
        monthly_usd=0,
        display_name="Free",
        description="For first-time users validating the workflow.",
        features=[
            "1 completed generation every 30 days",
            "Single-job generation",
            "Cover letter generation",
            "ATS keyword optimization",
            "Profile sharing",
        ],
    ),
    SubscriptionTier.LAUNCH: TierPricing(
        tier=SubscriptionTier.LAUNCH,
        monthly_usd=10,
        display_name="Launch",
        description="For focused single-job applications.",
        features=[
            f"{LAUNCH_MONTHLY_GENERATIONS} completed generations every 30 days",
            "Single-job generation",
            "Cover letter generation",
            "ATS keyword optimization",
            "Profile sharing",
        ],
    ),
    SubscriptionTier.BOUNTY: TierPricing(
        tier=SubscriptionTier.BOUNTY,
        monthly_usd=20,
        display_name="Bounty",
        description="For high-volume job hunts and full workflow access.",
        features=[
            "Unlimited completed generations",
            "Batch job description upload",
            "ZIP downloads",
            "Priority generation queue",
            "Extra templates",
            "Everything in Launch",
        ],
    ),
}


# =============================================================================
# AFRICAN COUNTRIES
# =============================================================================
AFRICAN_COUNTRIES = {
    "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD", "KM",
    "CG", "CD", "CI", "DJ", "EG", "GQ", "ER", "SZ", "ET", "GA", "GM",
    "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG", "MW", "ML", "MR",
    "MU", "MA", "MZ", "NA", "NE", "NG", "RW", "ST", "SN", "SC", "SL",
    "SO", "ZA", "SS", "SD", "TZ", "TG", "TN", "UG", "ZM", "ZW",
}


def is_african_user(country_code: Optional[str]) -> bool:
    if not country_code:
        return False
    return country_code.upper() in AFRICAN_COUNTRIES


# =============================================================================
# TIER HELPERS
# =============================================================================
def normalize_tier_name(tier: Optional[str]) -> str:
    if not tier:
        return SubscriptionTier.FREE.value

    normalized = str(tier).strip().lower()
    normalized = LEGACY_TIER_ALIASES.get(normalized, normalized)

    if normalized in TIER_ORDER:
        return normalized
    return SubscriptionTier.FREE.value


def tier_rank(tier: Optional[str]) -> int:
    return TIER_ORDER.get(normalize_tier_name(tier), 0)


def is_paid_tier(tier: Optional[str]) -> bool:
    return normalize_tier_name(tier) in {
        SubscriptionTier.LAUNCH.value,
        SubscriptionTier.BOUNTY.value,
    }


def is_bounty_tier(tier: Optional[str]) -> bool:
    return normalize_tier_name(tier) == SubscriptionTier.BOUNTY.value


def get_tier_limits(tier: Optional[str]) -> TierLimits:
    tier_enum = SubscriptionTier(normalize_tier_name(tier))
    return TIER_LIMITS[tier_enum]


def get_tier_pricing(tier: Optional[str]) -> TierPricing:
    tier_enum = SubscriptionTier(normalize_tier_name(tier))
    return TIER_PRICING[tier_enum]


def get_user_price(tier: Optional[str], country_code: Optional[str] = None) -> float:
    _ = country_code
    return get_tier_pricing(tier).monthly_usd


def can_use_feature(tier: Optional[str], feature: str) -> bool:
    if not SUBSCRIPTION_LIVE:
        return True

    limits = get_tier_limits(tier)
    return bool(getattr(limits, feature, False))


def get_subscription_features(tier: Optional[str]) -> dict:
    limits = get_tier_limits(tier)
    if not SUBSCRIPTION_LIVE:
        return {
            "batch_upload": True,
            "zip_download": True,
            "priority_queue": True,
            "profile_sharing": True,
            "ats_keywords": True,
            "cover_letter": True,
            "unlimited_generations": True,
            "extra_templates": True,
        }

    return {
        "batch_upload": limits.batch_jd_upload,
        "zip_download": limits.zip_download,
        "priority_queue": limits.priority_generation,
        "profile_sharing": limits.profile_sharing,
        "ats_keywords": limits.ats_keywords,
        "cover_letter": limits.cover_letter,
        "unlimited_generations": limits.monthly_generations == -1,
        "extra_templates": limits.resume_templates > 1,
    }


def ensure_usage_window(user, now: Optional[datetime] = None) -> bool:
    now = now or datetime.utcnow()
    changed = False

    if user.monthly_generations_used is None:
        user.monthly_generations_used = 0
        changed = True

    if not user.usage_reset_at:
        user.usage_reset_at = now + timedelta(days=30)
        changed = True
    elif user.usage_reset_at <= now:
        user.monthly_generations_used = 0
        user.usage_reset_at = now + timedelta(days=30)
        changed = True

    return changed


def sync_user_subscription(user) -> bool:
    changed = False
    normalized_tier = normalize_tier_name(getattr(user, "subscription_tier", None))
    limits = get_tier_limits(normalized_tier)

    if getattr(user, "subscription_tier", None) != normalized_tier:
        user.subscription_tier = normalized_tier
        changed = True

    if getattr(user, "monthly_generations_limit", None) != limits.monthly_generations:
        user.monthly_generations_limit = limits.monthly_generations
        changed = True

    return changed


def check_generation_limit(tier: Optional[str], used: int) -> dict:
    if not SUBSCRIPTION_LIVE:
        return {"allowed": True, "remaining": -1, "limit": -1}

    limit = get_tier_limits(tier).monthly_generations
    if limit == -1:
        return {"allowed": True, "remaining": -1, "limit": -1}

    remaining = max(0, limit - max(0, used))
    return {
        "allowed": remaining > 0,
        "remaining": remaining,
        "limit": limit,
    }


def evaluate_generation_access(user, planned_jobs: int = 1) -> GenerationAccessDecision:
    tier = normalize_tier_name(getattr(user, "subscription_tier", None))
    used = getattr(user, "monthly_generations_used", 0) or 0
    limit_state = check_generation_limit(tier, used)

    if not SUBSCRIPTION_LIVE:
        return GenerationAccessDecision(
            allowed=True,
            tier=tier,
            used=used,
            limit=-1,
            remaining=-1,
        )

    auth_provider = getattr(user, "auth_provider", "email") or "email"
    if auth_provider == "email" and not bool(getattr(user, "is_verified", False)):
        return GenerationAccessDecision(
            allowed=False,
            tier=tier,
            used=used,
            limit=limit_state["limit"],
            remaining=limit_state["remaining"],
            reason_code="verification_required",
            message="Please verify your email before generating documents.",
        )

    limits = get_tier_limits(tier)
    if planned_jobs > 1 and not limits.batch_jd_upload:
        return GenerationAccessDecision(
            allowed=False,
            tier=tier,
            used=used,
            limit=limit_state["limit"],
            remaining=limit_state["remaining"],
            reason_code="batch_upgrade_required",
            message="Batch generation is available on the Bounty plan.",
            upgrade_target=SubscriptionTier.BOUNTY.value,
        )

    if limits.monthly_generations != -1 and limit_state["remaining"] < planned_jobs:
        if tier == SubscriptionTier.FREE.value:
            return GenerationAccessDecision(
                allowed=False,
                tier=tier,
                used=used,
                limit=limit_state["limit"],
                remaining=limit_state["remaining"],
                reason_code="free_limit_reached",
                message=(
                    "You have used your free generation for this month. "
                    "Upgrade to Launch or Bounty to continue."
                ),
                upgrade_target=SubscriptionTier.LAUNCH.value,
            )
        return GenerationAccessDecision(
            allowed=False,
            tier=tier,
            used=used,
            limit=limit_state["limit"],
            remaining=limit_state["remaining"],
            reason_code="launch_limit_reached",
            message=(
                "You have reached your Launch plan limit for this month. "
                "Upgrade to Bounty to continue."
            ),
            upgrade_target=SubscriptionTier.BOUNTY.value,
        )

    return GenerationAccessDecision(
        allowed=True,
        tier=tier,
        used=used,
        limit=limit_state["limit"],
        remaining=limit_state["remaining"],
    )


def record_generation_usage(user, count: int = 1, now: Optional[datetime] = None) -> None:
    ensure_usage_window(user, now=now)
    user.monthly_generations_used = (user.monthly_generations_used or 0) + max(0, count)


def apply_subscription_purchase(user, tier: Optional[str], now: Optional[datetime] = None) -> str:
    normalized_tier = normalize_tier_name(tier)
    now = now or datetime.utcnow()
    limits = get_tier_limits(normalized_tier)

    user.subscription_tier = normalized_tier
    user.subscription_status = SubscriptionStatus.ACTIVE.value
    user.subscription_started_at = now
    user.subscription_expires_at = now + timedelta(days=30)
    user.monthly_generations_limit = limits.monthly_generations
    user.monthly_generations_used = 0
    user.usage_reset_at = now + timedelta(days=30)
    return normalized_tier


def get_all_plans(country_code: Optional[str] = None) -> List[dict]:
    _ = country_code
    plans = []
    for tier in [
        SubscriptionTier.FREE,
        SubscriptionTier.LAUNCH,
        SubscriptionTier.BOUNTY,
    ]:
        pricing = TIER_PRICING[tier]
        limits = TIER_LIMITS[tier]
        plans.append(
            {
                "tier": tier.value,
                "name": pricing.display_name,
                "description": pricing.description,
                "features": pricing.features,
                "monthly_price": pricing.monthly_usd,
                "is_regional_pricing": False,
                "currency": "USD",
                "limits": {
                    "monthly_generations": limits.monthly_generations,
                    "batch_upload": limits.batch_jd_upload,
                    "zip_download": limits.zip_download,
                    "priority_queue": limits.priority_generation,
                },
            }
        )
    return plans


# =============================================================================
# PAYMENT CONFIGURATION
# =============================================================================
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_BASE_URL = "https://api.paystack.co"
USD_TO_GHS_RATE = float(os.getenv("USD_TO_GHS_RATE", "16.0"))


def is_payment_configured() -> bool:
    return bool(PAYSTACK_SECRET_KEY)


def get_payment_config(tier: Optional[str]) -> PaymentConfig:
    normalized_tier = normalize_tier_name(tier)
    pricing = get_tier_pricing(normalized_tier)

    return PaymentConfig(
        tier=normalized_tier,
        display_currency="USD",
        display_price=f"${int(pricing.monthly_usd)}",
        usd_amount=pricing.monthly_usd,
        paystack_currency="GHS",
        paystack_amount=int(pricing.monthly_usd * USD_TO_GHS_RATE * 100),
    )

logger.info(f"Subscription system: {'LIVE' if SUBSCRIPTION_LIVE else 'DORMANT'}")
logger.info(f"Anonymous generation enabled: {ALLOW_ANONYMOUS_GENERATION}")
logger.info(f"Launch quota per 30 days: {LAUNCH_MONTHLY_GENERATIONS}")
logger.info(f"Payment providers configured: {is_payment_configured()}")
