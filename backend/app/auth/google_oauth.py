"""
Google OAuth 2.0 implementation.
Handles authorization URL generation, token exchange,
token refresh, and user info fetch.
"""

import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Google endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"


def build_google_auth_url(state: str) -> str:
    """
    Build the Google OAuth authorization URL.
    Uses access_type=offline to get a refresh token.
    """
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(settings.google_scopes_list),
        "access_type": "offline",       # get refresh token
        "prompt": "consent",            # force consent to always get refresh token
        "state": state,
        "include_granted_scopes": "true",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_google_code(code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access + refresh tokens.
    Returns the raw token response dict.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("google_token_exchange_failed", 
                         status_code=resp.status_code, 
                         response=resp.text)
            raise e
        token_data = resp.json()

    logger.info("google_token_exchanged", scopes=token_data.get("scope", ""))
    return token_data


async def refresh_google_token(refresh_token: str) -> Dict[str, Any]:
    """
    Use a refresh token to obtain a new access token.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        token_data = resp.json()

    logger.info("google_token_refreshed")
    return token_data


async def get_google_user_info(access_token: str) -> Dict[str, Any]:
    """
    Fetch Google user profile using an access token.
    Returns dict with: sub, email, name, picture, etc.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


def compute_expiry(expires_in: int) -> datetime:
    """Convert expires_in seconds to an absolute UTC datetime."""
    return datetime.now(timezone.utc) + timedelta(seconds=expires_in - 30)


def generate_state() -> str:
    """Generate a cryptographically random OAuth state parameter."""
    return secrets.token_urlsafe(32)
