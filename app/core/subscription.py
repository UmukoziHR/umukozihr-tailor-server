"""
Subscription Configuration Module
v1.4 - Payment Infrastructure (Dormant until SUBSCRIPTION_LIVE=True)

This module defines:
- Master switch for enabling/disabling subscription enforcement
- Tier definitions with limits and pricing
- Region-based pricing (Africa-first)
- Feature flags based on subscription tier
"""
import os
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# MASTER SWITCH - Controls entire subscription system
# =============================================================================
# When False: All users have unlimited access (current behavior)
# When True: Tier limits and pricing enforced
SUBSCRIPTION_LIVE = os.getenv("SUBSCRIPTION_LIVE", "false").lower() == "true"


# =============================================================================
# TIER DEFINITIONS
# =============================================================================
class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    # Future tiers (not implemented yet)
    # BASIC = "basic"
    # ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"


@dataclass
class TierLimits:
    """Defines limits for each subscription tier"""
    monthly_generations: int  # -1 = unlimited
    batch_jd_upload: bool
    zip_download: bool
    priority_generation: bool
    profile_sharing: bool
    ats_keywords: bool
    cover_letter: bool
    # Future features
    resume_templates: int  # Number of template options
    ai_suggestions: bool


@dataclass
class TierPricing:
    """Pricing for a tier in different regions"""
    tier: SubscriptionTier
    africa_monthly_usd: float
    global_monthly_usd: float
    africa_yearly_usd: float
    global_yearly_usd: float
    display_name: str
    description: str
    features: List[str]


# =============================================================================
# TIER CONFIGURATIONS
# =============================================================================
TIER_LIMITS = {
    SubscriptionTier.FREE: TierLimits(
        monthly_generations=5,  # Limited to 5/month
        batch_jd_upload=False,
        zip_download=False,  # Single file only
        priority_generation=False,
        profile_sharing=True,  # Keep this free
        ats_keywords=True,  # Keep this free
        cover_letter=True,  # Keep this free
        resume_templates=1,  # Default template only
        ai_suggestions=True  # Keep AI features in free
    ),
    SubscriptionTier.PRO: TierLimits(
        monthly_generations=-1,  # Unlimited
        batch_jd_upload=True,
        zip_download=True,
        priority_generation=True,
        profile_sharing=True,
        ats_keywords=True,
        cover_letter=True,
        resume_templates=5,  # All templates
        ai_suggestions=True
    ),
}

TIER_PRICING = {
    SubscriptionTier.FREE: TierPricing(
        tier=SubscriptionTier.FREE,
        africa_monthly_usd=0,
        global_monthly_usd=0,
        africa_yearly_usd=0,
        global_yearly_usd=0,
        display_name="Free",
        description="Perfect for getting started",
        features=[
            "5 tailored resumes per month",
            "AI-powered resume tailoring",
            "Cover letter generation",
            "ATS keyword optimization",
            "Public profile sharing",
            "Download as PDF"
        ]
    ),
    SubscriptionTier.PRO: TierPricing(
        tier=SubscriptionTier.PRO,
        africa_monthly_usd=5.00,  # $5 for Africa
        global_monthly_usd=20.00,  # $20 for global
        africa_yearly_usd=40.00,  # $40/year (33% off)
        global_yearly_usd=160.00,  # $160/year (33% off)
        display_name="Pro",
        description="For serious job seekers",
        features=[
            "Unlimited tailored resumes",
            "Batch job description upload",
            "Download all as ZIP",
            "Priority generation queue",
            "All resume templates",
            "Everything in Free",
        ]
    ),
}


# =============================================================================
# AFRICAN COUNTRIES (for regional pricing)
# =============================================================================
# ISO 3166-1 alpha-2 codes for African countries
AFRICAN_COUNTRIES = {
    "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD", "KM",
    "CG", "CD", "CI", "DJ", "EG", "GQ", "ER", "SZ", "ET", "GA", "GM",
    "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG", "MW", "ML", "MR",
    "MU", "MA", "MZ", "NA", "NE", "NG", "RW", "ST", "SN", "SC", "SL",
    "SO", "ZA", "SS", "SD", "TZ", "TG", "TN", "UG", "ZM", "ZW"
}


def is_african_user(country_code: Optional[str]) -> bool:
    """Check if user is from an African country"""
    if not country_code:
        return False
    return country_code.upper() in AFRICAN_COUNTRIES


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_tier_limits(tier: str) -> TierLimits:
    """Get limits for a subscription tier"""
    try:
        tier_enum = SubscriptionTier(tier.lower())
        return TIER_LIMITS.get(tier_enum, TIER_LIMITS[SubscriptionTier.FREE])
    except ValueError:
        return TIER_LIMITS[SubscriptionTier.FREE]


