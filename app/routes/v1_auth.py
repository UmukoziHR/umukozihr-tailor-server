import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.db.database import get_db
from app.db.models import User
from app.auth.auth import hash_password, verify_password, create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/signup")
def signup(req: SignupRequest, db: Session = Depends(get_db)):
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

        # Create user
        logger.info(f"Creating user object for: {req.email}")
        user = User(
            email=req.email,
            password_hash=hashed_password
        )

        logger.info(f"Adding user to database session: {req.email}")
        db.add(user)

        logger.info(f"Committing user to database: {req.email}")
        db.commit()

        logger.info(f"Refreshing user object: {req.email}")
        db.refresh(user)

        logger.info(f"User created successfully: {req.email} with ID: {user.id}")

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
def login(req: LoginRequest, db: Session = Depends(get_db)):
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