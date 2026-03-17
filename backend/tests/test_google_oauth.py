"""Tests for Google OAuth sign-in flow."""

from unittest.mock import patch

import pytest

from app.integrations.google_oauth import GoogleUserInfo

GOOGLE_ENDPOINT = "/api/auth/google"
LINK_ENDPOINT = "/api/auth/link-google"

FAKE_GOOGLE_USER = GoogleUserInfo(
    sub="google-uid-12345",
    email="googleuser@gmail.com",
    name="Google User",
    picture="https://lh3.googleusercontent.com/photo.jpg",
    email_verified=True,
)


def _mock_verify(user_info: GoogleUserInfo = FAKE_GOOGLE_USER):
    """Patch verify_google_token to return the given user info."""
    return patch(
        "app.api.auth.verify_google_token",
        return_value=user_info,
    )


class TestGoogleAuthNewUser:
    async def test_creates_user_and_sets_cookies(self, client):
        with _mock_verify():
            resp = await client.post(
                GOOGLE_ENDPOINT,
                json={"credential": "fake-id-token"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["primary_email"] == "googleuser@gmail.com"
        assert data["user"]["full_name"] == "Google User"
        assert data["user"]["status"] == "active"
        assert data["user"]["email_verified_at"] is not None
        assert data["access_token"]
        assert data["refresh_token"]
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies


class TestGoogleAuthReturningUser:
    async def test_returns_same_user_on_second_login(self, client):
        with _mock_verify():
            resp1 = await client.post(
                GOOGLE_ENDPOINT,
                json={"credential": "fake-id-token"},
            )
            user_id_1 = resp1.json()["user"]["id"]

            resp2 = await client.post(
                GOOGLE_ENDPOINT,
                json={"credential": "fake-id-token"},
            )
            user_id_2 = resp2.json()["user"]["id"]

        assert resp2.status_code == 200
        assert user_id_1 == user_id_2


class TestGoogleAuthInvalidToken:
    async def test_invalid_credential_returns_400(self, client):
        from app.services.auth import AuthError

        with patch(
            "app.api.auth.verify_google_token",
            side_effect=AuthError("Invalid Google credential: bad token", 400),
        ):
            resp = await client.post(
                GOOGLE_ENDPOINT,
                json={"credential": "bad-token"},
            )

        assert resp.status_code == 400
        assert "Invalid Google credential" in resp.json()["detail"]


class TestGoogleAuthEmailConflict:
    async def test_conflict_with_existing_password_account(self, client):
        # Register with email/password first
        await client.post(
            "/api/auth/register",
            json={
                "email": "googleuser@gmail.com",
                "password": "securepass123",
                "full_name": "Password User",
            },
        )

        # Google login with same email should fail with 409
        with _mock_verify():
            resp = await client.post(
                GOOGLE_ENDPOINT,
                json={"credential": "fake-id-token"},
            )

        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"].lower()


class TestLinkGoogleIdentity:
    async def test_link_google_success(self, client):
        await client.post(
            "/api/auth/register",
            json={
                "email": "googleuser@gmail.com",
                "password": "securepass123",
                "full_name": "Password User",
            },
        )

        with _mock_verify():
            resp = await client.post(
                LINK_ENDPOINT,
                json={"credential": "fake-id-token", "password": "securepass123"},
            )

        assert resp.status_code == 200
        assert resp.json()["user"]["primary_email"] == "googleuser@gmail.com"
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    async def test_link_google_wrong_password(self, client):
        await client.post(
            "/api/auth/register",
            json={
                "email": "googleuser@gmail.com",
                "password": "securepass123",
                "full_name": "Password User",
            },
        )

        with _mock_verify():
            resp = await client.post(
                LINK_ENDPOINT,
                json={"credential": "fake-id-token", "password": "wrongpassword"},
            )

        assert resp.status_code == 401

    async def test_link_google_idempotent(self, client, db_session):
        from sqlalchemy import select

        from app.models.auth_identity import AuthIdentity
        from app.models.enums import AuthProvider

        await client.post(
            "/api/auth/register",
            json={
                "email": "googleuser@gmail.com",
                "password": "securepass123",
                "full_name": "Password User",
            },
        )

        with _mock_verify():
            resp1 = await client.post(
                LINK_ENDPOINT,
                json={"credential": "fake-id-token", "password": "securepass123"},
            )
            resp2 = await client.post(
                LINK_ENDPOINT,
                json={"credential": "fake-id-token", "password": "securepass123"},
            )

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        result = await db_session.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == AuthProvider.GOOGLE,
                AuthIdentity.provider_user_id == "google-uid-12345",
            )
        )
        identities = result.scalars().all()
        assert len(identities) == 1


class TestGoogleAuthProviderUserId:
    async def test_uses_sub_not_email_as_provider_user_id(self, client, db_session):
        from sqlalchemy import select

        from app.models.auth_identity import AuthIdentity
        from app.models.enums import AuthProvider

        with _mock_verify():
            await client.post(
                GOOGLE_ENDPOINT,
                json={"credential": "fake-id-token"},
            )

        result = await db_session.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == AuthProvider.GOOGLE,
                AuthIdentity.provider_user_id == "google-uid-12345",
            )
        )
        identity = result.scalar_one()
        assert identity.provider_user_id == "google-uid-12345"
        assert identity.email == "googleuser@gmail.com"
        assert identity.password_hash is None
        assert identity.is_verified is True
