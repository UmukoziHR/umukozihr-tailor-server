"""
Gamification System - Achievements & Challenges
UmukoziHR Resume Tailor v1.6

Achievement tiers:
- Tier 1: Getting Started (Free)
- Tier 2: Building Momentum (Free)
- Tier 3: Pro Exclusive (Premium)
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from enum import Enum


class AchievementTier(str, Enum):
    TIER_1 = "tier_1"  # Getting Started (Free)
    TIER_2 = "tier_2"  # Building Momentum (Free)
    TIER_3 = "tier_3"  # Pro Exclusive


# Achievement definitions
ACHIEVEMENTS = {
    # Tier 1 - Getting Started (Free)
    "resume_rookie": {
        "id": "resume_rookie",
        "name": "Resume Rookie",
        "description": "Generate your first tailored resume",
        "icon": "FileText",
        "tier": AchievementTier.TIER_1,
        "xp": 10,
        "requirement": {"type": "applications", "count": 1},
        "color": "#22c55e"  # Green
    },
    "application_machine": {
        "id": "application_machine",
        "name": "Application Machine",
        "description": "Generate 5 tailored resumes",
        "icon": "Rocket",
        "tier": AchievementTier.TIER_1,
        "xp": 25,
        "requirement": {"type": "applications", "count": 5},
        "color": "#3b82f6"  # Blue
    },
    "phone_ringer": {
        "id": "phone_ringer",
        "name": "Phone Ringer",
        "description": "Land your first interview",
        "icon": "Phone",
        "tier": AchievementTier.TIER_1,
        "xp": 50,
        "requirement": {"type": "interviews", "count": 1},
        "color": "#8b5cf6"  # Purple
    },
    "in_demand": {
        "id": "in_demand",
        "name": "In Demand",
        "description": "Receive your first job offer",
        "icon": "Star",
        "tier": AchievementTier.TIER_1,
        "xp": 100,
        "requirement": {"type": "offers", "count": 1},
        "color": "#f59e0b"  # Amber
    },
    "hired": {
        "id": "hired",
        "name": "Hired!",
        "description": "Land your first job",
        "icon": "Trophy",
        "tier": AchievementTier.TIER_1,
        "xp": 200,
        "requirement": {"type": "landed", "count": 1},
        "color": "#eab308"  # Yellow/Gold
    },
    
    # Tier 2 - Building Momentum (Free)
    "seven_day_warrior": {
        "id": "seven_day_warrior",
        "name": "7-Day Warrior",
        "description": "Maintain a 7-day activity streak",
        "icon": "Flame",
        "tier": AchievementTier.TIER_2,
        "xp": 75,
        "requirement": {"type": "streak", "count": 7},
        "color": "#ef4444"  # Red
    },
    "mass_applicant": {
        "id": "mass_applicant",
        "name": "Mass Applicant",
        "description": "Generate 25 tailored resumes",
        "icon": "Layers",
        "tier": AchievementTier.TIER_2,
        "xp": 100,
        "requirement": {"type": "applications", "count": 25},
        "color": "#06b6d4"  # Cyan
    },
    "interview_magnet": {
        "id": "interview_magnet",
        "name": "Interview Magnet",
        "description": "Land 5 interviews",
        "icon": "Magnet",
        "tier": AchievementTier.TIER_2,
        "xp": 150,
        "requirement": {"type": "interviews", "count": 5},
        "color": "#ec4899"  # Pink
    },
    "choice_maker": {
        "id": "choice_maker",
        "name": "Choice Maker",
        "description": "Receive 3 job offers",
        "icon": "CheckCircle2",
        "tier": AchievementTier.TIER_2,
        "xp": 200,
        "requirement": {"type": "offers", "count": 3},
        "color": "#14b8a6"  # Teal
    },
    
    # Tier 3 - Pro Exclusive
    "thirty_day_champion": {
        "id": "thirty_day_champion",
        "name": "30-Day Champion",
        "description": "Maintain a 30-day activity streak",
        "icon": "Crown",
        "tier": AchievementTier.TIER_3,
        "xp": 300,
        "requirement": {"type": "streak", "count": 30},
        "color": "#f97316",  # Orange
        "pro_only": True
    },
    "century_club": {
        "id": "century_club",
        "name": "Century Club",
        "description": "Generate 100 tailored resumes",
        "icon": "Award",
        "tier": AchievementTier.TIER_3,
        "xp": 500,
        "requirement": {"type": "applications", "count": 100},
        "color": "#a855f7",  # Violet
        "pro_only": True
    },
    "interview_master": {
        "id": "interview_master",
        "name": "Interview Master",
        "description": "Land 10 interviews",
        "icon": "Target",
        "tier": AchievementTier.TIER_3,
        "xp": 400,
        "requirement": {"type": "interviews", "count": 10},
        "color": "#84cc16",  # Lime
        "pro_only": True
    },
    "multi_hired": {
        "id": "multi_hired",
        "name": "Multi-Hired",
        "description": "Land 3 different jobs",
        "icon": "Medal",
        "tier": AchievementTier.TIER_3,
        "xp": 1000,
        "requirement": {"type": "landed", "count": 3},
        "color": "#fbbf24",  # Amber/Gold
        "pro_only": True
    }
}


# Weekly challenge pool
WEEKLY_CHALLENGES = [
    {
        "id": "weekly_apply_5",
        "name": "Weekly Applicant",
        "description": "Apply to 5 jobs this week",
        "icon": "Target",
        "type": "applications",
        "target": 5,
        "xp": 50,
        "pro_only": False
    },
    {
        "id": "weekly_apply_3",
        "name": "Resume Builder",
        "description": "Generate 3 tailored resumes",
        "icon": "FileText",
        "type": "applications",
        "target": 3,
        "xp": 30,
        "pro_only": False
    },
    {
        "id": "weekly_profile_update",
        "name": "Profile Perfectionist",
        "description": "Update your profile",
        "icon": "User",
        "type": "profile_update",
        "target": 1,
        "xp": 20,
        "pro_only": False
    },
    {
        "id": "weekly_share_profile",
        "name": "Network Expander",
        "description": "Share your profile link",
        "icon": "Share2",
        "type": "profile_share",
        "target": 1,
        "xp": 25,
        "pro_only": False
    },
    {
        "id": "weekly_batch_10",
        "name": "Power Applicant",
        "description": "Apply to 10 jobs in one session",
        "icon": "Zap",
        "type": "applications",
        "target": 10,
        "xp": 100,
        "pro_only": True
    }
]


# Monthly challenge pool
MONTHLY_CHALLENGES = [
    {
        "id": "monthly_interview",
        "name": "Interview Hunter",
        "description": "Land an interview this month",
        "icon": "Phone",
        "type": "interviews",
        "target": 1,
        "xp": 100,
        "pro_only": False
    },
    {
        "id": "monthly_apply_20",
        "name": "Monthly Marathon",
        "description": "Apply to 20 jobs this month",
        "icon": "Calendar",
        "type": "applications",
        "target": 20,
        "xp": 150,
        "pro_only": False
    },
    {
        "id": "monthly_offer",
        "name": "Offer Chaser",
        "description": "Get a job offer this month",
        "icon": "Gift",
        "type": "offers",
        "target": 1,
        "xp": 200,
        "pro_only": False
    }
]


def get_user_stats(db, user_id: str) -> Dict:
    """Get current stats for a user to check achievements"""
    from sqlalchemy import text
    
    # Get application count
    result = db.execute(
        text("SELECT COUNT(*) FROM runs WHERE user_id = :user_id AND status = 'completed'"),
        {"user_id": user_id}
    )
    applications_count = result.scalar() or 0
    
    # Get user data
    result = db.execute(
        text("""
            SELECT interviews_count, offers_count, landed_job_count,
                   current_streak_days, longest_streak_days, total_xp,
                   achievements_unlocked, subscription_tier
            FROM users WHERE id = :user_id
        """),
        {"user_id": user_id}
    )
    row = result.fetchone()
    
    if not row:
        return {}
    
    return {
        "applications": applications_count,
        "interviews": row[0] or 0,
        "offers": row[1] or 0,
        "landed": row[2] or 0,
        "streak": row[3] or 0,
        "longest_streak": row[4] or 0,
        "total_xp": row[5] or 0,
        "achievements_unlocked": row[6] or [],
        "is_pro": row[7] == "pro"
    }


def check_achievements(stats: Dict) -> Tuple[List[Dict], int]:
    """
    Check which achievements user has earned but not yet unlocked.
    Returns (newly_unlocked_achievements, total_xp_earned)
    """
    already_unlocked = set(stats.get("achievements_unlocked", []))
    is_pro = stats.get("is_pro", False)
    newly_unlocked = []
    total_xp = 0
    
    for achievement_id, achievement in ACHIEVEMENTS.items():
        # Skip if already unlocked
        if achievement_id in already_unlocked:
            continue
        
        # Skip pro-only achievements for free users
        if achievement.get("pro_only") and not is_pro:
            continue
        
        requirement = achievement["requirement"]
        req_type = requirement["type"]
        req_count = requirement["count"]
        
        # Check if requirement is met
        current_count = stats.get(req_type, 0)
        
        if current_count >= req_count:
            newly_unlocked.append(achievement)
            total_xp += achievement["xp"]
    
    return newly_unlocked, total_xp


def update_streak(db, user_id: str) -> Tuple[int, int, bool]:
    """
    Update user's activity streak.
    Returns (current_streak, longest_streak, is_new_milestone)
    """
    from sqlalchemy import text
    
    today = datetime.utcnow().date()
    
    # Get user's last activity date and streak
    result = db.execute(
        text("""
            SELECT last_activity_date, current_streak_days, longest_streak_days
            FROM users WHERE id = :user_id
        """),
        {"user_id": user_id}
    )
    row = result.fetchone()
    
    if not row:
        return 0, 0, False
    
    last_activity = row[0].date() if row[0] else None
    current_streak = row[1] or 0
    longest_streak = row[2] or 0
    
    is_new_milestone = False
    
    if last_activity is None:
        # First activity ever
        current_streak = 1
    elif last_activity == today:
        # Already active today, no change
        pass
    elif last_activity == today - timedelta(days=1):
        # Consecutive day - increment streak
        current_streak += 1
        # Check for milestone (7, 14, 30, 60, 90)
        if current_streak in [7, 14, 30, 60, 90]:
            is_new_milestone = True
    else:
        # Streak broken - reset to 1
        current_streak = 1
    
    # Update longest streak if needed
    if current_streak > longest_streak:
        longest_streak = current_streak
    
    # Update database
    db.execute(
        text("""
            UPDATE users SET 
                last_activity_date = :today,
                current_streak_days = :streak,
                longest_streak_days = :longest
            WHERE id = :user_id
        """),
        {
            "today": today,
            "streak": current_streak,
            "longest": longest_streak,
            "user_id": user_id
        }
    )
    db.commit()
    
    return current_streak, longest_streak, is_new_milestone


def unlock_achievements(db, user_id: str, achievement_ids: List[str], xp_earned: int):
    """Save unlocked achievements and add XP to user"""
    from sqlalchemy import text
    import json
    
    # Get current achievements
    result = db.execute(
        text("SELECT achievements_unlocked, total_xp FROM users WHERE id = :user_id"),
        {"user_id": user_id}
    )
    row = result.fetchone()
    
    current_achievements = row[0] or []
    current_xp = row[1] or 0
    
    # Add new achievements
    updated_achievements = list(set(current_achievements + achievement_ids))
    new_xp = current_xp + xp_earned
    
    # Update database
    db.execute(
        text("""
            UPDATE users SET 
                achievements_unlocked = :achievements,
                total_xp = :xp
            WHERE id = :user_id
        """),
        {
            "achievements": json.dumps(updated_achievements),
            "xp": new_xp,
            "user_id": user_id
        }
    )
    db.commit()


def get_active_challenges(user_id: str, is_pro: bool = False) -> List[Dict]:
    """Get currently active challenges for a user"""
    import random
    from datetime import datetime
    
    today = datetime.utcnow()
    week_number = today.isocalendar()[1]
    month = today.month
    
    # Seed random with week/month for consistent challenges
    random.seed(f"{today.year}-{week_number}")
    
    # Pick 2 weekly challenges (1 free, 1 potentially pro)
    free_weekly = [c for c in WEEKLY_CHALLENGES if not c.get("pro_only")]
    weekly_1 = random.choice(free_weekly)
    
    if is_pro:
        weekly_2 = random.choice(WEEKLY_CHALLENGES)
    else:
        weekly_2 = random.choice(free_weekly)
        while weekly_2["id"] == weekly_1["id"]:
            weekly_2 = random.choice(free_weekly)
    
    # Pick 1 monthly challenge
    random.seed(f"{today.year}-{month}")
    monthly = random.choice(MONTHLY_CHALLENGES)
    
    return [
        {**weekly_1, "period": "weekly", "ends_at": _get_week_end()},
        {**weekly_2, "period": "weekly", "ends_at": _get_week_end()},
        {**monthly, "period": "monthly", "ends_at": _get_month_end()}
    ]


def _get_week_end() -> str:
    """Get end of current week (Sunday) ISO string"""
    today = datetime.utcnow()
    days_until_sunday = 6 - today.weekday()
    week_end = today + timedelta(days=days_until_sunday)
    return week_end.replace(hour=23, minute=59, second=59).isoformat()


def _get_month_end() -> str:
    """Get end of current month ISO string"""
    today = datetime.utcnow()
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return month_end.replace(hour=23, minute=59, second=59).isoformat()


def get_all_achievements() -> List[Dict]:
    """Get all achievements for display"""
    return list(ACHIEVEMENTS.values())


def get_achievement_by_id(achievement_id: str) -> Optional[Dict]:
    """Get a single achievement by ID"""
    return ACHIEVEMENTS.get(achievement_id)
