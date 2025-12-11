from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import os
import hashlib
import uuid
import logging

logger = logging.getLogger(__name__)

SECRET_KEY = os.environ.get("SECRET_KEY", "secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

security = HTTPBearer()

# Use SHA256 for testing if bcrypt is problematic
try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    logger.info("Bcrypt password context initialized successfully")
except Exception as e:
    logger.warning(f"Bcrypt initialization failed: {e}, will use SHA256 fallback")
    pwd_context = None

def hash_password(password: str) -> str:
    """Hash password using bcrypt or SHA256 fallback"""
    logger.debug(f"Hashing password, length: {len(password)}")

    # Fallback to SHA256 if bcrypt fails
    if pwd_context:
        try:
            hashed = pwd_context.hash(password)
            logger.debug(f"Password hashed using bcrypt, hash length: {len(hashed)}")
            return hashed
        except Exception as e:
            logger.warning(f"Bcrypt hashing failed: {e}, falling back to SHA256")

    # Simple SHA256 fallback for testing
    hashed = hashlib.sha256(password.encode()).hexdigest()
    logger.debug(f"Password hashed using SHA256, hash length: {len(hashed)}")
    return hashed

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash using bcrypt or SHA256 fallback"""
    logger.debug(f"Verifying password, plain length: {len(plain_password)}, hash length: {len(hashed_password)}")

    if pwd_context:
        try:
            result = pwd_context.verify(plain_password, hashed_password)
            logger.debug(f"Password verification using bcrypt: {result}")
            return result
        except Exception as e:
            logger.warning(f"Bcrypt verification failed: {e}, falling back to SHA256")

    # Simple SHA256 verification for testing
    result = hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
    logger.debug(f"Password verification using SHA256: {result}")
    return result

def create_access_token(data: dict):
    """Create JWT access token"""
    logger.info(f"Creating access token for data: {data.keys()}")

    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    logger.debug(f"Token expiration set to: {expire} ({ACCESS_TOKEN_EXPIRE_MINUTES} minutes from now)")

    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(f"Access token created successfully, length: {len(encoded_jwt)}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create access token: {e}", exc_info=True)
        raise

def verify_token(token: str):
    """Verify and decode JWT token"""
    logger.debug(f"Verifying token, length: {len(token)}")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug(f"Token verified successfully, payload keys: {payload.keys()}")
        return payload
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}", exc_info=True)
        return None

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(lambda: None)  # Will be overridden by actual dependency
):
    """
    Dependency to get current authenticated user
    Raises HTTPException if token is invalid
    Returns dict with user_id
    """
    logger.debug("Getting current user from credentials")

    token = credentials.credentials
    logger.debug(f"Extracted token from credentials, length: {len(token)}")

    payload = verify_token(token)

    if not payload:
        logger.warning("Token verification failed - invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        logger.warning("Token payload missing 'sub' field")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"User authenticated successfully: {user_id}")
    return {"user_id": user_id}