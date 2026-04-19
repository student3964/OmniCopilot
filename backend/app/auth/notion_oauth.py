"""
Notion OAuth 2.0 implementation.
Uses the Notion public integration OAuth flow.
"""

from typing import Dict, Any
from urllib.parse import urlencode
import base64

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
NOTION_USER_URL = "https://api.notion.com/v1/users/me"


def build_notion_auth_url(state: str) -> str:
    """Build the Notion OAuth authorization URL."""
    params = {
        "client_id": settings.notion_client_id,
        "redirect_uri": settings.notion_redirect_uri,
        "response_type": "code",
        "owner": "user",
        "state": state,
    }
    return f"{NOTION_AUTH_URL}?{urlencode(params)}"


def _notion_basic_auth() -> str:
    """Notion requires Basic auth with client_id:client_secret for token exchange."""
    creds = f"{settings.notion_client_id}:{settings.notion_client_secret}"
    return base64.b64encode(creds.encode()).decode()


async def exchange_notion_code(code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for Notion access token.
    Notion uses Basic auth (not body params) for the token request.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            NOTION_TOKEN_URL,
            headers={
                "Authorization": f"Basic {_notion_basic_auth()}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            },
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.notion_redirect_uri,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    logger.info("notion_token_exchanged", workspace=data.get("workspace_name"))
    return data


async def get_notion_user(access_token: str) -> Dict[str, Any]:
    """Fetch the Notion user associated with the token."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            NOTION_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": "2022-06-28",
            },
        )
        resp.raise_for_status()
        return resp.json()
