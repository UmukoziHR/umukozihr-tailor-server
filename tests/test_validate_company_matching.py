#!/usr/bin/env python3
import os
import sys

import pytest

# Add server root to import path (matches existing test style in this repo)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.validate import business_rules_check
from app.models import Profile, Role


def _profile_with_company(company: str) -> Profile:
    return Profile(
        name="Test User",
        experience=[
            Role(
                title="Engineer",
                company=company,
                start="2020-01",
                end="2023-01",
                bullets=["Built backend services"],
            )
        ],
    )


def _llm_data_with_company(company: str) -> dict:
    return {
        "resume": {
            "experience": [
                {
                    "title": "Engineer",
                    "company": company,
                    "start": "2020-01",
                    "end": "2023-01",
                    "bullets": ["Built backend services"],
                }
            ]
        }
    }


def test_business_rules_accepts_case_only_company_difference():
    profile = _profile_with_company("VALUE CHAIN FACTORY")
    llm_data = _llm_data_with_company("Value Chain Factory")

    # Should not raise.
    business_rules_check(llm_data, profile)


def test_business_rules_accepts_punctuation_and_spacing_difference():
    profile = _profile_with_company("Value-Chain   Factory, Ltd.")
    llm_data = _llm_data_with_company("value chain factory ltd")

    # Should not raise.
    business_rules_check(llm_data, profile)


def test_business_rules_still_rejects_unknown_company():
    profile = _profile_with_company("Value Chain Factory")
    llm_data = _llm_data_with_company("Completely Different Co")

    with pytest.raises(ValueError, match="company not in profile"):
        business_rules_check(llm_data, profile)
