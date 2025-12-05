"""
Profile completeness calculator for v1.3
Scoring: basics(20%) + experience(40%) + education(15%) + projects(10%) + skills(10%) + links(5%)
"""
from typing import Dict, List, Tuple
from app.models import ProfileV3


def calculate_completeness(profile: ProfileV3) -> Tuple[float, Dict[str, float], List[str]]:
    """
    Calculate profile completeness percentage

    Returns:
        - completeness: float (0-100)
        - breakdown: dict of section scores
        - missing_fields: list of recommended fields to fill
    """
    scores = {}
    missing = []

    # Basics (20%)
    basics_score = 0.0
    basics_fields = {
        "full_name": 5,
        "headline": 3,
        "summary": 5,
        "location": 2,
        "email": 3,
        "phone": 2
    }

    for field, weight in basics_fields.items():
        value = getattr(profile.basics, field, "")
        if value and value.strip():
            basics_score += weight
        else:
            missing.append(f"basics.{field}")

    scores["basics"] = (basics_score / 20) * 20  # Normalize to 20%

    # Experience (40%)
    if len(profile.experience) > 0:
        exp_quality = 0
        for exp in profile.experience:
            # Has required fields
            if exp.title and exp.company:
                exp_quality += 10
            # Has dates
            if exp.start:
                exp_quality += 2
            # Has bullets
            if len(exp.bullets) >= 2:
                exp_quality += 8
            elif len(exp.bullets) == 1:
                exp_quality += 4

        # Cap at 40% max
        scores["experience"] = min(40, exp_quality)
    else:
        scores["experience"] = 0
        missing.append("experience (add at least 1 role)")

    # Education (15%)
    if len(profile.education) > 0:
        edu_quality = 0
        for edu in profile.education:
            if edu.school and edu.degree:
                edu_quality += 15
                break  # At least one complete education = full points

        scores["education"] = min(15, edu_quality)
    else:
        scores["education"] = 0
        missing.append("education (add at least 1 entry)")

    # Projects (10%)
    if len(profile.projects) > 0:
        proj_quality = 0
        for proj in profile.projects:
            if proj.name:
                proj_quality += 5
            if len(proj.bullets) >= 2:
                proj_quality += 5

        scores["projects"] = min(10, proj_quality)
    else:
        scores["projects"] = 0
        missing.append("projects (add at least 1 project)")

    # Skills (10%)
    if len(profile.skills) >= 5:
        scores["skills"] = 10
    elif len(profile.skills) >= 3:
        scores["skills"] = 7
    elif len(profile.skills) >= 1:
        scores["skills"] = 4
    else:
        scores["skills"] = 0
        missing.append("skills (add at least 5 skills)")

    # Links & Extras (5%)
    links_score = 0
    if len(profile.basics.links) > 0:
        links_score += 2
    if profile.basics.website:
        links_score += 1
    if len(profile.certifications) > 0:
        links_score += 1
    if len(profile.languages) > 0:
        links_score += 1

    scores["links"] = min(5, links_score)

    if links_score < 5:
        missing.append("links, certifications, or languages")

    # Total completeness
    total = sum(scores.values())

    return round(total, 1), scores, missing
