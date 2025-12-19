import logging
import httpx
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.db.database import get_db
from app.db.models import User
from app.auth.auth import hash_password, verify_password, create_access_token
from app.utils.analytics import track_event, EventType
from app.core.subscription import is_african_user

logger = logging.getLogger(__name__)

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
    """Get country/city from IP using free geolocation API"""
    try:
        # Skip localhost/private IPs
        if ip in ['127.0.0.1', 'localhost', 'unknown'] or ip.startswith('10.') or ip.startswith('192.168.'):
            return {'country': None, 'country_name': None, 'city': None}
        
        # Use ip-api.com (free, no API key needed, 45 requests/minute)
        response = httpx.get(f'http://ip-api.com/json/{ip}?fields=status,country,countryCode,city', timeout=3.0)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return {
                    'country': data.get('countryCode'),  # 2-letter code like 'GH', 'US'
                    'country_name': data.get('country'),  # Full name like 'Ghana', 'United States'
                    'city': data.get('city')
                }
    except Exception as e:
        logger.warning(f"Failed to get location for IP {ip}: {e}")
    
    return {'country': None, 'country_name': None, 'city': None}

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

        # Update last login timestamp
        user.last_login_at = datetime.utcnow()
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