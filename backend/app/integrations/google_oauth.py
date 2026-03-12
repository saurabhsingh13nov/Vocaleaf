"""Google OAuth — ID token verification using google-auth."""

from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import settings
from app.services.auth import AuthError


@dataclass
class GoogleUserInfo:
    sub: str
    email: str
    name: str | None
    picture: str | None
    email_verified: bool


def verify_google_token(credential: str) -> GoogleUserInfo:
    """Verify a Google ID token and return user info.

    Raises AuthError if the token is invalid, expired, or has wrong audience.
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as e:
        raise AuthError(f"Invalid Google credential: {e}", status_code=400)

    if not idinfo.get("email_verified", False):
        raise AuthError("Google email not verified", status_code=400)

    return GoogleUserInfo(
        sub=idinfo["sub"],
        email=idinfo["email"].lower(),
        name=idinfo.get("name"),
        picture=idinfo.get("picture"),
        email_verified=idinfo.get("email_verified", False),
    )
