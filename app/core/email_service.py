"""
Email Service for UmukoziHR Resume Tailor
High-converting engagement emails using Resend

Psychology Tactics Used:
- Loss aversion ("Don't lose your progress")
- Social proof ("Join 10,000+ users")
- Urgency ("Your resume is waiting")
- Progress motivation (streaks, XP)
- Celebration (achievements, job landed)
"""

import os
import logging
import hashlib
import hmac
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

import resend

logger = logging.getLogger(__name__)

# Initialize Resend
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "UmukoziHR <notifications@umukozihr.com>")
UNSUBSCRIBE_SECRET = os.getenv("UNSUBSCRIBE_SECRET", "umukozihr-unsubscribe-2024")
APP_URL = os.getenv("APP_URL", "https://tailor.umukozihr.com")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY
    logger.info("Resend API initialized")
else:
    logger.warning("RESEND_API_KEY not set - emails will not be sent")


def generate_unsubscribe_token(user_id: str) -> str:
    """Generate a secure unsubscribe token for a user"""
    message = f"{user_id}:{UNSUBSCRIBE_SECRET}"
    return hashlib.sha256(message.encode()).hexdigest()[:32]


def verify_unsubscribe_token(user_id: str, token: str) -> bool:
    """Verify an unsubscribe token"""
    expected = generate_unsubscribe_token(user_id)
    return hmac.compare_digest(expected, token)


def get_unsubscribe_url(user_id: str) -> str:
    """Get the unsubscribe URL for a user"""
    token = generate_unsubscribe_token(user_id)
    return f"{APP_URL}/api/v1/auth/unsubscribe?user_id={user_id}&token={token}"


def send_email(
    to: str,
    subject: str,
    html: str,
    plain_text: Optional[str] = None,
    user_id: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Send an email using Resend
    
    Args:
        to: Recipient email address
        subject: Email subject
        html: HTML content
        plain_text: Plain text fallback (auto-generated if not provided)
        user_id: User ID for unsubscribe link
        tags: Tags for email categorization
    
    Returns:
        Resend response dict or None if failed
    """
    if not RESEND_API_KEY:
        logger.warning(f"Email not sent (no API key): {subject} -> {to}")
        return None
    
    try:
        # Add unsubscribe footer if user_id provided
        if user_id:
            unsubscribe_url = get_unsubscribe_url(user_id)
            html = html.replace("{{unsubscribe_url}}", unsubscribe_url)
            if plain_text:
                plain_text = plain_text.replace("{{unsubscribe_url}}", unsubscribe_url)
        
        params = {
            "from": EMAIL_FROM,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        
        if plain_text:
            params["text"] = plain_text
        
        if tags:
            params["tags"] = [{"name": tag, "value": "true"} for tag in tags]
        
        response = resend.Emails.send(params)
        logger.info(f"Email sent: {subject} -> {to}, ID: {response.get('id')}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to send email: {subject} -> {to}, Error: {e}")
        return None


def send_bulk_emails(
    recipients: List[Dict[str, str]],
    subject: str,
    html_template: str,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Send bulk emails with personalization
    
    Args:
        recipients: List of dicts with 'email', 'name', 'user_id', and other variables
        subject: Email subject (can contain {name} placeholder)
        html_template: HTML template with placeholders like {name}, {email}, etc.
        tags: Tags for categorization
    
    Returns:
        Dict with success/failure counts
    """
    results = {"sent": 0, "failed": 0, "errors": []}
    
    for recipient in recipients:
        try:
            # Personalize subject and content
            personalized_subject = subject.format(**recipient)
            personalized_html = html_template.format(**recipient)
            
            # Add unsubscribe URL
            if recipient.get('user_id'):
                unsubscribe_url = get_unsubscribe_url(recipient['user_id'])
                personalized_html = personalized_html.replace("{unsubscribe_url}", unsubscribe_url)
            
            response = send_email(
                to=recipient['email'],
                subject=personalized_subject,
                html=personalized_html,
                user_id=recipient.get('user_id'),
                tags=tags
            )
            
            if response:
                results["sent"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({"email": recipient['email'], "error": "Send failed"})
                
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"email": recipient.get('email', 'unknown'), "error": str(e)})
    
    logger.info(f"Bulk email completed: {results['sent']} sent, {results['failed']} failed")
    return results


# =============================================================================
# Pre-built Email Functions (for common use cases)
# =============================================================================

from app.core.email_templates import (
    get_welcome_email,
    get_onboarding_nudge_email,
    get_first_generation_email,
    get_inactivity_48h_email,
    get_winback_7day_email,
    get_weekly_digest_email,
    get_achievement_email,
    get_interview_celebration_email,
    get_job_landed_email,
    get_broadcast_email
)


def send_welcome_email(email: str, name: str, user_id: str) -> Optional[Dict]:
    """Send welcome email immediately after signup"""
    subject, html = get_welcome_email(name)
    return send_email(to=email, subject=subject, html=html, user_id=user_id, tags=["welcome"])


