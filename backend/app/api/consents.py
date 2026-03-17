"""Consent capture and status endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.enums import ConsentType
from app.models.user import User
from app.schemas.consent import ConsentAcceptRequest, ConsentStatusResponse
from app.services.consent import (
    ConsentError,
    LEGAL_CONSENT_TYPES,
    consent_status_payload,
    record_consents,
)

router = APIRouter(prefix="/api/consents", tags=["consents"])


@router.get("/status", response_model=ConsentStatusResponse)
async def get_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await consent_status_payload(db, user_id=current_user.id)
    current_by_type = {item["consent_type"]: bool(item["is_current"]) for item in items}
    return ConsentStatusResponse(
        items=items,
        requires_legal_consent=not all(current_by_type.get(consent_type, False) for consent_type in LEGAL_CONSENT_TYPES),
        has_voice_cloning_consent=current_by_type.get(ConsentType.VOICE_CLONING, False),
    )


@router.post("", response_model=ConsentStatusResponse)
async def accept_consents(
    body: ConsentAcceptRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await record_consents(
            db,
            user_id=current_user.id,
            requested=[(item.consent_type, item.accepted_version) for item in body.consents],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ConsentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    items = await consent_status_payload(db, user_id=current_user.id)
    current_by_type = {item["consent_type"]: bool(item["is_current"]) for item in items}
    return ConsentStatusResponse(
        items=items,
        requires_legal_consent=not all(current_by_type.get(consent_type, False) for consent_type in LEGAL_CONSENT_TYPES),
        has_voice_cloning_consent=current_by_type.get(ConsentType.VOICE_CLONING, False),
    )
