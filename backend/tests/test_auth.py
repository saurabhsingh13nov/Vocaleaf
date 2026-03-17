"""Auth tests — security unit tests + API integration tests."""

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

# ---------------------------------------------------------------------------
# Security unit tests
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self):
        hashed = hash_password("mysecretpassword")
        assert verify_password("mysecretpassword", hashed) is True

    def test_wrong_password_returns_false(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_hash_format_is_argon2id(self):
        hashed = hash_password("password123")
        assert hashed.startswith("$argon2id$")


class TestJWT:
    def test_access_token_decodes_with_correct_type(self):
        token = create_access_token("some-user-id")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "some-user-id"
        assert payload["type"] == "access"

    def test_refresh_token_decodes_with_correct_type(self):
        token = create_refresh_token("some-user-id")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "some-user-id"
        assert payload["type"] == "refresh"

    def test_tampered_token_returns_none(self):
        token = create_access_token("user-id")
        assert decode_token(token + "tampered") is None

    def test_garbage_token_returns_none(self):
        assert decode_token("not.a.token") is None


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"
REFRESH_URL = "/api/auth/refresh"
LOGOUT_URL = "/api/auth/logout"


class TestRegister:
    async def test_register_success(self, client):
        resp = await client.post(REGISTER_URL, json={
            "email": "new@example.com",
            "password": "securepass123",
            "full_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["primary_email"] == "new@example.com"
        assert data["user"]["full_name"] == "New User"
        assert data["user"]["role"] == "customer"
        assert data["access_token"]
        assert data["refresh_token"]
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    async def test_register_duplicate_email(self, client):
        payload = {
            "email": "dupe@example.com",
            "password": "securepass123",
            "full_name": "First",
        }
        resp1 = await client.post(REGISTER_URL, json=payload)
        assert resp1.status_code == 201

        resp2 = await client.post(REGISTER_URL, json=payload)
        assert resp2.status_code == 409

    async def test_register_short_password(self, client):
        resp = await client.post(REGISTER_URL, json={
            "email": "short@example.com",
            "password": "short",
            "full_name": "Test",
        })
        assert resp.status_code == 422

    async def test_register_missing_fields(self, client):
        resp = await client.post(REGISTER_URL, json={"email": "only@example.com"})
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client):
        await client.post(REGISTER_URL, json={
            "email": "login@example.com",
            "password": "securepass123",
            "full_name": "Login User",
        })
        resp = await client.post(LOGIN_URL, json={
            "email": "login@example.com",
            "password": "securepass123",
        })
        assert resp.status_code == 200
        assert resp.json()["user"]["primary_email"] == "login@example.com"
        assert "access_token" in resp.cookies

    async def test_login_wrong_password(self, client):
        await client.post(REGISTER_URL, json={
            "email": "wrongpw@example.com",
            "password": "securepass123",
            "full_name": "Test",
        })
        resp = await client.post(LOGIN_URL, json={
            "email": "wrongpw@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client):
        resp = await client.post(LOGIN_URL, json={
            "email": "nobody@example.com",
            "password": "whatever123",
        })
        assert resp.status_code == 401


class TestMe:
    async def test_me_with_valid_token(self, client):
        resp = await client.post(REGISTER_URL, json={
            "email": "me@example.com",
            "password": "securepass123",
            "full_name": "Me User",
        })
        # client automatically carries cookies
        me_resp = await client.get(ME_URL)
        assert me_resp.status_code == 200
        assert me_resp.json()["primary_email"] == "me@example.com"

    async def test_me_with_valid_bearer_token(self, client):
        resp = await client.post(REGISTER_URL, json={
            "email": "bearer@example.com",
            "password": "securepass123",
            "full_name": "Bearer User",
        })
        access_token = resp.json()["access_token"]

        client.cookies.clear()
        me_resp = await client.get(ME_URL, headers={"Authorization": f"Bearer {access_token}"})

        assert me_resp.status_code == 200
        assert me_resp.json()["primary_email"] == "bearer@example.com"

    async def test_me_without_token(self, client):
        resp = await client.get(ME_URL)
        assert resp.status_code == 401


class TestRefresh:
    async def test_refresh_with_valid_refresh_token(self, client):
        await client.post(REGISTER_URL, json={
            "email": "refresh@example.com",
            "password": "securepass123",
            "full_name": "Refresh User",
        })
        resp = await client.post(REFRESH_URL)
        assert resp.status_code == 200
        assert resp.json()["access_token"]
        assert "access_token" in resp.cookies

    async def test_refresh_with_bearer_refresh_token(self, client):
        reg_resp = await client.post(REGISTER_URL, json={
            "email": "refreshbearer@example.com",
            "password": "securepass123",
            "full_name": "Refresh Bearer",
        })
        refresh_token = reg_resp.json()["refresh_token"]

        client.cookies.clear()
        resp = await client.post(
            REFRESH_URL,
            headers={"Authorization": f"Bearer {refresh_token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["access_token"]

    async def test_refresh_with_access_token_rejected(self, client):
        """Access tokens must not be usable as refresh tokens."""
        reg_resp = await client.post(REGISTER_URL, json={
            "email": "badrefresh@example.com",
            "password": "securepass123",
            "full_name": "Bad Refresh",
        })
        access_token = reg_resp.json()["access_token"]
        # Clear cookies and send access token as refresh bearer token
        client.cookies.clear()
        resp = await client.post(
            REFRESH_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 401

    async def test_refresh_without_token(self, client):
        resp = await client.post(REFRESH_URL)
        assert resp.status_code == 401


class TestLogout:
    async def test_logout_clears_cookies(self, client):
        await client.post(REGISTER_URL, json={
            "email": "logout@example.com",
            "password": "securepass123",
            "full_name": "Logout User",
        })
        resp = await client.post(LOGOUT_URL)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logged out"


class TestEmailNormalization:
    async def test_register_normalized_login_works(self, client):
        await client.post(REGISTER_URL, json={
            "email": "  FoO@Bar.COM  ",
            "password": "securepass123",
            "full_name": "Norm User",
        })
        # Clear cookies so login gets fresh ones
        client.cookies.clear()
        resp = await client.post(LOGIN_URL, json={
            "email": "foo@bar.com",
            "password": "securepass123",
        })
        assert resp.status_code == 200
        assert resp.json()["user"]["primary_email"] == "foo@bar.com"


class TestFullFlow:
    async def test_register_me_logout_login_refresh(self, client):
        # Register
        reg = await client.post(REGISTER_URL, json={
            "email": "flow@example.com",
            "password": "securepass123",
            "full_name": "Flow User",
        })
        assert reg.status_code == 201

        # Me works after register
        me1 = await client.get(ME_URL)
        assert me1.status_code == 200

        # Logout
        logout = await client.post(LOGOUT_URL)
        assert logout.status_code == 200

        # Me fails after logout
        me2 = await client.get(ME_URL)
        assert me2.status_code == 401

        # Login
        login = await client.post(LOGIN_URL, json={
            "email": "flow@example.com",
            "password": "securepass123",
        })
        assert login.status_code == 200

        # Me works after login
        me3 = await client.get(ME_URL)
        assert me3.status_code == 200

        # Refresh works
        refresh = await client.post(REFRESH_URL)
        assert refresh.status_code == 200

        # Me still works after refresh
        me4 = await client.get(ME_URL)
        assert me4.status_code == 200
