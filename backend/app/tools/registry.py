"""
Tool Registry — central registry mapping tool names to their implementations.
The LangGraph agent uses this to dispatch tool calls.
"""

from typing import Any, Callable, Dict, Optional

# ── Import all tool functions ─────────────────────────────────
from app.tools.google_drive import get_drive_files, search_drive_files, get_drive_file_metadata, upload_to_drive
from app.tools.google_docs import read_drive_file
from app.tools.gmail import get_emails, send_email, search_emails
from app.tools.google_calendar import get_calendar_events, create_calendar_event, delete_calendar_event
from app.tools.slack import get_slack_channels, get_slack_messages, send_slack_message, search_slack_messages, get_today_messages
from app.tools.notion import search_notion, get_notion_page, list_notion_databases, create_notion_page
from app.tools.zoom import get_zoom_meetings, get_zoom_transcript, list_past_meetings, create_zoom_meeting

# ── Import all schemas ────────────────────────────────────────
from app.tools.google_drive import DRIVE_TOOLS_SCHEMA
from app.tools.google_docs import DOCS_TOOLS_SCHEMA
from app.tools.gmail import GMAIL_TOOLS_SCHEMA
from app.tools.google_calendar import CALENDAR_TOOLS_SCHEMA
from app.tools.slack import SLACK_TOOLS_SCHEMA
from app.tools.notion import NOTION_TOOLS_SCHEMA
from app.tools.zoom import ZOOM_TOOLS_SCHEMA


# ═══════════════════════════════════════════════════════════════
# Tool Registry
# Maps tool_name → async callable
# ═══════════════════════════════════════════════════════════════

TOOL_REGISTRY: Dict[str, Callable] = {
    # Google Drive
    "get_drive_files": get_drive_files,
    "search_drive_files": search_drive_files,
    "get_drive_file_metadata": get_drive_file_metadata,
    "upload_to_drive": upload_to_drive,

    # Google Docs
    "read_drive_file": read_drive_file,

    # Gmail
    "get_emails": get_emails,
    "send_email": send_email,
    "search_emails": search_emails,

    # Google Calendar
    "get_calendar_events": get_calendar_events,
    "create_calendar_event": create_calendar_event,
    "delete_calendar_event": delete_calendar_event,

    # Slack
    "get_slack_channels": get_slack_channels,
    "get_slack_messages": get_slack_messages,
    "get_today_messages": get_today_messages,
    "send_slack_message": send_slack_message,
    "search_slack_messages": search_slack_messages,

    # Notion
    "search_notion": search_notion,
    "get_notion_page": get_notion_page,
    "list_notion_databases": list_notion_databases,
    "create_notion_page": create_notion_page,

    # Zoom
    "get_zoom_meetings": get_zoom_meetings,
    "get_zoom_transcript": get_zoom_transcript,
    "list_past_meetings": list_past_meetings,
    "create_zoom_meeting": create_zoom_meeting,
}


# ═══════════════════════════════════════════════════════════════
# Tool Provider Mapping
# Maps tool_name → OAuth provider needed
# ═══════════════════════════════════════════════════════════════

TOOL_PROVIDER_MAP: Dict[str, str] = {
    "get_drive_files": "google",
    "search_drive_files": "google",
    "get_drive_file_metadata": "google",
    "upload_to_drive": "google",
    "read_drive_file": "google",
    "get_emails": "google",
    "send_email": "google",
    "search_emails": "google",
    "get_calendar_events": "google",
    "create_calendar_event": "google",
    "delete_calendar_event": "google",
    "get_slack_channels": "slack",
    "get_slack_messages": "slack",
    "get_today_messages": "slack",
    "send_slack_message": "slack",
    "search_slack_messages": "slack",
    "search_notion": "notion",
    "get_notion_page": "notion",
    "list_notion_databases": "notion",
    "create_notion_page": "notion",
    "get_zoom_meetings": "zoom",
    "get_zoom_transcript": "zoom",
    "list_past_meetings": "zoom",
    "create_zoom_meeting": "zoom",
}


# ═══════════════════════════════════════════════════════════════
# Sensitive Tools (require user confirmation)
# ═══════════════════════════════════════════════════════════════

SENSITIVE_TOOLS = {
    "send_email",
    "create_calendar_event",
    "delete_calendar_event",
    "send_slack_message",
    "create_notion_page",
    "create_zoom_meeting",
    "upload_to_drive",
}


# ═══════════════════════════════════════════════════════════════
# Full Schema List (for LLM tool calling)
# ═══════════════════════════════════════════════════════════════

ALL_TOOL_SCHEMAS = (
    DRIVE_TOOLS_SCHEMA
    + DOCS_TOOLS_SCHEMA
    + GMAIL_TOOLS_SCHEMA
    + CALENDAR_TOOLS_SCHEMA
    + SLACK_TOOLS_SCHEMA
    + NOTION_TOOLS_SCHEMA
    + ZOOM_TOOLS_SCHEMA
)


def get_tool_fn(tool_name: str) -> Optional[Callable]:
    """Lookup a tool function by name."""
    return TOOL_REGISTRY.get(tool_name)


def is_sensitive(tool_name: str) -> bool:
    """Check if a tool requires user confirmation before execution."""
    return tool_name in SENSITIVE_TOOLS


def get_provider_for_tool(tool_name: str) -> Optional[str]:
    """Get the OAuth provider required for a tool."""
    return TOOL_PROVIDER_MAP.get(tool_name)
