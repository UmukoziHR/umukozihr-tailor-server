import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import os

from app.models import (
    Profile, ProfileV3, ProfileResponse, ProfileUpdateRequest,
    ProfileUpdateResponse, CompletenessResponse
)
from app.db.database import get_db
from app.db.models import Profile as DBProfile
from app.auth.auth import get_current_user
from app.utils.completeness import calculate_completeness

logger = logging.getLogger(__name__)

router = APIRouter()

# Legacy endpoint (v1.2 - file-based storage)
@router.post("/profile")
def save_profile(profile: Profile):
    """Legacy endpoint for backward compatibility"""
    logger.info(f"Saving profile for: {profile.name}")
    artifact_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "artifacts"))
    os.makedirs(artifact_dir, exist_ok=True)
    path = os.path.join(artifact_dir, f"profile_{profile.name.replace(' ','_')}.json")
    open(path, "w", encoding="utf-8").write(profile.model_dump_json(indent=2))
    logger.info(f"Profile saved successfully to: {path}")
    return {"ok": True, "path": path}


# v1.3 endpoints (database-backed)

@router.get("/profile", response_model=ProfileResponse)
def get_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/profile
    Return saved profile for authenticated user
    """
    user_id = current_user["user_id"]
    logger.info(f"=== GET PROFILE START === User ID: {user_id}")

    try:
        # Convert string UUID to UUID object for database query
        import uuid
        logger.info(f"Converting user ID to UUID: {user_id}")
        try:
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            logger.info(f"UUID conversion successful: {user_uuid}")
        except ValueError as e:
            logger.error(f"Invalid user ID format: {user_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid user ID format")

        logger.info(f"Querying database for profile: user_uuid={user_uuid}")
        db_profile = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()

        if not db_profile:
            logger.warning(f"Profile not found for user: {user_uuid}")
            raise HTTPException(status_code=404, detail="Profile not found. Please complete onboarding.")

        logger.info(f"Profile found: version={db_profile.version}, completeness={db_profile.completeness}")

        # Parse profile_data JSON into ProfileV3
        logger.info(f"Parsing profile data for user: {user_uuid}")
        profile = ProfileV3(**db_profile.profile_data)
        logger.info(f"Profile data parsed successfully")

        logger.info(f"=== GET PROFILE SUCCESS === User: {user_uuid}, Version: {db_profile.version}")
        return ProfileResponse(
            profile=profile,
            version=db_profile.version,
            completeness=db_profile.completeness,
            updated_at=db_profile.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== GET PROFILE ERROR === User: {user_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}")


@router.put("/profile", response_model=ProfileUpdateResponse)
def update_profile(
    request: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    PUT /api/v1/profile
    Update profile with versioning and completeness calculation
    """
    user_id = current_user["user_id"]
    logger.info(f"=== UPDATE PROFILE START === User ID: {user_id}")

    try:
        # Convert string UUID to UUID object
        import uuid
        logger.info(f"Converting user ID to UUID: {user_id}")
        try:
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            logger.info(f"UUID conversion successful: {user_uuid}")
        except ValueError as e:
            logger.error(f"Invalid user ID format: {user_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid user ID format")

        # Calculate completeness
        logger.info(f"Calculating profile completeness for user: {user_uuid}")
        completeness, breakdown, missing = calculate_completeness(request.profile)
        logger.info(f"Profile completeness: {completeness}% - Breakdown: {breakdown}, Missing: {missing}")

        # Check if profile exists
        logger.info(f"Checking if profile exists for user: {user_uuid}")
        db_profile = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()

        if db_profile:
            # Update existing profile
            logger.info(f"Updating existing profile - current version: {db_profile.version}")
            db_profile.profile_data = request.profile.model_dump(mode="json")
            db_profile.version += 1
            db_profile.completeness = completeness
            db_profile.updated_at = datetime.utcnow()
            message = f"Profile updated successfully to version {db_profile.version}"
            logger.info(f"Profile updated to version {db_profile.version}")
        else:
            # Create new profile
            logger.info(f"Creating new profile for user: {user_uuid}")
            db_profile = DBProfile(
                user_id=user_uuid,
                profile_data=request.profile.model_dump(mode="json"),
                version=1,
                completeness=completeness,
                updated_at=datetime.utcnow()
            )
            db.add(db_profile)
            message = "Profile created successfully"
            logger.info(f"New profile created for user: {user_uuid}")

        logger.info(f"Committing profile to database for user: {user_uuid}")
        db.commit()

        logger.info(f"Refreshing profile object for user: {user_uuid}")
        db.refresh(db_profile)

        logger.info(f"=== UPDATE PROFILE SUCCESS === User: {user_uuid}, Version: {db_profile.version}, Completeness: {completeness}%")

        return ProfileUpdateResponse(
            success=True,
            version=db_profile.version,
            completeness=db_profile.completeness,
            message=message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== UPDATE PROFILE ERROR === User: {user_id}, Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@router.get("/me/completeness", response_model=CompletenessResponse)
def get_completeness(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/me/completeness
    Calculate and return profile completeness with breakdown
    """
    user_id = current_user["user_id"]
    logger.info(f"=== GET COMPLETENESS START === User ID: {user_id}")

    try:
        # Convert string UUID to UUID object for database query
        import uuid
        logger.info(f"Converting user ID to UUID: {user_id}")
        try:
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            logger.info(f"UUID conversion successful: {user_uuid}")
        except ValueError as e:
            logger.error(f"Invalid user ID format: {user_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid user ID format")

        logger.info(f"Querying database for profile: user_uuid={user_uuid}")
        db_profile = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()

        if not db_profile:
            logger.warning(f"No profile found for user: {user_uuid} - returning 0% completeness")
            return CompletenessResponse(
                completeness=0.0,
                breakdown={},
                missing_fields=["Complete onboarding to create your profile"]
            )

        logger.info(f"Profile found, parsing data for user: {user_uuid}")
        profile = ProfileV3(**db_profile.profile_data)

        logger.info(f"Calculating completeness for user: {user_uuid}")
        completeness, breakdown, missing = calculate_completeness(profile)

        logger.info(f"=== GET COMPLETENESS SUCCESS === User: {user_uuid}, Completeness: {completeness}%, Missing: {len(missing)} fields")

        return CompletenessResponse(
            completeness=completeness,
            breakdown=breakdown,
            missing_fields=missing
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== GET COMPLETENESS ERROR === User: {user_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get completeness: {str(e)}")