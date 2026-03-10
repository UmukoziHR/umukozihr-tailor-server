from types import SimpleNamespace

from app.core import subscription
from app.core.email_service import generate_email_verification_token, verify_email_verification_token
from app.core.subscription import GenerationAccessDecision


def make_user(
    tier: str,
    *,
    used: int = 0,
    verified: bool = True,
    auth_provider: str = "email",
):
    user = SimpleNamespace(
        subscription_tier=tier,
        monthly_generations_used=used,
        monthly_generations_limit=0,
        usage_reset_at=None,
        auth_provider=auth_provider,
        is_verified=verified,
    )
    subscription.sync_user_subscription(user)
    return user


def test_legacy_pro_normalizes_to_bounty(monkeypatch):
    monkeypatch.setattr(subscription, "SUBSCRIPTION_LIVE", True)
    assert subscription.normalize_tier_name("pro") == "bounty"


def test_free_user_gets_one_generation(monkeypatch):
    monkeypatch.setattr(subscription, "SUBSCRIPTION_LIVE", True)
    user = make_user("free")

    first = subscription.evaluate_generation_access(user, planned_jobs=1)
    assert isinstance(first, GenerationAccessDecision)
    assert first.allowed is True

    subscription.record_generation_usage(user, 1)
    second = subscription.evaluate_generation_access(user, planned_jobs=1)
    assert second.allowed is False
    assert second.reason_code == "free_limit_reached"


def test_launch_limit_blocks_when_quota_used(monkeypatch):
    monkeypatch.setattr(subscription, "SUBSCRIPTION_LIVE", True)
    user = make_user("launch", used=10)

    decision = subscription.evaluate_generation_access(user, planned_jobs=1)
    assert decision.allowed is False
    assert decision.reason_code == "launch_limit_reached"


def test_unverified_email_user_is_blocked(monkeypatch):
    monkeypatch.setattr(subscription, "SUBSCRIPTION_LIVE", True)
    user = make_user("bounty", verified=False)

    decision = subscription.evaluate_generation_access(user, planned_jobs=1)
    assert decision.allowed is False
    assert decision.reason_code == "verification_required"


def test_batch_generation_requires_bounty(monkeypatch):
    monkeypatch.setattr(subscription, "SUBSCRIPTION_LIVE", True)
    user = make_user("launch")

    decision = subscription.evaluate_generation_access(user, planned_jobs=2)
    assert decision.allowed is False
    assert decision.reason_code == "batch_upgrade_required"


def test_launch_respects_env_var_quota(monkeypatch):
    monkeypatch.setattr(subscription, "SUBSCRIPTION_LIVE", True)
    monkeypatch.setattr(subscription, "LAUNCH_MONTHLY_GENERATIONS", 5)

    # At quota — should be blocked
    user_at_limit = make_user("launch", used=5)
    decision = subscription.evaluate_generation_access(user_at_limit, planned_jobs=1)
    assert decision.allowed is False
    assert decision.reason_code == "launch_limit_reached"

    # One under quota — should be allowed
    user_under = make_user("launch", used=4)
    decision2 = subscription.evaluate_generation_access(user_under, planned_jobs=1)
    assert decision2.allowed is True


def test_email_verification_token_round_trip():
    token = generate_email_verification_token(
        "12345678-1234-1234-1234-123456789012",
        "test@example.com",
    )
    payload = verify_email_verification_token(token)

    assert payload is not None
    assert payload["sub"] == "12345678-1234-1234-1234-123456789012"
    assert payload["email"] == "test@example.com"
