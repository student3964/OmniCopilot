"""
Gmail Tool — read, search, and send emails via Gmail API.
Send email is a SENSITIVE action that requires user confirmation.
"""

import base64
import email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from app.core.logging import get_logger

logger = get_logger(__name__)


def _gmail_service(access_token: str):
    creds = Credentials(token=access_token)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _decode_body(payload: dict) -> str:
    """Recursively decode email body from Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data", "")

    if mime_type == "text/plain" and data:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    if mime_type == "text/html" and data:
        # Strip HTML tags for plain text representation
        import re
        html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        return re.sub(r"<[^>]+>", " ", html).strip()

    # Multipart — recurse into parts
    for part in payload.get("parts", []):
        result = _decode_body(part)
        if result:
            return result

    return ""


def _parse_message(msg: dict) -> dict:
    """Parse a Gmail message into a clean dict."""
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _decode_body(msg.get("payload", {}))

    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId"),
        "subject": headers.get("subject", "(no subject)"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "body": body[:15000] if body else msg.get("snippet", ""),  # cap body length
    }


async def get_emails(
    access_token: str,
    max_results: int = 5,
    query: str = "",
    label: str = "INBOX",
    num_emails: Optional[int] = None,    # Alias
    num_messages: Optional[int] = None,  # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Fetch emails from Gmail.

    Args:
        access_token: Valid Google OAuth access token.
        max_results: Number of emails to return (default 5).
        query: Gmail search query (e.g. 'from:boss@company.com is:unread').
        label: Gmail label to filter by (INBOX, SENT, STARRED, etc.).
        num_emails: Alias for max_results.
        num_messages: Alias for max_results.
    """
    # Handle aliases
    max_results = num_emails or num_messages or max_results
    try:
        service = _gmail_service(access_token)

        q = f"label:{label} {query}".strip()
        response = service.users().messages().list(
            userId="me",
            maxResults=max_results,
            q=q,
        ).execute()

        messages = response.get("messages", [])
        parsed = []

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me",
                id=msg_ref["id"],
                format="full",
            ).execute()
            parsed.append(_parse_message(msg))

        logger.info("emails_fetched", count=len(parsed), query=q)
        return {"success": True, "count": len(parsed), "emails": parsed}

    except Exception as e:
        logger.error("get_emails_error", error=str(e))
        return {"success": False, "error": str(e), "emails": []}


async def send_email(
    access_token: str,
    to: str = "",
    subject: str = "",
    body: str = "",
    cc: Optional[str] = None,
    reply_to_thread_id: Optional[str] = None,
    recipient: Optional[str] = None,  # Alias
    receiver: Optional[str] = None,   # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Send an email via Gmail.
    ⚠️ SENSITIVE — requires user confirmation before execution.

    Args:
        access_token: Valid Google OAuth access token.
        to: Recipient email address(es), comma-separated.
        subject: Email subject line.
        body: Plain text email body.
        cc: Optional CC email addresses.
        reply_to_thread_id: Optional Gmail thread ID to reply in same thread.
        recipient: Alias for to.
        receiver: Alias for to.
    """
    # Handle aliases
    to = to or recipient or receiver or ""
    
    if not to:
        return {"success": False, "error": "Recipient email address ('to') is required."}

    try:
        service = _gmail_service(access_token)

        msg = MIMEMultipart()
        msg["to"] = to
        msg["subject"] = subject
        if cc:
            msg["cc"] = cc
        msg.attach(MIMEText(body, "plain"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        payload: dict = {"raw": raw}
        if reply_to_thread_id:
            payload["threadId"] = reply_to_thread_id

        sent = service.users().messages().send(userId="me", body=payload).execute()

        logger.info("email_sent", to=to, subject=subject, message_id=sent.get("id"))
        return {
            "success": True,
            "message_id": sent.get("id"),
            "thread_id": sent.get("threadId"),
        }
    except Exception as e:
        logger.error("send_email_error", to=to, error=str(e))
        return {"success": False, "error": str(e)}


async def search_emails(
    access_token: str,
    query: str,
    max_results: int = 5,
    num_emails: Optional[int] = None,    # Alias
    num_messages: Optional[int] = None,  # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Search Gmail using Gmail's search syntax.

    Args:
        access_token: Valid Google OAuth access token.
        query: Gmail search query (from:, subject:, after:, before:, is:unread, etc.).
        max_results: Number of results.
    """
    return await get_emails(access_token=access_token, max_results=max_results, query=query, label="")


# ── Tool Schema ────────────────────────────────────────────────

GMAIL_TOOLS_SCHEMA = [
    {
        "name": "get_emails",
        "description": "Fetch recent emails from Gmail inbox or other labels. Use this to read emails, check inbox, or get emails from specific senders.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Number of emails to fetch. Default 5.", "default": 5},
                "query": {"type": "string", "description": "Gmail search query. E.g. 'from:boss@company.com is:unread today'"},
                "label": {"type": "string", "description": "Gmail label: INBOX, SENT, STARRED, IMPORTANT. Default INBOX.", "default": "INBOX"},
            },
            "required": [],
        },
    },
    {
        "name": "send_email",
        "description": "⚠️ SENSITIVE: Send an email via Gmail. Always confirm with the user before sending. Show them the draft first.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address(es)."},
                "subject": {"type": "string", "description": "Email subject."},
                "body": {"type": "string", "description": "Email body text."},
                "cc": {"type": "string", "description": "CC email addresses (optional)."},
            },
            "required": ["to", "subject", "body"],
        },
        "requires_confirmation": True,
    },
    {
        "name": "search_emails",
        "description": "Search Gmail messages using Gmail search syntax (from:, subject:, after:YYYY/MM/DD, etc.).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query string."},
                "max_results": {"type": "integer", "description": "Max results. Default 5.", "default": 5},
            },
            "required": ["query"],
        },
    },
]
