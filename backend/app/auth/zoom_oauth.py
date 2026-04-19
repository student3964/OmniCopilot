"""
Zoom Server-to-Server OAuth implementation.
Uses account_credentials grant type — no user redirect needed.
Tokens are fetched directly using client_id, client_secret, and account_id.
"""

from typing import Dict, Any
import base64

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"


def _zoom_basic_auth() -> str:
    """Build the Basic auth header for Zoom token exchange."""
    raw = f"{settings.zoom_client_id}:{settings.zoom_client_secret}"
    return base64.b64encode(raw.encode()).decode()


async def get_zoom_s2s_token() -> Dict[str, Any]:
    """
    Fetch a Server-to-Server OAuth token from Zoom.
    This is the primary flow for S2S apps — no user interaction needed.
    Returns dict with access_token, token_type, expires_in.
    """
    logger.info("zoom_s2s_requesting_token", 
                account_id=settings.zoom_account_id[:8] + "...",
                client_id=settings.zoom_client_id[:8] + "...")
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ZOOM_TOKEN_URL,
            headers={
                "Authorization": f"Basic {_zoom_basic_auth()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "account_credentials",
                "account_id": settings.zoom_account_id,
            },
        )
        
        # Log the full response for debugging
        if resp.status_code != 200:
            error_body = resp.json() if resp.headers.get("content-type") == "application/json" else {"error": resp.text}
            error_msg = error_body.get("error", "unknown")
            reason = error_body.get("reason", "No reason provided")

            logger.error("zoom_s2s_token_error", 
                        status=resp.status_code, 
                        body=resp.text,
                        account_id=settings.zoom_account_id)
            
            hint = ""
            if error_msg == "invalid_request":
                hint = " (Hint: This often means your S2S app is not yet 'Activated' in the Zoom Marketplace under the 'Activation' tab, or the Account ID is incorrect.)"
            
            raise ValueError(
                f"Zoom S2S token request failed ({resp.status_code}): {error_msg} - {reason}.{hint}"
            )
        
        data = resp.json()

    if "access_token" not in data:
        raise ValueError(f"Zoom S2S OAuth error: no access_token in response: {data}")

    logger.info("zoom_s2s_token_obtained", expires_in=data.get("expires_in"))
    return data


async def refresh_zoom_token(refresh_token: str = None) -> Dict[str, Any]:
    """
    For S2S OAuth, there's no refresh token — just get a new token.
    The refresh_token parameter is ignored (kept for interface compatibility).
    """
    return await get_zoom_s2s_token()
