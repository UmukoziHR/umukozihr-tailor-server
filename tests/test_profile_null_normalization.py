#!/usr/bin/env python3
import os
import sys

# Add server root to import path (matches existing test style in this repo)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.linkedin_scraper import map_linkedin_to_profile_v3
from app.models import Education


def test_education_model_coerces_null_text_fields_to_empty_string():
    edu = Education(
        school=None,
        degree=None,
        start=None,
        end=None,
        gpa=None,
    )

    assert edu.school == ""
    assert edu.degree == ""
    assert edu.start == ""
    assert edu.end == ""
    assert edu.gpa is None


def test_linkedin_mapper_never_returns_null_degree_or_school():
    linkedin_payload = {
        "education": [
            {
                "schoolName": None,
                "degree": None,
                "fieldOfStudy": None,
                "startDate": {"year": None},
                "endDate": {"year": None},
                "grade": None,
            }
        ]
    }

    mapped = map_linkedin_to_profile_v3(linkedin_payload)
    edu = mapped["education"][0]

    assert edu["school"] == ""
    assert edu["degree"] == ""
    assert edu["start"] == ""
    assert edu["end"] == ""
    assert edu["gpa"] is None
