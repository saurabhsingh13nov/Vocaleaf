"""Assign a subscription plan to a user by email or user id."""

from __future__ import annotations

import argparse
import asyncio
import uuid

from app.db.session import dispose_session_state, get_async_session_factory
from app.services.subscription import assign_subscription_to_user


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assign a subscription plan to a Vocaleaf user.")
    parser.add_argument("--plan", required=True, help="Plan code, for example 'free' or 'premium'.")
    parser.add_argument("--email", help="User primary email.")
    parser.add_argument("--user-id", help="User UUID.")
    return parser


async def _run(plan: str, *, email: str | None, user_id: str | None) -> None:
    parsed_user_id = uuid.UUID(user_id) if user_id else None
    session_factory = get_async_session_factory()
    async with session_factory() as db:
        subscription = await assign_subscription_to_user(
            db,
            plan_code=plan,
            email=email,
            user_id=parsed_user_id,
        )
        print(
            f"Assigned plan '{subscription.plan.code}' to user {subscription.user_id} "
            f"for period ending {subscription.current_period_end.isoformat() if subscription.current_period_end else 'unknown'}."
        )


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if bool(args.email) == bool(args.user_id):
        parser.error("Provide exactly one of --email or --user-id.")
    try:
        asyncio.run(_run(args.plan, email=args.email, user_id=args.user_id))
    finally:
        asyncio.run(dispose_session_state())


if __name__ == "__main__":
    main()
