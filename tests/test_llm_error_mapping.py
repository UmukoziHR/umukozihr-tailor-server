#!/usr/bin/env python3
import asyncio
import importlib
import json
import os
import sys
import types

from fastapi import HTTPException
from fastapi import APIRouter
from pydantic import BaseModel
from starlette.requests import Request

# Add server root to import path (matches existing test style in this repo)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.llm import LLMQuotaExceededError, classify_llm_exception


class DummyGeminiQuotaError(Exception):
    def __init__(self):
        self.code = 429
        self.status = "RESOURCE_EXHAUSTED"
        self.details = {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": (
                    "You exceeded your current quota. "
                    "Please retry in 44.143569955s."
                ),
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "44.143569955s",
                    }
                ],
            }
        }
        super().__init__(f"{self.code} {self.status}. {self.details}")


def _load_http_exception_handler():
    for module_name in [
        "app.routes.v1_profile",
        "app.routes.v1_generate",
        "app.routes.v1_auth",
        "app.routes.v1_history",
        "app.routes.v1_admin",
        "app.routes.v1_public",
        "app.routes.v1_upload",
        "app.routes.v1_jd",
        "app.routes.v1_subscription",
    ]:
        module = types.ModuleType(module_name)
        module.router = APIRouter()
        sys.modules[module_name] = module

    main = importlib.import_module("app.main")
    return main.http_exception_handler


def _load_generation_exception_mapper():
    app_models = types.ModuleType("app.models")
    app_models.GenerateRequest = type("GenerateRequest", (BaseModel,), {})
    app_models.Profile = type("Profile", (BaseModel,), {})
    app_models.ProfileV3 = type("ProfileV3", (BaseModel,), {})
    sys.modules["app.models"] = app_models

    tailor = types.ModuleType("app.core.tailor")
    tailor.run_tailor = lambda *args, **kwargs: None
    tailor.detect_region_from_jd = lambda *args, **kwargs: "GL"
    sys.modules["app.core.tailor"] = tailor

    tex_compile = types.ModuleType("app.core.tex_compile")
    tex_compile.render_tex = lambda *args, **kwargs: ("resume.tex", "cover.tex")
    tex_compile.compile_tex = lambda *args, **kwargs: True
    tex_compile.bundle_pdfs_only = lambda *args, **kwargs: "bundle.zip"
    sys.modules["app.core.tex_compile"] = tex_compile

    docx_compile = types.ModuleType("app.core.docx_compile")
    docx_compile.render_docx = lambda *args, **kwargs: ("resume.docx", "cover.docx")
    sys.modules["app.core.docx_compile"] = docx_compile

    db_database = types.ModuleType("app.db.database")
    db_database.get_db = lambda: None
    sys.modules["app.db.database"] = db_database

    db_models = types.ModuleType("app.db.models")
    db_models.User = type("User", (), {})
    db_models.Profile = type("DBProfile", (), {})
    db_models.Job = type("DBJob", (), {})
    db_models.Run = type("DBRun", (), {})
    sys.modules["app.db.models"] = db_models

    auth = types.ModuleType("app.auth.auth")
    auth.verify_token = lambda *args, **kwargs: None
    sys.modules["app.auth.auth"] = auth

    analytics = types.ModuleType("app.utils.analytics")
    analytics.track_event = lambda *args, **kwargs: None
    analytics.track_generation_metric = lambda *args, **kwargs: None
    analytics.EventType = type("EventType", (), {"GENERATION_ERROR": "generation_error"})
    analytics.detect_jd_industry = lambda *args, **kwargs: ""
    analytics.detect_jd_role_type = lambda *args, **kwargs: ""
    sys.modules["app.utils.analytics"] = analytics

    subscription = types.ModuleType("app.core.subscription")
    subscription.SUBSCRIPTION_LIVE = False
    sys.modules["app.core.subscription"] = subscription

    sys.modules.pop("app.routes.v1_generate", None)
    module = importlib.import_module("app.routes.v1_generate")
    return module._to_generation_http_exception


def test_classify_llm_exception_detects_quota_and_retry_after():
    classified = classify_llm_exception(DummyGeminiQuotaError())

    assert isinstance(classified, LLMQuotaExceededError)
    assert classified.status_code == 429
    assert classified.retry_after_seconds == 45


def test_generation_exception_mapper_reclassifies_raw_quota_errors():
    mapper = _load_generation_exception_mapper()
    http_exc = mapper(DummyGeminiQuotaError(), "DAIR")

    assert http_exc.status_code == 429
    assert http_exc.detail == (
        "We are temporarily unable to generate your documents. "
        "Please try again in about 45 seconds."
    )
    assert http_exc.headers == {"Retry-After": "45"}


def test_http_exception_handler_preserves_retry_after_header():
    http_exception_handler = _load_http_exception_handler()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/generate/",
            "headers": [],
        }
    )
    exc = HTTPException(status_code=429, detail="quota", headers={"Retry-After": "45"})

    response = asyncio.run(http_exception_handler(request, exc))

    assert response.status_code == 429
    assert response.headers["retry-after"] == "45"
    assert json.loads(response.body) == {"detail": "quota"}
