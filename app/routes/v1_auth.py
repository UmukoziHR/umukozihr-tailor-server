import logging
import httpx
import os
import jwt
import base64
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.db.database import get_db
from app.db.models import User
from app.auth.auth import hash_password, verify_password, create_access_token
from app.utils.analytics import track_event, EventType
from app.core.subscription import is_african_user

logger = logging.getLogger(__name__)

# Supabase JWT secret (from your Supabase project settings)
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies"""
    # Check for forwarded headers (behind proxy/CDN like Render/Cloudflare)
    forwarded_for = request.headers.get('x-forwarded-for')
    if forwarded_for:
        # First IP in the list is the original client
        return forwarded_for.split(',')[0].strip()
    
    cf_ip = request.headers.get('cf-connecting-ip')
    if cf_ip:
        return cf_ip
    
    true_client_ip = request.headers.get('true-client-ip')
    if true_client_ip:
        return true_client_ip
    
    return request.client.host if request.client else 'unknown'


def get_location_from_ip(ip: str) -> dict:
    """Get country/city from IP using multiple geolocation APIs with fallback"""
    # Skip localhost/private IPs
    if ip in ['127.0.0.1', 'localhost', 'unknown', ''] or ip.startswith('10.') or ip.startswith('192.168.') or ip.startswith('172.'):
        logger.info(f"Skipping geolocation for private/local IP: {ip}")
        return {'country': None, 'country_name': None, 'city': None}
    
    # Try multiple geo APIs with fallback
    apis = [
        # ipinfo.io - very reliable, 50k/month free
        {
            'url': f'https://ipinfo.io/{ip}/json',
            'parser': lambda d: {
                'country': d.get('country'),
                'country_name': get_country_name(d.get('country')),
                'city': d.get('city')
            } if d.get('country') else None
        },
        # ip-api.com - backup (HTTP only but reliable)
        {
            'url': f'http://ip-api.com/json/{ip}?fields=status,country,countryCode,city',
            'parser': lambda d: {
                'country': d.get('countryCode'),
                'country_name': d.get('country'),
                'city': d.get('city')
            } if d.get('status') == 'success' else None
        },
        # ipapi.co - another backup
        {
            'url': f'https://ipapi.co/{ip}/json/',
            'parser': lambda d: {
                'country': d.get('country_code'),
                'country_name': d.get('country_name'),
                'city': d.get('city')
            } if d.get('country_code') else None
        }
    ]
    
    for api in apis:
        try:
            response = httpx.get(api['url'], timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                result = api['parser'](data)
                if result and result.get('country'):
                    logger.info(f"Geo lookup success for {ip}: {result['country']} ({result['country_name']})")
                    return result
        except Exception as e:
            logger.warning(f"Geo API failed for {ip} ({api['url'][:30]}...): {e}")
            continue
    
    logger.warning(f"All geo APIs failed for IP: {ip}")
    return {'country': None, 'country_name': None, 'city': None}


# Country code to name mapping for ipinfo.io which only returns code
COUNTRY_NAMES = {
    'GH': 'Ghana', 'NG': 'Nigeria', 'KE': 'Kenya', 'ZA': 'South Africa', 'EG': 'Egypt',
    'MA': 'Morocco', 'TZ': 'Tanzania', 'ET': 'Ethiopia', 'UG': 'Uganda', 'RW': 'Rwanda',
    'SN': 'Senegal', 'CI': "Côte d'Ivoire", 'CM': 'Cameroon', 'ZW': 'Zimbabwe', 'ZM': 'Zambia',
    'US': 'United States', 'GB': 'United Kingdom', 'DE': 'Germany', 'FR': 'France', 'NL': 'Netherlands',
    'CA': 'Canada', 'AU': 'Australia', 'IN': 'India', 'AE': 'United Arab Emirates', 'SG': 'Singapore',
    'JP': 'Japan', 'CN': 'China', 'BR': 'Brazil', 'MX': 'Mexico', 'ES': 'Spain', 'IT': 'Italy',
    'PL': 'Poland', 'SE': 'Sweden', 'NO': 'Norway', 'DK': 'Denmark', 'FI': 'Finland', 'IE': 'Ireland',
    'CH': 'Switzerland', 'AT': 'Austria', 'BE': 'Belgium', 'PT': 'Portugal', 'CZ': 'Czech Republic',
}

def get_country_name(code: str) -> str:
    """Get country name from 2-letter code"""
    if not code:
        return None
    return COUNTRY_NAMES.get(code.upper(), code)

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/signup")
def signup(req: SignupRequest, request: Request, db: Session = Depends(get_db)):
    logger.info(f"=== SIGNUP START === Email: {req.email}")

    try:
        # Check if user exists
        logger.info(f"Checking if user exists: {req.email}")
        existing = db.query(User).filter(User.email == req.email).first()

        if existing:
            logger.warning(f"Signup failed - email already registered: {req.email}")
            raise HTTPException(status_code=400, detail="Email already registered")

        logger.info(f"Email available, proceeding with user creation: {req.email}")

        # Hash password
        logger.info(f"Hashing password for user: {req.email}")
        hashed_password = hash_password(req.password)
        logger.info(f"Password hashed successfully, length: {len(hashed_password)}")

        # Get client IP and location
        client_ip = get_client_ip(request)
        location = get_location_from_ip(client_ip)
        logger.info(f"Client IP: {client_ip}, Location: {location}")
        
        # Determine region group for pricing
        country_code = location.get('country')
        region_group = 'africa' if is_african_user(country_code) else 'global'
        logger.info(f"Region group: {region_group}")

        # Create user
        logger.info(f"Creating user object for: {req.email}")
        user = User(
            email=req.email,
            password_hash=hashed_password,
            is_admin=False,
            is_verified=False,
            onboarding_completed=False,
            onboarding_step=0,
            country=country_code,
            country_name=location.get('country_name'),
            city=location.get('city'),
            signup_ip=client_ip,
            region_group=region_group
        )

        logger.info(f"Adding user to database session: {req.email}")
        db.add(user)

        logger.info(f"Committing user to database: {req.email}")
        db.commit()

        logger.info(f"Refreshing user object: {req.email}")
        db.refresh(user)

        logger.info(f"User created successfully: {req.email} with ID: {user.id}")

        # Track signup event
        track_event(
            db=db,
            event_type=EventType.SIGNUP,
            user_id=str(user.id),
            event_data={"email": req.email},
            request=request
        )

        # Generate token
        logger.info(f"Generating access token for user: {user.id}")
        access_token = create_access_token({"sub": str(user.id)})
        logger.info(f"Access token generated successfully for user: {user.id}")

        logger.info(f"=== SIGNUP SUCCESS === User ID: {user.id}, Email: {req.email}")
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== SIGNUP ERROR === Email: {req.email}, Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

@router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    logger.info(f"=== LOGIN START === Email: {req.email}")

    try:
        logger.info(f"Querying database for user: {req.email}")
        user = db.query(User).filter(User.email == req.email).first()

        if not user:
            logger.warning(f"Login failed - user not found: {req.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        logger.info(f"User found, verifying password for: {req.email}")
        password_valid = verify_password(req.password, str(user.password_hash))

        if not password_valid:
            logger.warning(f"Login failed - invalid password for email: {req.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        logger.info(f"Password verified successfully for user: {user.id}")

        # Update last login timestamp and refresh location
        client_ip = get_client_ip(request)
        user.last_login_at = datetime.utcnow()
        
        # Refresh location on every login (catches VPN changes, fixes NULL countries)
        if client_ip and client_ip != 'unknown':
            location = get_location_from_ip(client_ip)
            if location.get('country'):
                old_country = user.country
                user.country = location.get('country')
                user.country_name = location.get('country_name')
                user.city = location.get('city')
                user.region_group = 'africa' if is_african_user(user.country) else 'global'
                if old_country != user.country:
                    logger.info(f"User location updated: {old_country} -> {user.country} ({user.region_group})")
        
        db.commit()

        # Track login event
        track_event(
            db=db,
            event_type=EventType.LOGIN,
            user_id=str(user.id),
            event_data={"email": req.email},
            request=request
        )

        logger.info(f"Generating access token for user: {user.id}")
        access_token = create_access_token({"sub": str(user.id)})

        logger.info(f"=== LOGIN SUCCESS === User ID: {user.id}, Email: {req.email}")
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== LOGIN ERROR === Email: {req.email}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


# ============= OAuth Authentication (Supabase) =============

class OAuthSyncRequest(BaseModel):
    token: str
    provider: str = "google"


def verify_supabase_token(token: str) -> Optional[dict]:
    """
    Verify Supabase JWT token and extract user info.
    For production, you should verify against Supabase's JWT secret.
    """
    try:
        if SUPABASE_JWT_SECRET:
            # Supabase JWT secret is base64 encoded - decode it first
            try:
                secret_key = base64.b64decode(SUPABASE_JWT_SECRET)
            except Exception:
                # If base64 decode fails, use as-is (might be raw secret)
                secret_key = SUPABASE_JWT_SECRET
            
            # First decode header to check algorithm
            try:
                unverified_header = jwt.get_unverified_header(token)
                token_alg = unverified_header.get('alg', 'HS256')
                logger.info(f"Token algorithm: {token_alg}")
            except Exception as e:
                logger.warning(f"Could not read token header: {e}")
                token_alg = 'HS256'
            
            logger.info(f"Verifying token with secret (length: {len(str(secret_key))}), alg: {token_alg}")
            
            payload = jwt.decode(
                token,
                secret_key,
                algorithms=[token_alg, "HS256", "HS384", "HS512"],
                audience="authenticated"
            )
        else:
            # Development: decode without verification (not recommended for production)
            logger.warning("SUPABASE_JWT_SECRET not set - skipping signature verification")
            payload = jwt.decode(token, options={"verify_signature": False})
        
        logger.info(f"Token verified successfully for email: {payload.get('email')}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Supabase token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Supabase token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error verifying Supabase token: {e}")
        return None


@router.post("/oauth-sync")
def oauth_sync(req: OAuthSyncRequest, request: Request, db: Session = Depends(get_db)):
    """
    Sync OAuth user (from Supabase) with our database.
    Creates user if not exists, or returns token for existing user.
    """
    logger.info(f"=== OAUTH SYNC START === Provider: {req.provider}")
    
    try:
        # Verify Supabase token
        payload = verify_supabase_token(req.token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OAuth token"
            )
        
        # Extract email from token
        email = payload.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not found in OAuth token"
            )
        
        logger.info(f"OAuth sync for email: {email}")
        
        # Check if user exists
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            # User exists - update auth provider if needed and return token
            logger.info(f"Existing user found: {user.id}")
            if user.auth_provider != req.provider:
                user.auth_provider = req.provider
            user.is_verified = True  # OAuth users are verified
            user.last_login_at = datetime.utcnow()
            db.commit()
        else:
            # Create new user
            logger.info(f"Creating new OAuth user: {email}")
            
            # Get location
            client_ip = get_client_ip(request)
            location = get_location_from_ip(client_ip)
            country_code = location.get('country')
            region_group = 'africa' if is_african_user(country_code) else 'global'
            
            user = User(
                email=email,
                password_hash=None,  # OAuth users don't have passwords
                auth_provider=req.provider,
                is_admin=False,
                is_verified=True,
                onboarding_completed=False,
                onboarding_step=0,
                country=country_code,
                country_name=location.get('country_name'),
                city=location.get('city'),
                signup_ip=client_ip,
                region_group=region_group
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # Track signup
            track_event(
                db=db,
                event_type=EventType.SIGNUP,
                user_id=str(user.id),
                event_data={"email": email, "provider": req.provider},
                request=request
            )
        
        # Generate our backend token
        access_token = create_access_token({"sub": str(user.id)})
        
        logger.info(f"=== OAUTH SYNC SUCCESS === User ID: {user.id}")
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "is_new_user": user.created_at and (datetime.utcnow() - user.created_at).seconds < 60
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== OAUTH SYNC ERROR === Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth sync failed: {str(e)}"
        )
