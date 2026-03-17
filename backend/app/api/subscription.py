"""Subscription and usage summary endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.subscription import (
    SubscriptionSummaryResponse,
)
from app.services.subscription import get_subscription_context, subscription_summary_payload

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


@router.get("", response_model=SubscriptionSummaryResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    context = await get_subscription_context(db, user_id=current_user.id)
    return SubscriptionSummaryResponse.model_validate(subscription_summary_payload(context))