def send_onboarding_nudge_email(
    email: str, name: str, user_id: str, completeness: int
) -> Optional[Dict]:
    """Send nudge to complete onboarding (24h after signup)"""
    subject, html = get_onboarding_nudge_email(name, completeness)
    return send_email(to=email, subject=subject, html=html, user_id=user_id, tags=["onboarding", "nudge"])


def send_first_generation_email(
    email: str, name: str, user_id: str, company: str, title: str
) -> Optional[Dict]:
    """Send celebration after first resume generation"""
    subject, html = get_first_generation_email(name, company, title)
    return send_email(to=email, subject=subject, html=html, user_id=user_id, tags=["generation", "first"])


def send_inactivity_48h_email(
    email: str, name: str, user_id: str, completeness: int
) -> Optional[Dict]:
    """Send nudge after 48 hours of inactivity"""
    subject, html = get_inactivity_48h_email(name, completeness)
    return send_email(to=email, subject=subject, html=html, user_id=user_id, tags=["inactivity", "48h"])


def send_winback_7day_email(
    email: str, name: str, user_id: str, generations: int
) -> Optional[Dict]:
    """Send win-back email after 7 days of inactivity"""
    subject, html = get_winback_7day_email(name, generations)
    return send_email(to=email, subject=subject, html=html, user_id=user_id, tags=["winback", "7day"])


def send_weekly_digest_email(
    email: str, name: str, user_id: str,
    generations_this_week: int, streak: int, xp: int,
    new_achievements: List[str] = None
) -> Optional[Dict]:
    """Send weekly progress digest (every Monday)"""
    subject, html = get_weekly_digest_email(
        name, generations_this_week, streak, xp, new_achievements or []
    )
    return send_email(to=email, subject=subject, html=html, user_id=user_id, tags=["digest", "weekly"])


def send_achievement_email(
    email: str, name: str, user_id: str,
    achievement_name: str, achievement_description: str, xp_earned: int
) -> Optional[Dict]:
    """Send email when user unlocks an achievement"""
    subject, html = get_achievement_email(name, achievement_name, achievement_description, xp_earned)
    return send_email(to=email, subject=subject, html=html, user_id=user_id, tags=["achievement"])


def send_interview_celebration_email(
    email: str, name: str, user_id: str, company: str, title: str
) -> Optional[Dict]:
    """Send celebration when user marks interview"""
    subject, html = get_interview_celebration_email(name, company, title)
    return send_email(to=email, subject=subject, html=html, user_id=user_id, tags=["interview", "celebration"])


def send_job_landed_email(
    email: str, name: str, user_id: str, company: str, title: str
) -> Optional[Dict]:
    """Send celebration when user lands a job"""
    subject, html = get_job_landed_email(name, company, title)
    return send_email(to=email, subject=subject, html=html, user_id=user_id, tags=["landed", "celebration"])


def send_broadcast_email(
    email: str, name: str, user_id: str,
    subject: str, content: str
) -> Optional[Dict]:
    """Send admin broadcast email to single user"""
    final_subject, html = get_broadcast_email(name, subject, content)
    return send_email(to=email, subject=final_subject, html=html, user_id=user_id, tags=["broadcast"])


def send_broadcast_to_all(
    subject: str,
    body: str,
    html: Optional[str],
    recipients: List[str]
) -> Dict[str, Any]:
    """
    Send broadcast email to multiple recipients
    
    Args:
        subject: Email subject
        body: Plain text body
        html: HTML content (optional, will wrap body in HTML if not provided)
        recipients: List of email addresses
    
    Returns:
        Dict with success stats
    """
    if not RESEND_API_KEY:
        logger.warning(f"Broadcast not sent (no API key): {subject}")
        return {
            "success": False,
            "message": "RESEND_API_KEY not configured",
            "total": len(recipients),
            "successful": 0,
            "failed": len(recipients)
        }
    
    # Generate HTML if not provided
    if not html:
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #FF6B35 0%, #FF8C42 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">UmukoziHR Resume Tailor</h1>
            </div>
            <div style="padding: 30px; background: #ffffff;">
                <p style="color: #333; font-size: 16px; line-height: 1.6;">{body}</p>
            </div>
            <div style="padding: 20px; background: #f8f9fa; text-align: center;">
                <p style="color: #666; font-size: 12px; margin: 0;">
                    © 2024 UmukoziHR. All rights reserved.
                </p>
            </div>
        </div>
        """.replace("{body}", body.replace("\n", "<br>"))
    
    successful = 0
    failed = 0
    
    for email in recipients:
        try:
            response = resend.Emails.send({
                "from": EMAIL_FROM,
                "to": [email],
                "subject": subject,
                "html": html,
                "tags": [{"name": "broadcast", "value": "true"}]
            })
            if response and response.get('id'):
                successful += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {email}: {e}")
            failed += 1
    
    logger.info(f"Broadcast complete: {successful}/{len(recipients)} sent")
    
    return {
        "success": successful > 0,
        "message": f"Broadcast sent to {successful}/{len(recipients)} recipients",
        "total": len(recipients),
        "successful": successful,
        "failed": failed
    }
