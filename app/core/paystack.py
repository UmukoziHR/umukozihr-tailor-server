"""
Paystack Payment Integration
v1.4 - Handles subscriptions via Paystack API

Paystack API Docs: https://paystack.com/docs/api
"""
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.core.subscription import (
    PAYSTACK_SECRET_KEY,
    PAYSTACK_BASE_URL,
    PAYSTACK_PLAN_AFRICA_MONTHLY,
    PAYSTACK_PLAN_GLOBAL_MONTHLY,
    PAYSTACK_PLAN_AFRICA_YEARLY,
    PAYSTACK_PLAN_GLOBAL_YEARLY,
    get_paystack_plan_code,
    get_user_price,
    is_african_user
)

logger = logging.getLogger(__name__)


def get_headers() -> Dict[str, str]:
    """Get Paystack API headers"""
    return {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }


async def initialize_transaction(
    email: str,
    amount_usd: float,
    user_id: str,
    plan_code: Optional[str] = None,
    callback_url: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Initialize a Paystack transaction
    
    For one-time payments: Just pass amount
    For subscriptions: Pass plan_code
    
    Returns:
        {
            "status": True,
            "message": "Authorization URL created",
            "data": {
                "authorization_url": "https://checkout.paystack.com/xxx",
                "access_code": "xxx",
                "reference": "xxx"
            }
        }
    """
    if not PAYSTACK_SECRET_KEY:
        logger.warning("Paystack not configured - returning mock response")
        return {
            "status": False,
            "message": "Payment system not configured",
            "data": None
        }
    
    # Convert USD to kobo (smallest unit) - Paystack uses kobo for GHS
    # Note: Paystack handles currency conversion based on your account settings
    amount_kobo = int(amount_usd * 100)  # $5 = 500 cents
    
    payload = {
        "email": email,
        "amount": amount_kobo,
        "currency": "USD",
        "metadata": {
            "user_id": user_id,
            "custom_fields": [
                {
                    "display_name": "User ID",
                    "variable_name": "user_id",
                    "value": user_id
                }
            ],
            **(metadata or {})
        }
    }
    
    if plan_code:
        payload["plan"] = plan_code
    
    if callback_url:
        payload["callback_url"] = callback_url
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/transaction/initialize",
                json=payload,
                headers=get_headers(),
                timeout=30.0
            )
            
            result = response.json()
            
            if response.status_code == 200 and result.get("status"):
                logger.info(f"Transaction initialized for {email}: {result['data']['reference']}")
                return result
            else:
                logger.error(f"Paystack error: {result}")
                return {
                    "status": False,
                    "message": result.get("message", "Payment initialization failed"),
                    "data": None
                }
                
    except Exception as e:
        logger.error(f"Paystack request failed: {e}")
        return {
            "status": False,
            "message": "Payment service unavailable",
            "data": None
        }


async def create_subscription(
    email: str,
    user_id: str,
    country_code: Optional[str],
    billing_cycle: str = "monthly",
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a subscription checkout for a user
    
    Args:
        email: User's email
        user_id: User's UUID
        country_code: ISO 2-letter country code for pricing
        billing_cycle: "monthly" or "yearly"
        callback_url: URL to redirect after payment
    
    Returns:
        Dict with authorization_url to redirect user to
    """
    plan_code = get_paystack_plan_code(country_code, billing_cycle)
    price = get_user_price("pro", country_code, billing_cycle)
    
    if not plan_code:
        # If no plan code configured, use one-time payment
        logger.warning("No plan code configured - using one-time payment")
        return await initialize_transaction(
            email=email,
            amount_usd=price,
            user_id=user_id,
            callback_url=callback_url,
            metadata={
                "type": "subscription",
                "tier": "pro",
                "billing_cycle": billing_cycle,
                "is_africa": is_african_user(country_code)
            }
        )
    
    # Initialize with plan for recurring subscription
    return await initialize_transaction(
        email=email,
        amount_usd=price,
        user_id=user_id,
        plan_code=plan_code,
        callback_url=callback_url,
        metadata={
            "type": "subscription",
            "tier": "pro",
            "billing_cycle": billing_cycle,
            "is_africa": is_african_user(country_code)
        }
    )


async def verify_transaction(reference: str) -> Dict[str, Any]:
    """
    Verify a Paystack transaction by reference
    
    Returns:
        Transaction details including status, customer, etc.
    """
    if not PAYSTACK_SECRET_KEY:
        return {"status": False, "message": "Payment not configured"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
                headers=get_headers(),
                timeout=30.0
            )
            
            result = response.json()
            
            if response.status_code == 200:
                return result
            else:
                logger.error(f"Transaction verification failed: {result}")
                return {"status": False, "message": "Verification failed"}
                
    except Exception as e:
        logger.error(f"Verification request failed: {e}")
        return {"status": False, "message": "Verification service unavailable"}


async def get_subscription(subscription_code: str) -> Dict[str, Any]:
    """
    Get subscription details by code
    """
    if not PAYSTACK_SECRET_KEY:
        return {"status": False, "message": "Payment not configured"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/subscription/{subscription_code}",
                headers=get_headers(),
                timeout=30.0
            )
            
            return response.json()
            
    except Exception as e:
        logger.error(f"Get subscription failed: {e}")
        return {"status": False, "message": "Service unavailable"}


async def cancel_subscription(subscription_code: str, email_token: str) -> Dict[str, Any]:
    """
    Cancel a subscription
    
    Args:
        subscription_code: The subscription code (SUB_xxx)
        email_token: The email token from subscription
    """
    if not PAYSTACK_SECRET_KEY:
        return {"status": False, "message": "Payment not configured"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/subscription/disable",
                json={
                    "code": subscription_code,
                    "token": email_token
                },
                headers=get_headers(),
                timeout=30.0
            )
            
            result = response.json()
            logger.info(f"Subscription cancelled: {subscription_code}")
            return result
            
    except Exception as e:
        logger.error(f"Cancel subscription failed: {e}")
        return {"status": False, "message": "Cancellation failed"}


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Paystack webhook signature
    
    Paystack signs webhooks with HMAC SHA512
    """
    import hmac
    import hashlib
    
    if not PAYSTACK_SECRET_KEY:
        return False
    
    expected = hmac.new(
        PAYSTACK_SECRET_KEY.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)
