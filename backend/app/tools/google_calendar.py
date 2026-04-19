"""
Google Calendar Tool — list, create, and manage calendar events.
Create/delete events are SENSITIVE actions requiring user confirmation.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from app.core.logging import get_logger

logger = get_logger(__name__)


def _cal_service(access_token: str):
    creds = Credentials(token=access_token)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _format_event(event: dict) -> dict:
    """Flatten a Calendar event into a clean dict."""
    start = event.get("start", {})
    end = event.get("end", {})
    attendees = event.get("attendees", [])
    
    # Robust Meet link extraction
    hangout_link = event.get("hangoutLink", "")
    conf_data = event.get("conferenceData", {})
    entry_points = conf_data.get("entryPoints", [])
    meet_link = next((ep.get("uri") for ep in entry_points if ep.get("entryPointType") == "video"), "")
    
    # Prefer conferenceData URI, then hangoutLink
    final_meet_link = meet_link or hangout_link

    return {
        "id": event.get("id"),
        "summary": event.get("summary", "(no title)"),
        "description": event.get("description", ""),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "location": event.get("location", ""),
        "google_meet_link": final_meet_link,
        "hangout_link": hangout_link,
        "attendees": [a.get("email") for a in attendees],
        "organizer": event.get("organizer", {}).get("email", ""),
        "status": event.get("status", "confirmed"),
        "html_link": event.get("htmlLink", ""),
    }


async def get_calendar_events(
    access_token: str,
    max_results: int = 10,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    calendar_id: str = "primary",
    query: Optional[str] = None,
    num_events: Optional[int] = None,  # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    List upcoming calendar events.

    Args:
        access_token: Valid Google OAuth access token.
        max_results: Number of events to return.
        time_min: Start time in ISO 8601 format (default: now).
        time_max: End time in ISO 8601 format (default: 7 days from now).
        calendar_id: Calendar ID ('primary' for main calendar).
        query: Free-text search query for event titles/descriptions.
        num_events: Alias for max_results.
    """
    # Handle aliases
    max_results = num_events or max_results
    try:
        service = _cal_service(access_token)

        now = datetime.now(timezone.utc)
        if not time_min:
            time_min = now.isoformat()
        if not time_max:
            time_max = (now + timedelta(days=7)).isoformat()

        params = {
            "calendarId": calendar_id,
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if query:
            params["q"] = query

        result = service.events().list(**params).execute()
        events = result.get("items", [])
        formatted = [_format_event(e) for e in events]

        logger.info("calendar_events_fetched", count=len(formatted))
        return {"success": True, "count": len(formatted), "events": formatted}

    except Exception as e:
        logger.error("get_calendar_events_error", error=str(e))
        return {"success": False, "error": str(e), "events": []}


async def create_calendar_event(
    access_token: str,
    summary: str = "",
    start_datetime: str = "",
    end_datetime: str = "",
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    add_meet_link: bool = True,
    calendar_id: str = "primary",
    # Aliases for LLM robustness
    # Aliases for LLM robustness
    title: Optional[str] = None,
    event_name: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    start: Optional[Any] = None, # Catch 'start' object or string
    end: Optional[Any] = None,   # Catch 'end' object or string
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Create a new Google Calendar event.
    ⚠️ SENSITIVE — requires user confirmation before execution.
    """
    logger.info("create_calendar_event_init", 
                summary=summary, start_datetime=start_datetime, 
                title=title, start_time=start_time, start=start, kwargs=kwargs)

    # Handle aliases
    summary = summary or title or event_name or "New Event"
    
    # Handle start time aliases
    raw_start = start_datetime or start_time
    if not raw_start and start:
        raw_start = start if isinstance(start, str) else start.get("dateTime") or start.get("date")
    
    # Handle end time aliases
    raw_end = end_datetime or end_time
    if not raw_end and end:
        raw_end = end if isinstance(end, str) else end.get("dateTime") or end.get("date")

    if not raw_start:
        return {"success": False, "error": "Missing start time"}

    # Natural Language Parsing with dateparser
    try:
        import dateparser
        # Use future-biased parsing for upcoming events
        now_dt = datetime.now()
        parsed_start = dateparser.parse(
            raw_start, 
            settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False}
        )
        if not parsed_start:
            return {"success": False, "error": f"Failed to parse start time: {raw_start}. Please provide a standard format."}
        
        # [GRACE PERIOD FIX]: If it parsed as tomorrow but it's very close to 'today' at that time,
        # and the user didn't explicitly mention 'tomorrow', fallback to today.
        # This fixes the 'invisible meeting' bug when a user asks for a time that just passed.
        if (parsed_start.date() > now_dt.date()) and ("tomorrow" not in raw_start.lower()):
            time_diff = parsed_start - now_dt
            # If the intended time was within the last 2 hours today, dateparser pushed it to tomorrow.
            # We'll pull it back.
            if time_diff.total_seconds() > 22 * 3600: # It's tomorrow but was likely intended for today if within ~2 hours 
                logger.info("calendar_date_pullback_triggered", original=parsed_start, adjusted="today")
                parsed_start = parsed_start - timedelta(days=1)

        effective_start = parsed_start.isoformat()
        logger.info("calendar_effective_start", start=effective_start)

        if not raw_end:
            # Default to 30 mins after start
            effective_end = (parsed_start + timedelta(minutes=30)).isoformat()
        else:
            parsed_end = dateparser.parse(
                raw_end, 
                settings={"RELATIVE_BASE": parsed_start, "RETURN_AS_TIMEZONE_AWARE": False}
            )
            if parsed_end:
                effective_end = parsed_end.isoformat()
            else:
                # Fallback to 30 mins if end parsing fails
                effective_end = (parsed_start + timedelta(minutes=30)).isoformat()
    except Exception as parse_err:
        logger.error("date_parsing_error", error=str(parse_err), input=raw_start)
        return {"success": False, "error": f"Error parsing dates: {str(parse_err)}"}

    try:
        service = _cal_service(access_token)

        event_body: dict = {
            "summary": summary,
            "start": {"dateTime": effective_start, "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": effective_end, "timeZone": "Asia/Kolkata"},
        }
        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location
        if attendees:
            event_body["attendees"] = [{"email": e} for e in attendees]
        if add_meet_link:
            event_body["conferenceData"] = {
                "createRequest": {"requestId": f"omni-{datetime.now().timestamp()}"}
            }

        result = service.events().insert(
            calendarId=calendar_id,
            body=event_body,
            conferenceDataVersion=1 if add_meet_link else 0,
            sendUpdates="all" if attendees else "none",
        ).execute()

        logger.info("calendar_event_created", event_id=result.get("id"), summary=summary)
        return {"success": True, "event": _format_event(result)}

    except Exception as e:
        logger.error("create_calendar_event_error", error=str(e))
        return {"success": False, "error": str(e)}


async def delete_calendar_event(
    access_token: str,
    event_id: str,
    calendar_id: str = "primary",
) -> Dict[str, Any]:
    """
    Delete a calendar event.
    ⚠️ SENSITIVE — requires user confirmation before execution.
    """
    try:
        service = _cal_service(access_token)
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        logger.info("calendar_event_deleted", event_id=event_id)
        return {"success": True, "deleted_event_id": event_id}
    except Exception as e:
        logger.error("delete_calendar_event_error", error=str(e))
        return {"success": False, "error": str(e)}


# ── Tool Schema ────────────────────────────────────────────────

CALENDAR_TOOLS_SCHEMA = [
    {
        "name": "get_calendar_events",
        "description": "List upcoming Google Calendar events. Use this for 'what's on my calendar', 'do I have meetings today/tomorrow', 'show schedule'.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Number of events. Default 10.", "default": 10},
                "time_min": {"type": "string", "description": "Start time as ISO 8601 string. Default is now."},
                "time_max": {"type": "string", "description": "End time as ISO 8601 string. Default is 7 days from now."},
                "query": {"type": "string", "description": "Search events by title or description."},
            },
            "required": [],
        },
    },
    {
        "name": "create_calendar_event",
        "description": "⚠️ SENSITIVE: Create a Google Calendar event. Used for creating Google Meet video conferences. Always confirm details with user first. Supports relative date strings (e.g., 'tomorrow at 5pm', 'next Monday').",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title."},
                "start_datetime": {"type": "string", "description": "ISO 8601 start datetime or relative string like 'tomorrow 9am'."},
                "end_datetime": {"type": "string", "description": "Optional: ISO 8601 end datetime or relative string. Defaults to 1 hour after start if omitted."},
                "description": {"type": "string", "description": "Event description (optional)."},
                "location": {"type": "string", "description": "Location or meeting room (optional)."},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee emails."},
                "add_meet_link": {"type": "boolean", "description": "Add Google Meet link. Default true.", "default": True},
            },
            "required": ["summary", "start_datetime"],
        },
        "requires_confirmation": True,
    },
]
