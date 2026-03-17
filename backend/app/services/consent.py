"""Versioned consent capture and lookup helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import Consent
from app.models.enums import ConsentType
from app.services.audit import record_audit_event

CONSENT_VERSION_2026_03_16 = "2026-03-16"

SUPPORTED_CONSENT_TYPES: tuple[ConsentType, ...] = (
    ConsentType.TERMS_OF_SERVICE,
    ConsentType.PRIVACY_POLICY,
    ConsentType.VOICE_CLONING,
)
LEGAL_CONSENT_TYPES: tuple[ConsentType, ...] = (
    ConsentType.TERMS_OF_SERVICE,
    ConsentType.PRIVACY_POLICY,
)

REQUIRED_CONSENT_VERSIONS: dict[ConsentType, str] = {
    ConsentType.TERMS_OF_SERVICE: CONSENT_VERSION_2026_03_16,
    ConsentType.PRIVACY_POLICY: CONSENT_VERSION_2026_03_16,
    ConsentType.VOICE_CLONING: CONSENT_VERSION_2026_03_16,
}


class ConsentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def latest_consents_by_type(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[ConsentType, Consent]:
    result = await db.execute(
        select(Consent)
        .where(
            Consent.user_id == user_id,
            Consent.consent_type.in_(SUPPORTED_CONSENT_TYPES),
        )
        .order_by(Consent.accepted_at.desc(), Consent.id.desc())
    )

    latest: dict[ConsentType, Consent] = {}
    for consent in result.scalars():
        latest.setdefault(consent.consent_type, consent)
    return latest


async def has_current_consent(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    consent_type: ConsentType,
) -> bool:
    latest = await latest_consents_by_type(db, user_id=user_id)
    consent = latest.get(consent_type)
    if consent is None:
        return False
    return consent.accepted_version == REQUIRED_CONSENT_VERSIONS[consent_type]


async def consent_status_payload(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[dict[str, str | bool | datetime | None]]:
    latest = await latest_consents_by_type(db, user_id=user_id)
    payload: list[dict[str, str | bool | datetime | None]] = []

    for consent_type in SUPPORTED_CONSENT_TYPES:
        current = latest.get(consent_type)
        required_version = REQUIRED_CONSENT_VERSIONS[consent_type]
        payload.append(
            {
                "consent_type": consent_type,
                "required_version": required_version,
                "accepted_version": current.accepted_version if current else None,
                "accepted_at": current.accepted_at if current else None,
                "is_current": bool(current and current.accepted_version == required_version),
            }
        )

    return payload


def _validate_requested_consents(
    requested: list[tuple[ConsentType, str]],
) -> None:
    if not requested:
        raise ConsentError("At least one consent must be provided", status_code=400)

    seen: set[ConsentType] = set()
    for consent_type, accepted_version in requested:
        if consent_type not in SUPPORTED_CONSENT_TYPES:
            raise ConsentError("Unsupported consent type", status_code=400)
        if consent_type in seen:
            raise ConsentError("Duplicate consent types are not allowed", status_code=400)
        seen.add(consent_type)

        required_version = REQUIRED_CONSENT_VERSIONS[consent_type]
        if accepted_version != required_version:
            raise ConsentError(
                f"{consent_type.value} must be accepted at version {required_version}",
                status_code=400,
            )


async def record_consents(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    requested: list[tuple[ConsentType, str]],
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    _validate_requested_consents(requested)

    for consent_type, accepted_version in requested:
        db.add(
            Consent(
                user_id=user_id,
                consent_type=consent_type,
                accepted_version=accepted_version,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        record_audit_event(
            db,
            user_id=user_id,
            entity_type="consent",
            event_type="consent.accepted",
            event_data={
                "consent_type": consent_type.value,
                "accepted_version": accepted_version,
            },
        )

    await db.commit()
