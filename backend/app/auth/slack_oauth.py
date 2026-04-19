"""
Slack OAuth 2.0 implementation.
Handles the Slack OAuth V2 flow for workspace-level token.
"""

from typing import Dict, Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_IDENTITY_URL = "https://slack.com/api/users.identity"

# Scopes required for reading/sending messages
SLACK_SCOPES = [
    "channels:history",
    "channels:read",
    "chat:write",
    "groups:history",
    "groups:read",
    "im:history",
    "im:read",
    "users:read",
    "users:read.email",
]
# User-level scopes (for identity)
SLACK_USER_SCOPES = ["identity.basic", "identity.email", "identity.avatar"]


def build_slack_auth_url(state: str) -> str:
    """Build the Slack OAuth authorization URL."""
    params = {
        "client_id": settings.slack_client_id,
        "redirect_uri": settings.slack_redirect_uri,
        "scope": ",".join(SLACK_SCOPES),
        "user_scope": ",".join(SLACK_USER_SCOPES),
        "state": state,
    }
    return f"{SLACK_AUTH_URL}?{urlencode(params)}"


async def exchange_slack_code(code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for Slack bot + user tokens.
    Returns the full oauth.v2.access response.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SLACK_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret,
                "redirect_uri": settings.slack_redirect_uri,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        raise ValueError(f"Slack OAuth error: {data.get('error', 'unknown')}")

    logger.info("slack_token_exchanged", team=data.get("team", {}).get("name"))
    return data


async def get_slack_user_identity(user_token: str) -> Dict[str, Any]:
    """Fetch Slack user identity using user-level token."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            SLACK_IDENTITY_URL,
            headers={"Authorization": f"Bearer {user_token}"},
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        raise ValueError(f"Slack identity error: {data.get('error', 'unknown')}")

    return data
