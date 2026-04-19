"""
Zoom Tool — list meetings, get meeting details, and fetch transcripts (if enabled).
Requires Zoom OAuth with meeting:read and recording:read scopes.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

ZOOM_API_BASE = "https://api.zoom.us/v2"


def _zoom_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


async def get_zoom_meetings(
    access_token: str,
    meeting_type: str = "upcoming",
    page_size: int = 10,
    num_meetings: Optional[int] = None,  # Alias
    count: Optional[int] = None,         # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    List Zoom meetings for the authenticated user.

    Args:
        access_token: Zoom OAuth access token.
        meeting_type: 'scheduled', 'live', 'upcoming', or 'previousMeetings'.
        page_size: Number of meetings to return.
        num_meetings: Alias for page_size.
        count: Alias for page_size.
    """
    # Handle aliases
    page_size = num_meetings or count or page_size
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ZOOM_API_BASE}/users/me/meetings",
                headers=_zoom_headers(access_token),
                params={"type": meeting_type, "page_size": page_size},
            )
            resp.raise_for_status()
            data = resp.json()

        meetings = data.get("meetings", [])
        logger.info("zoom_meetings_fetched", count=len(meetings), type=meeting_type)

        return {
            "success": True,
            "meetings": [
                {
                    "id": m.get("id"),
                    "uuid": m.get("uuid"),
                    "topic": m.get("topic", ""),
                    "start_time": m.get("start_time", ""),
                    "duration": m.get("duration", 0),
                    "join_url": m.get("join_url", ""),
                    "status": m.get("status", ""),
                }
                for m in meetings
            ],
        }
    except httpx.HTTPStatusError as e:
        logger.error("zoom_meetings_error", error=str(e), status=e.response.status_code)
        return {"success": False, "error": str(e), "meetings": []}
    except Exception as e:
        logger.error("zoom_meetings_error", error=str(e))
        return {"success": False, "error": str(e), "meetings": []}


async def get_zoom_meeting_recordings(
    access_token: str,
    meeting_id: str,
) -> Dict[str, Any]:
    """
    Get cloud recordings for a specific Zoom meeting.

    Args:
        access_token: Zoom OAuth access token.
        meeting_id: The Zoom meeting ID (numeric or UUID).
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ZOOM_API_BASE}/meetings/{meeting_id}/recordings",
                headers=_zoom_headers(access_token),
            )
            resp.raise_for_status()
            data = resp.json()

        recording_files = data.get("recording_files", [])
        logger.info("zoom_recordings_fetched", meeting_id=meeting_id, count=len(recording_files))

        return {
            "success": True,
            "meeting_topic": data.get("topic", ""),
            "start_time": data.get("start_time", ""),
            "duration": data.get("duration", 0),
            "recordings": [
                {
                    "id": r.get("id"),
                    "file_type": r.get("file_type", ""),  # MP4, M4A, TRANSCRIPT, etc.
                    "file_size": r.get("file_size", 0),
                    "download_url": r.get("download_url", ""),
                    "play_url": r.get("play_url", ""),
                    "recording_start": r.get("recording_start", ""),
                    "recording_end": r.get("recording_end", ""),
                    "status": r.get("status", ""),
                }
                for r in recording_files
            ],
        }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"success": False, "error": "No recordings found for this meeting.", "recordings": []}
        logger.error("zoom_recordings_error", meeting_id=meeting_id, error=str(e))
        return {"success": False, "error": str(e), "recordings": []}
    except Exception as e:
        logger.error("zoom_recordings_error", error=str(e))
        return {"success": False, "error": str(e), "recordings": []}


async def get_zoom_transcript(
    access_token: str,
    meeting_id: str,
) -> Dict[str, Any]:
    """
    Fetch the VTT/text transcript from a Zoom cloud recording.
    Requires cloud recording with transcript enabled on the Zoom account.

    Args:
        access_token: Zoom OAuth access token.
        meeting_id: The Zoom meeting ID.
    """
    try:
        # First, get recordings to find the TRANSCRIPT file
        recordings_result = await get_zoom_meeting_recordings(access_token, meeting_id)
        if not recordings_result["success"]:
            return recordings_result

        transcript_file = next(
            (r for r in recordings_result["recordings"] if r["file_type"] == "TRANSCRIPT"),
            None,
        )

        if not transcript_file:
            return {
                "success": False,
                "error": "No transcript available for this meeting. Enable cloud recording transcripts in Zoom settings.",
            }

        # Download transcript content
        download_url = transcript_file["download_url"]
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                download_url,
                headers=_zoom_headers(access_token),
                follow_redirects=True,
            )
            resp.raise_for_status()
            transcript_text = resp.text

        # Parse VTT to plain text
        plain_text = _parse_vtt(transcript_text)

        logger.info("zoom_transcript_fetched", meeting_id=meeting_id, chars=len(plain_text))

        return {
            "success": True,
            "meeting_id": meeting_id,
            "meeting_topic": recordings_result.get("meeting_topic", ""),
            "start_time": recordings_result.get("start_time", ""),
            "transcript": plain_text[:8000],  # cap to LLM context limit
            "char_count": len(plain_text),
            "truncated": len(plain_text) > 8000,
        }
    except Exception as e:
        logger.error("zoom_transcript_error", meeting_id=meeting_id, error=str(e))
        return {"success": False, "error": str(e)}


def _parse_vtt(vtt_content: str) -> str:
    """Parse WebVTT format transcript to plain text."""
    import re
    lines = vtt_content.split("\n")
    text_lines = []
    skip_patterns = re.compile(r"^WEBVTT|^\d+$|^\d{2}:\d{2}|^$")

    for line in lines:
        if skip_patterns.match(line.strip()):
            continue
        # Remove HTML tags from VTT
        clean = re.sub(r"<[^>]+>", "", line)
        if clean.strip():
            text_lines.append(clean.strip())

    return " ".join(text_lines)


async def list_past_meetings(
    access_token: str,
    days_back: int = 30,
    page_size: int = 10,
    num_meetings: Optional[int] = None,  # Alias
    count: Optional[int] = None,         # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    List past Zoom meetings within the last N days.

    Args:
        access_token: Zoom OAuth access token.
        days_back: How many days back to search.
        page_size: Number of results.
    """
    try:
        from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ZOOM_API_BASE}/users/me/meetings",
                headers=_zoom_headers(access_token),
                params={"type": "previousMeetings", "page_size": page_size, "from": from_date, "to": to_date},
            )
            resp.raise_for_status()
            data = resp.json()

        meetings = data.get("meetings", [])
        return {
            "success": True,
            "meetings": [
                {
                    "id": m.get("id"),
                    "topic": m.get("topic", ""),
                    "start_time": m.get("start_time", ""),
                    "duration": m.get("duration", 0),
                }
                for m in meetings
            ],
        }
    except Exception as e:
        logger.error("zoom_past_meetings_error", error=str(e))
        return {"success": False, "error": str(e), "meetings": []}


