import logging
import re
import uuid
import urllib.parse
import os
import io
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime
from PIL import Image
import boto3
from botocore.exceptions import NoCredentialsError

from app.models import (
    Profile, ProfileV3, ProfileResponse, ProfileUpdateRequest,
    ProfileUpdateResponse, CompletenessResponse,
    ShareSettingsRequest, ShareSettingsResponse, ShareLinksResponse
)
from app.db.database import get_db
from app.db.models import Profile as DBProfile, User, Job, Run, UserEvent, GenerationMetric
from app.auth.auth import get_current_user
from app.utils.completeness import calculate_completeness
from app.utils.analytics import track_event, EventType

logger = logging.getLogger(__name__)

router = APIRouter()

# Base URL for profiles (production)
PROFILE_BASE_URL = "https://tailor.umukozihr.com/p"
BRAND_EMAIL = "tailor@umukozihr.com"

# Legacy endpoint (v1.2 - file-based storage)
@router.post("/")
def save_profile(profile: Profile):
    """Legacy endpoint for backward compatibility"""
    logger.info(f"Saving profile for: {profile.name}")
    artifact_dir = os.environ.get("ARTIFACTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "artifacts")))
    os.makedirs(artifact_dir, exist_ok=True)
    path = os.path.join(artifact_dir, f"profile_{profile.name.replace(' ','_')}.json")
    open(path, "w", encoding="utf-8").write(profile.model_dump_json(indent=2))
    logger.info(f"Profile saved successfully to: {path}")
    return {"ok": True, "path": path}


# v1.3 endpoints (database-backed)

@router.get("/", response_model=ProfileResponse)
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


@router.put("/", response_model=ProfileUpdateResponse)
def update_profile(
    request: ProfileUpdateRequest,
    http_request: Request,
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

        is_new_profile = db_profile is None

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

        # Update user onboarding status if profile is substantial
        if completeness >= 50:
            user = db.query(User).filter(User.id == user_uuid).first()
            if user and not user.onboarding_completed:
                user.onboarding_completed = True
                db.commit()
                
                # Track onboarding complete event
                track_event(
                    db=db,
                    event_type=EventType.ONBOARDING_COMPLETE,
                    user_id=user_id,
                    event_data={"completeness": completeness},
                    request=http_request
                )

        # Track profile update event
        track_event(
            db=db,
            event_type=EventType.PROFILE_UPDATE,
            user_id=user_id,
            event_data={
                "version": db_profile.version,
                "completeness": completeness,
                "is_new": is_new_profile
            },
            request=http_request
        )

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


# ============================================
# Shareable Profiles (v1.4)
# ============================================

def generate_username(full_name: str, user_id: str) -> str:
    """Generate a unique username from full name"""
    # Normalize name: lowercase, remove special chars, replace spaces with dashes
    base = re.sub(r'[^a-z0-9\s-]', '', full_name.lower())
    base = re.sub(r'\s+', '-', base.strip())
    if not base:
        base = "user"
    # Add short UUID suffix for uniqueness
    suffix = user_id[:6] if user_id else uuid.uuid4().hex[:6]
    return f"{base}-{suffix}"


def ensure_username(db: Session, user: User, profile_data: dict) -> str:
    """Ensure user has a username, create one if not"""
    if user.username:
        return user.username
    
    # Generate from profile name
    full_name = profile_data.get('basics', {}).get('full_name', '')
    username = generate_username(full_name, str(user.id))
    
    # Ensure uniqueness
    while db.query(User).filter(User.username == username).first():
        username = generate_username(full_name, uuid.uuid4().hex[:8])
    
    user.username = username
    db.commit()
    return username


@router.get("/share", response_model=ShareLinksResponse)
def get_share_links(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/profile/share
    Get pre-formatted share links for all platforms
    """
    user_id = current_user["user_id"]
    logger.info(f"=== GET SHARE LINKS === User: {user_id}")

    try:
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        user = db.query(User).filter(User.id == user_uuid).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        db_profile = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()

        if not db_profile:
            raise HTTPException(status_code=404, detail="Profile not found. Complete onboarding first.")

        username = ensure_username(db, user, db_profile.profile_data)
        profile_url = f"{PROFILE_BASE_URL}/{username}"

        profile_data = db_profile.profile_data
        name = profile_data.get('basics', {}).get('full_name', 'I')
        first_name = name.split()[0] if name else 'I'

        linkedin_text = f"I just created my professional profile on UmukoziHR Tailor - the AI-powered resume builder for Africa's talent. Check it out!\n\n{profile_url}\n\n#Career #Resume #Africa #UmukoziHR"
        twitter_text = f"Just created my professional profile on @UmukoziHR Tailor!\n\n{profile_url}\n\n#CareerGrowth #AfricaTech"
        whatsapp_text = f"Hey! Check out my professional profile on UmukoziHR Tailor\n\n{profile_url}\n\nCreate your own free profile here: tailor.umukozihr.com"
        telegram_text = f"Check out my professional profile!\n\n{profile_url}\n\nGet your free AI-powered resume at tailor.umukozihr.com"
        email_subject = f"{first_name}'s Professional Profile - UmukoziHR Tailor"
        email_body = f"""Hi there,

I wanted to share my professional profile with you! You can view it here:

{profile_url}

UmukoziHR Tailor is an AI-powered platform that helps professionals create beautiful, tailored resumes.

Create your own free profile at: tailor.umukozihr.com

Best regards,
{name}

---
Get your profile at tailor.umukozihr.com
Questions? Contact us: {BRAND_EMAIL}
"""
        copy_text = f"Check out my professional profile: {profile_url}\n\nCreate your own at tailor.umukozihr.com"

        logger.info(f"=== SHARE LINKS SUCCESS === Username: {username}")

        return ShareLinksResponse(
            profile_url=profile_url,
            linkedin=f"https://www.linkedin.com/sharing/share-offsite/?url={urllib.parse.quote(profile_url)}",
            twitter=f"https://twitter.com/intent/tweet?text={urllib.parse.quote(twitter_text)}",
            whatsapp=f"https://wa.me/?text={urllib.parse.quote(whatsapp_text)}",
            telegram=f"https://t.me/share/url?url={urllib.parse.quote(profile_url)}&text={urllib.parse.quote(telegram_text)}",
            email_subject=email_subject,
            email_body=email_body,
            copy_text=copy_text
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== GET SHARE LINKS ERROR === User: {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate share links")


@router.put("/share", response_model=ShareSettingsResponse)
def update_share_settings(
    request: ShareSettingsRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    PUT /api/v1/profile/share
    Update profile privacy settings
    """
    user_id = current_user["user_id"]
    logger.info(f"=== UPDATE SHARE SETTINGS === User: {user_id}, is_public: {request.is_public}")

    try:
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        user = db.query(User).filter(User.id == user_uuid).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        db_profile = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()

        if not db_profile:
            raise HTTPException(status_code=404, detail="Profile not found. Complete onboarding first.")

        username = ensure_username(db, user, db_profile.profile_data)
        user.is_public = request.is_public
        db.commit()

        profile_url = f"{PROFILE_BASE_URL}/{username}"
        message = "Profile is now public and shareable!" if request.is_public else "Profile is now private."

        logger.info(f"=== UPDATE SHARE SETTINGS SUCCESS === Username: {username}, is_public: {request.is_public}")

        return ShareSettingsResponse(
            success=True,
            is_public=user.is_public,
            username=username,
            profile_url=profile_url,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== UPDATE SHARE SETTINGS ERROR === User: {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update share settings")


@router.get("/share/settings")
def get_share_settings(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/profile/share/settings
    Get current share settings (is_public, username, views)
    """
    user_id = current_user["user_id"]
    logger.info(f"=== GET SHARE SETTINGS === User: {user_id}")

    try:
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        user = db.query(User).filter(User.id == user_uuid).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        db_profile = db.query(DBProfile).filter(DBProfile.user_id == user_uuid).first()

        username = user.username
        if not username and db_profile:
            username = ensure_username(db, user, db_profile.profile_data)

        profile_url = f"{PROFILE_BASE_URL}/{username}" if username else None

        return {
            "is_public": user.is_public if hasattr(user, 'is_public') and user.is_public is not None else True,
            "username": username,
            "profile_url": profile_url,
            "profile_views": user.profile_views or 0
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== GET SHARE SETTINGS ERROR === User: {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get share settings")


# ============================================
# Delete Profile (v1.5)
# ============================================

@router.delete("/")
def delete_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    DELETE /api/v1/profile
    Permanently delete user profile and account
    """
    user_id = current_user["user_id"]
    logger.info(f"=== DELETE PROFILE START === User: {user_id}")

    try:
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        
        # Delete all related records first (foreign key constraints)
        # Order matters - delete children before parents
        
        # Delete generation metrics (references runs and users)
        db.query(GenerationMetric).filter(GenerationMetric.user_id == user_uuid).delete()
        logger.info(f"Deleted generation metrics for user: {user_uuid}")
        
        # Delete runs (references jobs and users)
        db.query(Run).filter(Run.user_id == user_uuid).delete()
        logger.info(f"Deleted runs for user: {user_uuid}")
        
        # Delete jobs
        db.query(Job).filter(Job.user_id == user_uuid).delete()
        logger.info(f"Deleted jobs for user: {user_uuid}")
        
        # Delete user events
        db.query(UserEvent).filter(UserEvent.user_id == user_uuid).delete()
        logger.info(f"Deleted user events for user: {user_uuid}")
        
        # Delete profile
        db.query(DBProfile).filter(DBProfile.user_id == user_uuid).delete()
        logger.info(f"Deleted profile for user: {user_uuid}")
        
        # Finally delete user
        db.query(User).filter(User.id == user_uuid).delete()
        logger.info(f"Deleted user account: {user_uuid}")
        
        db.commit()
        
        logger.info(f"=== DELETE PROFILE SUCCESS === User: {user_uuid}")
        return {
            "success": True,
            "message": "Your profile and account have been permanently deleted."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== DELETE PROFILE ERROR === User: {user_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete profile")


# ============================================
# Avatar Upload (v1.5)
# ============================================

AVATAR_MAX_SIZE = 5 * 1024 * 1024  # 5MB
AVATAR_ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
AVATAR_SIZE = (256, 256)  # Output size


def upload_avatar_to_s3(image_bytes: bytes, user_id: str, content_type: str) -> str:
    """
    Upload avatar to S3 with public access.
    Returns permanent public URL.
    """
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        bucket = os.getenv('S3_BUCKET', 'umukozihr-artifacts')
        region = os.getenv('AWS_REGION', 'us-east-1')
        
        # File extension from content type
        ext_map = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif'}
        ext = ext_map.get(content_type, 'jpg')
        
        s3_key = f"avatars/{user_id}.{ext}"
        
        # Upload with public-read ACL
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=image_bytes,
            ContentType=content_type,
            ACL='public-read',
            CacheControl='max-age=31536000'  # 1 year cache
        )
        
        # Return permanent public URL
        url = f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
        logger.info(f"Avatar uploaded to S3: {url}")
        return url
        
    except NoCredentialsError:
        logger.warning("S3 credentials not configured - using local fallback")
        return None
    except Exception as e:
        logger.error(f"S3 avatar upload error: {e}")
        return None


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/profile/avatar
    Upload user profile picture
    """
    user_id = current_user["user_id"]
    logger.info(f"=== AVATAR UPLOAD START === User: {user_id}")
    
    try:
        # Validate content type
        if file.content_type not in AVATAR_ALLOWED_TYPES:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: JPEG, PNG, WebP, GIF"
            )
        
        # Read file
        contents = await file.read()
        
        # Validate size
        if len(contents) > AVATAR_MAX_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Maximum 5MB.")
        
        # Process image with PIL - resize and optimize
        try:
            img = Image.open(io.BytesIO(contents))
            
            # Convert to RGB if necessary (for PNG with alpha)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize to square, crop center if needed
            width, height = img.size
            min_dim = min(width, height)
            left = (width - min_dim) // 2
            top = (height - min_dim) // 2
            img = img.crop((left, top, left + min_dim, top + min_dim))
            img = img.resize(AVATAR_SIZE, Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            processed_bytes = output.getvalue()
            
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Upload to S3
        avatar_url = upload_avatar_to_s3(processed_bytes, user_id, 'image/jpeg')
        
        if not avatar_url:
            # Fallback: store locally (not ideal for production)
            raise HTTPException(
                status_code=500, 
                detail="Image storage not configured. Please contact support."
            )
        
        # Update user record
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.avatar_url = avatar_url
        db.commit()
        
        logger.info(f"=== AVATAR UPLOAD SUCCESS === User: {user_id}, URL: {avatar_url}")
        
        return {
            "success": True,
            "avatar_url": avatar_url,
            "message": "Profile picture uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== AVATAR UPLOAD ERROR === User: {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload profile picture")


@router.delete("/avatar")
def delete_avatar(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    DELETE /api/v1/profile/avatar
    Remove user profile picture
    """
    user_id = current_user["user_id"]
    logger.info(f"=== AVATAR DELETE === User: {user_id}")
    
    try:
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.avatar_url = None
        db.commit()
        
        return {
            "success": True,
            "message": "Profile picture removed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== AVATAR DELETE ERROR === User: {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove profile picture")


@router.get("/avatar")
def get_avatar(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/profile/avatar
    Get current user's avatar URL
    """
    user_id = current_user["user_id"]
    
    try:
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        user = db.query(User).filter(User.id == user_uuid).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "avatar_url": user.avatar_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get avatar error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get avatar")