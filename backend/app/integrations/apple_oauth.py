"""Sign in with Apple identity token verification."""

from dataclasses import dataclass

import requests
from jose import JWTError, jwt

from app.core.config import settings
from app.services.auth import AuthError

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = f"{APPLE_ISSUER}/auth/keys"


@dataclass
class AppleUserInfo:
    sub: str
    email: str | None
    email_verified: bool


def _parse_email_verified(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False


def _fetch_apple_signing_keys() -> list[dict]:
    try:
        response = requests.get(APPLE_JWKS_URL, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AuthError("Unable to verify Apple credential", status_code=503) from exc

    payload = response.json()
    keys = payload.get("keys")
    if not isinstance(keys, list):
        raise AuthError("Unable to verify Apple credential", status_code=503)
    return keys


def verify_apple_token(credential: str) -> AppleUserInfo:
    if not settings.apple_client_id:
        raise AuthError("Apple client ID is not configured", status_code=500)

    try:
        header = jwt.get_unverified_header(credential)
    except JWTError as exc:
        raise AuthError(f"Invalid Apple credential: {exc}", status_code=400) from exc

    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise AuthError("Invalid Apple credential: missing key ID", status_code=400)

    signing_key = next((key for key in _fetch_apple_signing_keys() if key.get("kid") == kid), None)
    if signing_key is None:
        raise AuthError("Invalid Apple credential: unknown signing key", status_code=400)

    try:
        claims = jwt.decode(
            credential,
            signing_key,
            algorithms=["RS256"],
            audience=settings.apple_client_id,
            issuer=APPLE_ISSUER,
        )
    except JWTError as exc:
        raise AuthError(f"Invalid Apple credential: {exc}", status_code=400) from exc

    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthError("Invalid Apple credential: missing subject", status_code=400)

    email_claim = claims.get("email")
    email = email_claim.lower() if isinstance(email_claim, str) else None

    return AppleUserInfo(
        sub=sub,
        email=email,
        email_verified=_parse_email_verified(claims.get("email_verified")),
    )
