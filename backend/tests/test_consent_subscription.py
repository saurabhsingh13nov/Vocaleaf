"""Tests for consent status/capture and subscription defaults."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select

from app.core.roles import ROLE_STAFF
from app.models.consent import Consent
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.services.subscription import ensure_audio_quota_available

REGISTER_URL = "/api/auth/register"
CONSENTS_URL = "/api/consents"
CONSENT_STATUS_URL = "/api/consents/status"
SUBSCRIPTION_URL = "/api/subscription"


async def register(client: AsyncClient, *, email: str = "consent@example.com") -> None:
    response = await client.post(
        REGISTER_URL,
        json={
            "email": email,
            "password": "securepass123",
            "full_name": "Consent User",
        },
    )
    assert response.status_code == 201


async def get_user_by_email(db_session, email: str) -> User:
    result = await db_session.execute(select(User).where(User.primary_email == email))
    return result.scalar_one()


async def test_register_creates_default_subscription_and_seeded_plans(client: AsyncClient, db_session):
    await register(client)

    plans = (await db_session.execute(select(Plan).order_by(Plan.code.asc()))).scalars().all()
    subscriptions = (await db_session.execute(select(Subscription))).scalars().all()

    assert [plan.code for plan in plans] == ["free", "premium"]
    assert len(subscriptions) == 1
    assert subscriptions[0].provider == "system"


async def test_consent_status_starts_missing_and_updates(client: AsyncClient, db_session):
    await register(client)

    initial = await client.get(CONSENT_STATUS_URL)
    assert initial.status_code == 200
    assert initial.json()["requires_legal_consent"] is True
    assert initial.json()["has_voice_cloning_consent"] is False

    accepted = await client.post(
        CONSENTS_URL,
        json={
            "consents": [
                {"consent_type": "terms_of_service", "accepted_version": "2026-03-16"},
                {"consent_type": "privacy_policy", "accepted_version": "2026-03-16"},
            ]
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["requires_legal_consent"] is False

    rows = (await db_session.execute(select(Consent))).scalars().all()
    assert len(rows) == 2


async def test_subscription_summary_returns_usage_metrics(client: AsyncClient):
    await register(client)

    response = await client.get(SUBSCRIPTION_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["code"] == "free"
    assert body["plan"]["name"] == "free"
    assert body["usage"]["stories_created"]["limit"] == 3
    assert body["usage"]["voice_clones_created"]["limit"] == 1
    assert body["usage"]["audio_chars_synthesized"]["limit"] == 15000


async def test_subscription_summary_returns_unlimited_limits_for_elevated_users(client: AsyncClient, db_session):
    email = "staff-summary@example.com"
    await register(client, email=email)

    user = await get_user_by_email(db_session, email)
    user.role = ROLE_STAFF
    db_session.add(
        UsageRecord(
            user_id=user.id,
            usage_type="stories_created",
            quantity=4,
            unit="story",
            provider="system",
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    await db_session.commit()

    response = await client.get(SUBSCRIPTION_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["monthly_story_limit"] is None
    assert body["plan"]["max_pages_per_story"] is None
    assert body["plan"]["voice_clone_limit"] is None
    assert body["plan"]["monthly_audio_chars_limit"] is None
    assert body["usage"]["stories_created"]["used"] == 4
    assert body["usage"]["stories_created"]["limit"] is None
    assert body["usage"]["stories_created"]["remaining"] is None


async def test_elevated_users_bypass_audio_quota_checks(client: AsyncClient, db_session):
    email = "staff-audio@example.com"
    await register(client, email=email)

    user = await get_user_by_email(db_session, email)
    user.role = ROLE_STAFF
    db_session.add(
        UsageRecord(
            user_id=user.id,
            usage_type="audio_chars_synthesized",
            quantity=20000,
            unit="character",
            provider="system",
        )
    )
    await db_session.commit()

    context = await ensure_audio_quota_available(
        db_session,
        user_id=user.id,
        required_characters=999999,
    )

    assert context.effective_plan.monthly_audio_chars_limit is None
