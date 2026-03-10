"""
Paystack payment integration for Launch and Bounty subscriptions.
"""
import logging
from typing import Any, Dict, Optional

import httpx

from app.core.subscription import (
    PAYSTACK_BASE_URL,
    PAYSTACK_SECRET_KEY,
    PaymentConfig,
    get_payment_config,
    normalize_tier_name,
)

logger = logging.getLogger(__name__)


def get_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


async def initialize_transaction(
    email: str,
    tier: str,
    user_id: str,
    callback_url: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    if not PAYSTACK_SECRET_KEY:
        logger.warning("Paystack not configured - returning mock response")
        return {
            "status": False,
            "message": "Payment system not configured",
            "data": None,
        }

    config: PaymentConfig = get_payment_config(tier)
    logger.info(
        f"Payment init: tier={config.tier}, display={config.display_price}, "
        f"paystack_amount={config.paystack_amount}"
    )

    payload = {
        "email": email,
        "amount": config.paystack_amount,
        "currency": config.paystack_currency,
        "metadata": {
            "user_id": user_id,
            "display_price": config.display_price,
            "usd_amount": config.usd_amount,
            "custom_fields": [
                {
                    "display_name": "User ID",
                    "variable_name": "user_id",
                    "value": user_id,
                },
                {
                    "display_name": "Price (USD)",
                    "variable_name": "price_usd",
                    "value": config.display_price,
                },
            ],
            **(metadata or {}),
        },
    }

    if callback_url:
        payload["callback_url"] = callback_url

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/transaction/initialize",
                json=payload,
                headers=get_headers(),
                timeout=30.0,
            )
            result = response.json()

            if response.status_code == 200 and result.get("status"):
                logger.info(f"Transaction initialized: {result['data']['reference']}")
                return result

            logger.error(f"Paystack error: {result}")
            return {
                "status": False,
                "message": result.get("message", "Payment initialization failed"),
                "data": None,
            }
    except Exception as exc:
        logger.error(f"Paystack request failed: {exc}")
        return {
            "status": False,
            "message": "Payment service unavailable",
            "data": None,
        }


async def create_subscription(
    email: str,
    user_id: str,
    tier: str,
    country_code: Optional[str],
    callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    _ = country_code
    normalized_tier = normalize_tier_name(tier)
    config = get_payment_config(normalized_tier)

    logger.info(
        f"Creating payment: tier={normalized_tier}, {config.display_price} "
        f"(GHS {config.paystack_amount/100:.0f}) for {email}"
    )

    return await initialize_transaction(
        email=email,
        tier=normalized_tier,
        user_id=user_id,
        callback_url=callback_url,
        metadata={
            "type": "subscription",
            "tier": normalized_tier,
            "billing_cycle": "monthly",
            "price_usd": config.usd_amount,
        },
    )


async def verify_transaction(reference: str) -> Dict[str, Any]:
    if not PAYSTACK_SECRET_KEY:
        return {"status": False, "message": "Payment not configured"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
                headers=get_headers(),
                timeout=30.0,
            )
            result = response.json()

            if response.status_code == 200:
                return result

            logger.error(f"Transaction verification failed: {result}")
            return {"status": False, "message": "Verification failed"}
    except Exception as exc:
        logger.error(f"Verification request failed: {exc}")
        return {"status": False, "message": "Verification service unavailable"}


async def get_subscription(subscription_code: str) -> Dict[str, Any]:
    if not PAYSTACK_SECRET_KEY:
        return {"status": False, "message": "Payment not configured"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/subscription/{subscription_code}",
                headers=get_headers(),
                timeout=30.0,
            )
            return response.json()
    except Exception as exc:
        logger.error(f"Get subscription failed: {exc}")
        return {"status": False, "message": "Service unavailable"}


async def cancel_subscription(subscription_code: str, email_token: str) -> Dict[str, Any]:
    if not PAYSTACK_SECRET_KEY:
        return {"status": False, "message": "Payment not configured"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/subscription/disable",
                json={"code": subscription_code, "token": email_token},
                headers=get_headers(),
                timeout=30.0,
            )
            result = response.json()
            logger.info(f"Subscription cancelled: {subscription_code}")
            return result
    except Exception as exc:
        logger.error(f"Cancel subscription failed: {exc}")
        return {"status": False, "message": "Cancellation failed"}


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    import hashlib
    import hmac

    if not PAYSTACK_SECRET_KEY:
        return False

    expected = hmac.new(
        PAYSTACK_SECRET_KEY.encode("utf-8"),
        payload,
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