def get_tier_pricing(tier: str) -> TierPricing:
    """Get pricing for a subscription tier"""
    try:
        tier_enum = SubscriptionTier(tier.lower())
        return TIER_PRICING.get(tier_enum, TIER_PRICING[SubscriptionTier.FREE])
    except ValueError:
        return TIER_PRICING[SubscriptionTier.FREE]


def get_user_price(tier: str, country_code: Optional[str], billing_cycle: str = "monthly") -> float:
    """Get the appropriate price for a user based on region"""
    pricing = get_tier_pricing(tier)
    is_africa = is_african_user(country_code)
    
    if billing_cycle == "yearly":
        return pricing.africa_yearly_usd if is_africa else pricing.global_yearly_usd
    else:
        return pricing.africa_monthly_usd if is_africa else pricing.global_monthly_usd


def can_use_feature(tier: str, feature: str) -> bool:
    """Check if a tier has access to a feature"""
    if not SUBSCRIPTION_LIVE:
        return True  # All features available when subscription is OFF
    
    limits = get_tier_limits(tier)
    return getattr(limits, feature, False)


def check_generation_limit(tier: str, used: int) -> dict:
    """Check if user can generate more resumes"""
    if not SUBSCRIPTION_LIVE:
        return {"allowed": True, "remaining": -1, "limit": -1}
    
    limits = get_tier_limits(tier)
    limit = limits.monthly_generations
    
    if limit == -1:  # Unlimited
        return {"allowed": True, "remaining": -1, "limit": -1}
    
    remaining = max(0, limit - used)
    return {
        "allowed": remaining > 0,
        "remaining": remaining,
        "limit": limit
    }


def get_all_plans(country_code: Optional[str] = None) -> List[dict]:
    """Get all available plans with pricing"""
    is_africa = is_african_user(country_code)
    plans = []
    
    for tier in [SubscriptionTier.FREE, SubscriptionTier.PRO]:
        pricing = TIER_PRICING[tier]
        limits = TIER_LIMITS[tier]
        
        plans.append({
            "tier": tier.value,
            "name": pricing.display_name,
            "description": pricing.description,
            "features": pricing.features,
            "monthly_price": pricing.africa_monthly_usd if is_africa else pricing.global_monthly_usd,
            "yearly_price": pricing.africa_yearly_usd if is_africa else pricing.global_yearly_usd,
            "is_regional_pricing": is_africa,
            "currency": "USD",
            "limits": {
                "monthly_generations": limits.monthly_generations,
                "batch_upload": limits.batch_jd_upload,
                "zip_download": limits.zip_download,
                "priority_queue": limits.priority_generation,
            }
        })
    
    return plans


# =============================================================================
# PAYMENT PROVIDER - PAYSTACK (Global via Ghana account)
# =============================================================================
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_BASE_URL = "https://api.paystack.co"

# Plan codes - will be created in Paystack dashboard
# Format: PLN_xxxxx (monthly) - create these in Paystack
PAYSTACK_PLAN_AFRICA_MONTHLY = os.getenv("PAYSTACK_PLAN_AFRICA_MONTHLY", "")  # $5/month
PAYSTACK_PLAN_GLOBAL_MONTHLY = os.getenv("PAYSTACK_PLAN_GLOBAL_MONTHLY", "")  # $20/month
PAYSTACK_PLAN_AFRICA_YEARLY = os.getenv("PAYSTACK_PLAN_AFRICA_YEARLY", "")    # $40/year
PAYSTACK_PLAN_GLOBAL_YEARLY = os.getenv("PAYSTACK_PLAN_GLOBAL_YEARLY", "")    # $160/year

def is_payment_configured() -> bool:
    """Check if Paystack is configured"""
    return bool(PAYSTACK_SECRET_KEY)


def get_paystack_plan_code(country_code: Optional[str], billing_cycle: str = "monthly") -> Optional[str]:
    """Get the appropriate Paystack plan code based on region"""
    is_africa = is_african_user(country_code)
    
    if billing_cycle == "yearly":
        return PAYSTACK_PLAN_AFRICA_YEARLY if is_africa else PAYSTACK_PLAN_GLOBAL_YEARLY
    else:
        return PAYSTACK_PLAN_AFRICA_MONTHLY if is_africa else PAYSTACK_PLAN_GLOBAL_MONTHLY


# Log status on module load
import logging
logger = logging.getLogger(__name__)
logger.info(f"Subscription system: {'LIVE' if SUBSCRIPTION_LIVE else 'DORMANT'}")
logger.info(f"Payment providers configured: {is_payment_configured()}")
