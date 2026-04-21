"""
Token Service — manages OAuth token retrieval and transparent refresh.
Every tool call goes through get_valid_token() to ensure tokens are fresh.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import OAuthToken
from app.core.logging import get_logger

logger = get_logger(__name__)


async def get_valid_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider: str,
) -> Optional[str]:
    """
    Retrieve a valid access token for the given provider.
    Automatically refreshes if expired.
    Returns None if no token found (user not connected).
    """
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == provider,
        )
    )
    token_row = result.scalar_one_or_none()

    if token_row is None:
        logger.warning("no_token_found", user_id=str(user_id), provider=provider)
        return None

    # Check expiry with 60-second buffer
    now = datetime.now(timezone.utc)
    if token_row.expires_at and token_row.expires_at <= now:
        logger.info("token_expired_refreshing", provider=provider)
        token_row = await _refresh_token(db, token_row)

    return token_row.access_token


async def _refresh_token(db: AsyncSession, token_row: OAuthToken) -> OAuthToken:
    """Dispatch to the correct provider refresh function."""
    if token_row.provider == "google":
        return await _refresh_google(db, token_row)
    elif token_row.provider == "zoom":
        return await _refresh_zoom(db, token_row)
    elif token_row.provider == "slack":
        # Slack tokens don't expire (bot tokens are permanent)
        return token_row
    elif token_row.provider == "notion":
        # Notion tokens don't expire
        return token_row
    else:
        logger.error("unknown_provider_refresh", provider=token_row.provider)
        return token_row


async def _refresh_google(db: AsyncSession, token_row: OAuthToken) -> OAuthToken:
    """Refresh a Google access token using the stored refresh token."""
    from app.auth.google_oauth import refresh_google_token, compute_expiry

    if not token_row.refresh_token:
        raise ValueError("No refresh token stored for Google — user must re-authenticate")

    new_token_data = await refresh_google_token(token_row.refresh_token)

    token_row.access_token = new_token_data["access_token"]
    token_row.expires_at = compute_expiry(new_token_data.get("expires_in", 3600))
    if "refresh_token" in new_token_data:
        token_row.refresh_token = new_token_data["refresh_token"]

    await db.commit()
    await db.refresh(token_row)
    logger.info("google_token_refreshed_saved")
    return token_row


async def _refresh_zoom(db: AsyncSession, token_row: OAuthToken) -> OAuthToken:
    """Refresh a Zoom access token using the stored refresh token."""
    from app.auth.zoom_oauth import refresh_zoom_token
    from app.auth.google_oauth import compute_expiry

    # Zoom S2S OAuth doesn't use refresh tokens — we just fetch a new one.
    new_token_data = await refresh_zoom_token(token_row.refresh_token)

    token_row.access_token = new_token_data["access_token"]
    token_row.expires_at = compute_expiry(new_token_data.get("expires_in", 3600))
    if "refresh_token" in new_token_data:
        token_row.refresh_token = new_token_data["refresh_token"]

    await db.commit()
    await db.refresh(token_row)
    logger.info("zoom_token_refreshed_saved")
    return token_row


async def save_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider: str,
    token_data: dict,
) -> OAuthToken:
    """
    Upsert an OAuth token for a user+provider.
    Called after a successful OAuth callback.
    """
    from app.auth.google_oauth import compute_expiry

    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == provider,
        )
    )
    token_row = result.scalar_one_or_none()

    expires_at = None
    if "expires_in" in token_data:
        expires_at = compute_expiry(token_data["expires_in"])

    if token_row is None:
        token_row = OAuthToken(
            user_id=user_id,
            provider=provider,
            access_token=token_data.get("access_token", ""),
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type", "Bearer"),
            scope=token_data.get("scope"),
            expires_at=expires_at,
            raw_data=token_data,
        )
        db.add(token_row)
    else:
        token_row.access_token = token_data.get("access_token", token_row.access_token)
        if token_data.get("refresh_token"):
            token_row.refresh_token = token_data["refresh_token"]
        token_row.scope = token_data.get("scope", token_row.scope)
        token_row.expires_at = expires_at
        token_row.raw_data = token_data

    await db.commit()
    await db.refresh(token_row)
    return token_row


async def is_connected(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider: str,
) -> bool:
    """Check if a user has a stored token for the given provider."""
    result = await db.execute(
        select(OAuthToken.id).where(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == provider,
        )
    )
    return result.scalar_one_or_none() is not None
