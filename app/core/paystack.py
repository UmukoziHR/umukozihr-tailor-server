"""
Paystack Payment Integration
v1.5 - Fixed USD Pricing (Both African and International users pay in USD)

Paystack API Docs: https://paystack.com/docs/api

Key insight:
- Ghana Paystack account settles in GHS
- BUT we charge BOTH groups in USD for consistency
- African users: $5/month (500 cents)
- International users: $20/month (2000 cents)
- Everyone sees USD on checkout, Paystack settles in GHS

REQUIREMENT: International Payments must be enabled in Paystack Dashboard
"""
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.core.subscription import (
    PAYSTACK_SECRET_KEY,
    PAYSTACK_BASE_URL,
    get_payment_config,
    get_user_price,
    is_african_user,
    PaymentConfig,
    USD_PRICE_AFRICA,
    USD_PRICE_GLOBAL
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
    country_code: Optional[str],
    user_id: str,
    callback_url: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Initialize a Paystack transaction with fixed USD pricing.
    
    - African users: $5/month (500 cents)
    - International users: $20/month (2000 cents)
    
    BOTH groups see USD on checkout. Paystack settles in GHS.
    
    IMPORTANT: For this to work, Gideon must enable 
    "International Payments" in Paystack Dashboard.
    
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
    
    # Get payment configuration based on user's region
    config = get_payment_config(country_code)
    
    logger.info(f"Payment: {config.display_price} ({config.amount_cents} cents) for {'African' if config.is_african else 'International'} user")
    
    payload = {
        "email": email,
        "amount": config.amount_cents,  # Always in cents (USD)
        "currency": "USD",              # Always USD for both groups
        "metadata": {
            "user_id": user_id,
            "price_usd": config.amount,
            "display_price": config.display_price,
            "is_african": config.is_african,
            "custom_fields": [
                {
                    "display_name": "User ID",
                    "variable_name": "user_id",
                    "value": user_id
                },
                {
                    "display_name": "Price",
                    "variable_name": "price",
                    "value": config.display_price
                }
            ],
            **(metadata or {})
        }
    }
    
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
                logger.info(f"Transaction initialized: {result['data']['reference']} - {config.display_price}")
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
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a payment for subscription (one-time payment, we handle subscription internally)
    
    Fixed USD Pricing:
    - African users: $5/month (500 cents)
    - International users: $20/month (2000 cents)
    
    Args:
        email: User's email
        user_id: User's UUID
        country_code: ISO 2-letter country code for pricing tier
        callback_url: URL to redirect after payment
    
    Returns:
        Dict with authorization_url to redirect user to
    """
    config = get_payment_config(country_code)
    
    logger.info(f"Creating payment: {config.display_price} for {'African' if config.is_african else 'International'} user ({email})")
    
    return await initialize_transaction(
        email=email,
        country_code=country_code,
        user_id=user_id,
        callback_url=callback_url,
        metadata={
            "type": "subscription",
            "tier": "pro",
            "billing_cycle": "monthly",
            "is_africa": config.is_african,
            "price_usd": config.amount
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
