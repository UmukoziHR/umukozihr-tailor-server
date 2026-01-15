"""
Clerk Authentication Module

Verifies Clerk JWT tokens and provides user authentication.
Clerk uses RS256 signed JWTs with their public key.
"""

import os
import logging
import httpx
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.db.database import get_db
from app.db.models import User

logger = logging.getLogger(__name__)

# Clerk configuration
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY", "")
CLERK_PUBLISHABLE_KEY = os.getenv("CLERK_PUBLISHABLE_KEY", "")
# Allow explicit override via env var (recommended for production)
CLERK_FRONTEND_API_ENV = os.getenv("CLERK_FRONTEND_API", "")

# Extract Clerk instance ID from publishable key (pk_test_xxx... or pk_live_xxx...)
def get_clerk_frontend_api():
    """Get Clerk frontend API URL - prefers env var, falls back to decoding publishable key"""
    # First, check for explicit env var (most reliable)
    if CLERK_FRONTEND_API_ENV:
        logger.info(f"Using CLERK_FRONTEND_API from env: {CLERK_FRONTEND_API_ENV}")
        return CLERK_FRONTEND_API_ENV
    
    # Hardcoded fallback for umukozihr (prevents $-suffix bug)
    if CLERK_PUBLISHABLE_KEY and "umukozihr" in CLERK_PUBLISHABLE_KEY.lower():
        logger.info("Using hardcoded Clerk frontend API for umukozihr")
        return "https://clerk.umukozihr.com"
    
    if CLERK_PUBLISHABLE_KEY:
        # The publishable key contains base64 encoded frontend API
        import base64
        try:
            # pk_test_xxx or pk_live_xxx
            parts = CLERK_PUBLISHABLE_KEY.split("_")
            if len(parts) >= 3:
                encoded = parts[2]
                # Add padding if needed
                padding = 4 - len(encoded) % 4
                if padding != 4:
                    encoded += "=" * padding
                decoded = base64.b64decode(encoded).decode('utf-8').rstrip('$')
                logger.info(f"Decoded Clerk frontend API: https://{decoded}")
                return f"https://{decoded}"
        except Exception as e:
            logger.warning(f"Could not decode Clerk publishable key: {e}")
    return None

CLERK_FRONTEND_API = get_clerk_frontend_api()
CLERK_JWKS_URL = f"{CLERK_FRONTEND_API}/.well-known/jwks.json" if CLERK_FRONTEND_API else None
logger.info(f"Clerk JWKS URL configured: {CLERK_JWKS_URL}")

# Security scheme
security = HTTPBearer()

# JWKS client for token verification
_jwks_client = None

def get_jwks_client():
    """Get or create JWKS client for Clerk token verification"""
    global _jwks_client
    if _jwks_client is None and CLERK_JWKS_URL:
        _jwks_client = PyJWKClient(CLERK_JWKS_URL)
    return _jwks_client


def verify_clerk_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Clerk JWT token and return the payload.
    
    Args:
        token: The JWT token from Clerk
        
    Returns:
        The decoded token payload or None if invalid
    """
    if not CLERK_JWKS_URL:
        logger.error("Clerk JWKS URL not configured")
        return None
    
    try:
        jwks_client = get_jwks_client()
        if not jwks_client:
            logger.error("Failed to initialize JWKS client")
            return None
        
        # Get the signing key from Clerk's JWKS
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Decode and verify the token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False}  # Clerk doesn't set audience
        )
        
        logger.debug(f"Clerk token verified successfully: {payload.get('sub')}")
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning("Clerk token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Clerk token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error verifying Clerk token: {e}", exc_info=True)
        return None


def get_or_create_user_from_clerk(
    clerk_user_id: str,
    email: str,
    auth_provider: str = "google",
    db: Session = None
) -> Optional[User]:
    """
    Get or create a user from Clerk authentication.
    
    If a user with the same email exists, link the Clerk ID to them.
    Otherwise, create a new user.
    """
    if not db:
        return None
    
    # First, try to find by clerk_id
    user = db.query(User).filter(User.clerk_id == clerk_user_id).first()
    if user:
        logger.info(f"Found existing user by clerk_id: {user.email}")
        return user
    
    # Try to find by email (migration case - existing user signs in via OAuth)
    user = db.query(User).filter(User.email == email).first()
    if user:
        # Link the Clerk ID to existing user
        logger.info(f"Linking Clerk ID to existing user: {user.email}")
        user.clerk_id = clerk_user_id
        if user.auth_provider == "email":
            # Keep as email if they originally signed up with email
            pass
        else:
            user.auth_provider = auth_provider
        user.is_verified = True  # OAuth users are verified
        db.commit()
        db.refresh(user)
        return user
    
    # Create new user
    logger.info(f"Creating new user from Clerk: {email}")
    user = User(
        clerk_id=clerk_user_id,
        email=email,
        password_hash=None,  # OAuth users don't have passwords
        auth_provider=auth_provider,
        is_admin=False,
        is_verified=True,  # OAuth users are verified by the provider
        onboarding_completed=False,
        onboarding_step=0,
        region_group="global"  # Will be updated on first request
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user_clerk(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> dict:
    """
    FastAPI dependency to get the current user from a Clerk token.
    
    Returns a dict with user_id and email for compatibility with existing code.
    """
    token = credentials.credentials
    
    # Verify the Clerk token
    payload = verify_clerk_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    clerk_user_id = payload.get("sub")
    email = payload.get("email", "") or payload.get("primary_email_address", "")
    
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID",
        )
    
    # Get or create the user in our database
    user = get_or_create_user_from_clerk(
        clerk_user_id=clerk_user_id,
        email=email,
        auth_provider=payload.get("oauth_provider", "google"),
        db=db
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get or create user",
        )
    
    return {
        "user_id": str(user.id),
        "email": user.email,
        "clerk_id": clerk_user_id,
        "is_admin": user.is_admin,
        "auth_provider": user.auth_provider,
    }


# Hybrid auth dependency - supports both Clerk and legacy JWT tokens
def get_current_user_hybrid(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> dict:
    """
    Hybrid authentication that supports both Clerk and legacy JWT tokens.
    
    This allows for gradual migration from legacy auth to Clerk.
    """
    token = credentials.credentials
    
    # Try Clerk first
    if CLERK_JWKS_URL:
        payload = verify_clerk_token(token)
        if payload:
            clerk_user_id = payload.get("sub")
            email = payload.get("email", "") or payload.get("primary_email_address", "")
            
            user = get_or_create_user_from_clerk(
                clerk_user_id=clerk_user_id,
                email=email,
                auth_provider=payload.get("oauth_provider", "google"),
                db=db
            )
            
            if user:
                return {
                    "user_id": str(user.id),
                    "email": user.email,
                    "clerk_id": clerk_user_id,
                    "is_admin": user.is_admin,
                    "auth_provider": user.auth_provider,
                }
    
    # Fall back to legacy JWT
    from app.auth.auth import verify_token
    legacy_payload = verify_token(token)
    if legacy_payload:
        user_id = legacy_payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return {
                "user_id": str(user.id),
                "email": user.email,
                "clerk_id": user.clerk_id,
                "is_admin": user.is_admin,
                "auth_provider": user.auth_provider or "email",
            }
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
