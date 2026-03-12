"""Smoke test: verify all 17 domain tables are registered in Base.metadata."""

from app.db.base import Base
from app.models import (  # noqa: F401 — force registration
    Asset,
    AuditEvent,
    AuthIdentity,
    CharacterProfile,
    Child,
    Consent,
    Plan,
    Story,
    StoryCharacter,
    StoryGenerationJob,
    StoryPage,
    StoryPageGeneration,
    Subscription,
    UsageRecord,
    User,
    VoiceProfile,
    VoiceSample,
)

EXPECTED_TABLES = {
    "assets",
    "audit_events",
    "auth_identities",
    "character_profiles",
    "children",
    "consents",
    "plans",
    "stories",
    "story_characters",
    "story_generation_jobs",
    "story_page_generations",
    "story_pages",
    "subscriptions",
    "usage_records",
    "users",
    "voice_profiles",
    "voice_samples",
}


def test_all_tables_registered():
    registered = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - registered
    assert not missing, f"Missing tables: {missing}"


def test_table_count():
    assert len(EXPECTED_TABLES) == 17
    registered = set(Base.metadata.tables.keys())
    assert EXPECTED_TABLES.issubset(registered)
