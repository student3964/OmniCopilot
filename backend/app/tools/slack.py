"""
Slack Tool — read channels/messages, send messages, search conversations.
Send message is a SENSITIVE action requiring user confirmation.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from app.core.logging import get_logger

logger = get_logger(__name__)


def _slack_client(access_token: str) -> AsyncWebClient:
    return AsyncWebClient(token=access_token)


def _ts_to_datetime(ts: str) -> str:
    """Convert Slack timestamp to human-readable string."""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return ts


async def get_slack_channels(
    access_token: str,
    limit: int = 20,
    types: str = "public_channel,private_channel",
) -> Dict[str, Any]:
    """
    List Slack channels the bot is a member of.

    Args:
        access_token: Slack bot token.
        limit: Max channels to return.
        types: Channel types comma-separated (public_channel, private_channel, im, mpim).
    """
    try:
        client = _slack_client(access_token)
        response = await client.conversations_list(types=types, limit=limit)
        channels = response.get("channels", [])

        return {
            "success": True,
            "channels": [
                {
                    "id": c["id"],
                    "name": c.get("name", c.get("user", "DM")),
                    "is_private": c.get("is_private", False),
                    "is_im": c.get("is_im", False),
                    "member_count": c.get("num_members", 0),
                }
                for c in channels
            ],
        }
    except SlackApiError as e:
        logger.error("slack_channels_error", error=str(e))
        return {"success": False, "error": str(e), "channels": []}


async def get_slack_messages(
    access_token: str,
    channel: str,
    limit: int = 10,
    oldest: Optional[str] = None,
    num_messages: Optional[int] = None,  # Alias
    count: Optional[int] = None,         # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Fetch messages from a Slack channel.

    Args:
        access_token: Slack bot token.
        channel: Channel ID or name (e.g. '#general' or 'C01234ABC').
        limit: Number of messages to fetch.
        oldest: Oldest message timestamp (Unix float as string) — for filtering by date.
        num_messages: Alias for limit.
        count: Alias for limit.
    """
    # Handle aliases
    limit = num_messages or count or limit
    try:
        client = _slack_client(access_token)

        # Resolve channel name to ID if needed
        channel_id = channel
        if channel.startswith("#"):
            channel_id = await _resolve_channel_id(client, channel[1:])

        params: dict = {"channel": channel_id, "limit": limit}
        if oldest:
            params["oldest"] = oldest

        response = await client.conversations_history(**params)
        messages = response.get("messages", [])

        # Enrich with user display names
        user_cache = {}
        parsed = []
        for msg in messages:
            user_id = msg.get("user", "")
            if user_id and user_id not in user_cache:
                try:
                    u = await client.users_info(user=user_id)
                    user_cache[user_id] = u["user"]["profile"].get("display_name") or u["user"]["real_name"]
                except Exception:
                    user_cache[user_id] = user_id

            parsed.append({
                "ts": msg.get("ts"),
                "datetime": _ts_to_datetime(msg.get("ts", "")),
                "user": user_cache.get(user_id, user_id),
                "user_id": user_id,
                "text": msg.get("text", ""),
                "reply_count": msg.get("reply_count", 0),
                "reactions": [r["name"] for r in msg.get("reactions", [])],
            })

        logger.info("slack_messages_fetched", channel=channel_id, count=len(parsed))
        return {"success": True, "channel": channel, "messages": parsed}

    except SlackApiError as e:
        logger.error("slack_messages_error", channel=channel, error=str(e))
        return {"success": False, "error": str(e), "messages": []}


