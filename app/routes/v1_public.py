"""
v1.4 Public Profile Routes - Shareable Profiles for Viral Growth

Endpoints:
- GET /api/v1/p/{username} - View public profile (no auth required)

Note: Share endpoints (/profile/share) are now in v1_profile.py to avoid routing conflicts.
"""
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models import ProfileV3, PublicProfileResponse
from app.db.database import get_db
from app.db.models import Profile as DBProfile, User, UserEvent

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# Public Endpoint (No Auth Required)
# ============================================

@router.get("/p/{username}", response_model=PublicProfileResponse)
def get_public_profile(
    username: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/p/{username}
    View a public profile - NO AUTHENTICATION REQUIRED
    This is the viral endpoint that gets shared on social media.
    """
    logger.info(f"=== PUBLIC PROFILE VIEW === Username: {username}")

    try:
        # Find user by username
        user = db.query(User).filter(User.username == username).first()

        if not user:
            logger.warning(f"Profile not found: {username}")
            raise HTTPException(status_code=404, detail="Profile not found")

        # Check if profile is public
        if not user.is_public:
            logger.warning(f"Profile is private: {username}")
            raise HTTPException(status_code=403, detail="This profile is private")

        # Get profile data
        db_profile = db.query(DBProfile).filter(DBProfile.user_id == user.id).first()

        if not db_profile:
            logger.warning(f"No profile data for user: {username}")
            raise HTTPException(status_code=404, detail="Profile not found")

        # Increment view counter
        user.profile_views = (user.profile_views or 0) + 1
        db.commit()

        # Track profile view event (for analytics)
        try:
            new_event = UserEvent(
                user_id=user.id,
                event_type="profile_view",
                event_data={
                    "username": username,
                    "viewer_ip": request.client.host if request.client else None,
                    "referrer": request.headers.get("referer"),
                    "user_agent": request.headers.get("user-agent")
                }
            )
            db.add(new_event)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to track view event: {e}")

        # Parse profile data
        profile = ProfileV3(**db_profile.profile_data)

        logger.info(f"=== PUBLIC PROFILE SUCCESS === {username}, Views: {user.profile_views}")

        return PublicProfileResponse(
            username=username,
            profile=profile,
            completeness=db_profile.completeness or 0.0,
            profile_views=user.profile_views or 0,
            member_since=user.created_at.strftime("%B %Y") if user.created_at else "2024",
            is_available_for_hire=True  # Could be configurable later
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== PUBLIC PROFILE ERROR === {username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load profile")