async def create_zoom_meeting(
    access_token: str,
    topic: str,
    start_time: str,
    duration: int = 30,
    agenda: str = ""
) -> Dict[str, Any]:
    """
    Create a scheduled Zoom meeting.
    Requires 'meeting:write:admin' or 'meeting:write' scope.
    """
    try:
        payload = {
            "topic": topic,
            "type": 2, # Scheduled meeting
            "start_time": start_time,
            "duration": duration,
            "agenda": agenda,
            "settings": {
                "host_video": True,
                "participant_video": True,
                "join_before_host": False,
                "mute_upon_entry": True
            }
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{ZOOM_API_BASE}/users/me/meetings",
                headers=_zoom_headers(access_token),
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
        logger.info("zoom_meeting_created", topic=topic)
        
        return {
            "success": True,
            "meeting_id": data.get("id"),
            "join_url": data.get("join_url"),
            "start_url": data.get("start_url"), # for the host to start it directly
            "topic": data.get("topic"),
            "start_time": data.get("start_time"),
            "duration": data.get("duration")
        }
    except Exception as e:
        logger.error("zoom_create_meeting_error", error=str(e))
        return {"success": False, "error": str(e)}


# ── Tool Schema ────────────────────────────────────────────────

ZOOM_TOOLS_SCHEMA = [
    {
        "name": "get_zoom_meetings",
        "description": "List upcoming or scheduled Zoom meetings.",
        "parameters": {
            "type": "object",
            "properties": {
                "meeting_type": {"type": "string", "description": "Type: scheduled, live, upcoming. Default upcoming.", "default": "upcoming"},
                "page_size": {"type": "integer", "description": "Number of meetings. Default 10.", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "get_zoom_transcript",
        "description": "Fetch the transcript of a Zoom meeting recording. Requires cloud recording with transcripts enabled.",
        "parameters": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string", "description": "Zoom meeting ID."},
            },
            "required": ["meeting_id"],
        },
    },
    {
        "name": "list_past_meetings",
        "description": "List past Zoom meetings.",
        "parameters": {
            "type": "object",
            "properties": {
                "days_back": {"type": "integer", "description": "How many days back to look. Default 30.", "default": 30},
                "page_size": {"type": "integer", "description": "Number of results. Default 10.", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "create_zoom_meeting",
        "description": "Create a new scheduled Zoom meeting. Exclusive for Zoom Video Communications (NOT for Google Meet).",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Subject or title of the meeting."},
                "start_time": {"type": "string", "description": "Start time in ISO-8601 format (e.g., 2024-05-20T14:30:00Z)."},
                "duration": {"type": "integer", "description": "Duration in minutes. Default is 30.", "default": 30},
                "agenda": {"type": "string", "description": "Meeting description or agenda.", "default": ""}
            },
            "required": ["topic", "start_time"]
        }
    },
]
