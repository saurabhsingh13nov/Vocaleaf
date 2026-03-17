"""Tests for Apple sign-in flow."""

from unittest.mock import patch

from app.integrations.apple_oauth import AppleUserInfo

APPLE_ENDPOINT = "/api/auth/apple"
LINK_ENDPOINT = "/api/auth/link-apple"

FAKE_APPLE_USER = AppleUserInfo(
    sub="apple-uid-12345",
    email="appleuser@example.com",
    email_verified=True,
)


def _mock_verify(user_info: AppleUserInfo = FAKE_APPLE_USER):
    return patch(
        "app.api.auth.verify_apple_token",
        return_value=user_info,
    )


class TestAppleAuthNewUser:
    async def test_creates_user_and_sets_cookies(self, client):
        with _mock_verify():
            resp = await client.post(
                APPLE_ENDPOINT,
                json={"credential": "fake-apple-token"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["primary_email"] == "appleuser@example.com"
        assert data["user"]["status"] == "active"
        assert data["user"]["email_verified_at"] is not None
        assert data["access_token"]
        assert data["refresh_token"]
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies


class TestAppleAuthReturningUser:
    async def test_returns_same_user_on_second_login(self, client):
        with _mock_verify():
            resp1 = await client.post(
                APPLE_ENDPOINT,
                json={"credential": "fake-apple-token"},
            )
            user_id_1 = resp1.json()["user"]["id"]

            resp2 = await client.post(
                APPLE_ENDPOINT,
                json={"credential": "fake-apple-token"},
            )
            user_id_2 = resp2.json()["user"]["id"]

        assert resp2.status_code == 200
        assert user_id_1 == user_id_2


class TestAppleAuthMissingEmail:
    async def test_missing_email_is_rejected_for_first_time_sign_in(self, client):
        with _mock_verify(AppleUserInfo(sub="apple-no-email", email=None, email_verified=True)):
            resp = await client.post(
                APPLE_ENDPOINT,
                json={"credential": "fake-apple-token"},
            )

        assert resp.status_code == 400
        assert "missing email" in resp.json()["detail"].lower()


class TestAppleAuthEmailConflict:
    async def test_conflict_with_existing_password_account(self, client):
        await client.post(
            "/api/auth/register",
            json={
                "email": "appleuser@example.com",
                "password": "securepass123",
                "full_name": "Password User",
            },
        )

        with _mock_verify():
            resp = await client.post(
                APPLE_ENDPOINT,
                json={"credential": "fake-apple-token"},
            )

        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"].lower()


class TestLinkAppleIdentity:
    async def test_link_apple_success(self, client):
        await client.post(
            "/api/auth/register",
            json={
                "email": "appleuser@example.com",
                "password": "securepass123",
                "full_name": "Password User",
            },
        )

        with _mock_verify():
            resp = await client.post(
                LINK_ENDPOINT,
                json={"credential": "fake-apple-token", "password": "securepass123"},
            )

        assert resp.status_code == 200
        assert resp.json()["user"]["primary_email"] == "appleuser@example.com"
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    async def test_link_apple_wrong_password(self, client):
        await client.post(
            "/api/auth/register",
            json={
                "email": "appleuser@example.com",
                "password": "securepass123",
                "full_name": "Password User",
            },
        )

        with _mock_verify():
            resp = await client.post(
                LINK_ENDPOINT,
                json={"credential": "fake-apple-token", "password": "wrongpassword"},
            )

        assert resp.status_code == 401

    async def test_link_apple_is_idempotent(self, client, db_session):
        from sqlalchemy import select

        from app.models.auth_identity import AuthIdentity
        from app.models.enums import AuthProvider

        await client.post(
            "/api/auth/register",
            json={
                "email": "appleuser@example.com",
                "password": "securepass123",
                "full_name": "Password User",
            },
        )

        with _mock_verify():
            resp1 = await client.post(
                LINK_ENDPOINT,
                json={"credential": "fake-apple-token", "password": "securepass123"},
            )
            resp2 = await client.post(
                LINK_ENDPOINT,
                json={"credential": "fake-apple-token", "password": "securepass123"},
            )

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        result = await db_session.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == AuthProvider.APPLE,
                AuthIdentity.provider_user_id == "apple-uid-12345",
            )
        )
        identities = result.scalars().all()
        assert len(identities) == 1