async def send_slack_message(
    access_token: str,
    channel: str,
    text: str,
    thread_ts: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a message to a Slack channel or DM.
    ⚠️ SENSITIVE — requires user confirmation before execution.

    Args:
        access_token: Slack bot token.
        channel: Channel ID or name (e.g. '#general', 'C01234ABC', or a user's Slack ID).
        text: Message text (supports Slack mrkdwn formatting).
        thread_ts: Optional thread timestamp to reply in a thread.
    """
    try:
        client = _slack_client(access_token)

        params: dict = {"channel": channel, "text": text}
        if thread_ts:
            params["thread_ts"] = thread_ts

        response = await client.chat_postMessage(**params)

        logger.info("slack_message_sent", channel=channel, ts=response.get("ts"))
        return {
            "success": True,
            "ts": response.get("ts"),
            "channel": response.get("channel"),
        }
    except SlackApiError as e:
        logger.error("send_slack_message_error", channel=channel, error=str(e))
        return {"success": False, "error": str(e)}


async def search_slack_messages(
    access_token: str,
    query: str,
    count: int = 10,
) -> Dict[str, Any]:
    """
    Search Slack messages using Slack's search API.
    Requires the search:read scope on USER token.

    Args:
        access_token: Slack user token (not bot token — search requires user scope).
        query: Search query string.
        count: Number of results.
    """
    try:
        client = _slack_client(access_token)
        response = await client.search_messages(query=query, count=count)
        matches = response.get("messages", {}).get("matches", [])

        return {
            "success": True,
            "query": query,
            "messages": [
                {
                    "text": m.get("text", ""),
                    "channel": m.get("channel", {}).get("name", ""),
                    "user": m.get("username", ""),
                    "datetime": _ts_to_datetime(m.get("ts", "")),
                    "permalink": m.get("permalink", ""),
                }
                for m in matches
            ],
        }
    except SlackApiError as e:
        logger.error("search_slack_error", query=query, error=str(e))
        return {"success": False, "error": str(e), "messages": []}


async def _resolve_channel_id(client: AsyncWebClient, channel_name: str) -> str:
    """Resolve a channel name to its Slack ID."""
    response = await client.conversations_list(types="public_channel,private_channel", limit=200)
    for ch in response.get("channels", []):
        if ch.get("name") == channel_name:
            return ch["id"]
    return channel_name  # Return as-is if not found


async def get_today_messages(
    access_token: str,
    channel: str,
    limit: int = 20,
    num_messages: Optional[int] = None,  # Alias
    count: Optional[int] = None,         # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Get messages from today in a Slack channel.
    Convenience wrapper around get_slack_messages.
    """
    from datetime import datetime, timezone, timedelta
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    oldest_ts = str(today_start.timestamp())
    return await get_slack_messages(
        access_token=access_token,
        channel=channel,
        limit=limit,
        oldest=oldest_ts,
    )


# ── Tool Schema ────────────────────────────────────────────────

SLACK_TOOLS_SCHEMA = [
    {
        "name": "get_slack_channels",
        "description": "List Slack channels the user has access to.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max channels. Default 20.", "default": 20},
            },
            "required": [],
        },
    },
    {
        "name": "get_slack_messages",
        "description": "Fetch messages from a specific Slack channel. Use this to read conversations, find what someone said, or summarize channel activity.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel ID or name (with # prefix)."},
                "limit": {"type": "integer", "description": "Number of messages. Default 10.", "default": 10},
            },
            "required": ["channel"],
        },
    },
    {
        "name": "get_today_messages",
        "description": "Get all messages from today in a Slack channel.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel ID or name."},
                "limit": {"type": "integer", "description": "Max messages. Default 20.", "default": 20},
            },
            "required": ["channel"],
        },
    },
    {
        "name": "send_slack_message",
        "description": "⚠️ SENSITIVE: Send a message to a Slack channel or person. Always confirm with the user before sending.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel ID or name."},
                "text": {"type": "string", "description": "Message text."},
                "thread_ts": {"type": "string", "description": "Thread timestamp to reply in thread (optional)."},
            },
            "required": ["channel", "text"],
        },
        "requires_confirmation": True,
    },
    {
        "name": "search_slack_messages",
        "description": "Search across all Slack messages using keywords.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "count": {"type": "integer", "description": "Max results. Default 10.", "default": 10},
            },
            "required": ["query"],
        },
    },
]
