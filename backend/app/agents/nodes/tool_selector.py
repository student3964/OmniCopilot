"""
Tool Selector Node — identifies which tool to call for the current plan step.
Validates tool availability and prepares the tool call payload.
"""

import uuid
from typing import Optional

from app.agents.state import AgentState, ToolCall
from app.tools.registry import (
    get_tool_fn, get_provider_for_tool, is_sensitive, ALL_TOOL_SCHEMAS
)
from app.core.logging import get_logger

logger = get_logger(__name__)


async def tool_selector_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Tool Selector.
    Examines the current plan step and prepares a ToolCall.
    """
    plan = state.get("plan", [])
    step_index = state.get("current_step_index", 0)

    if step_index >= len(plan):
        logger.warning("tool_selector_no_step", index=step_index)
        return state

    current_step = plan[step_index]
    tool_name = current_step.get("tool_name")
    tool_input = current_step.get("tool_input", {})

    logger.info(
        "tool_selector_node",
        step=step_index + 1,
        description=current_step.get("description", "")[:60],
        tool=tool_name,
    )

    # No tool needed for this step (reasoning-only step)
    if not tool_name:
        logger.info("tool_selector_no_tool_step")
        return {
            **state,
            "pending_tool_calls": [],
        }

    # Validate tool exists in registry
    tool_fn = get_tool_fn(tool_name)
    if not tool_fn:
        logger.warning("tool_selector_unknown_tool", tool=tool_name)
        return {
            **state,
            "pending_tool_calls": [],
            "error": f"Unknown tool: {tool_name}",
        }

    # ── Pre-flight check for sensitive tools ──────────────────
    # Guard: prevent sensitive actions if critical info is missing or placeholder
    if is_sensitive(tool_name):
        tool_input = current_step.get("tool_input", {})
        if tool_name in ["create_calendar_event", "create_zoom_meeting"]:
            # Platform Safety Override: If user said 'Meet' but planner chose 'Zoom'
            q = state.get("user_query", "").lower()
            if tool_name == "create_zoom_meeting" and ("meet" in q or "google" in q):
                logger.warning("tool_selector_platform_override", original="zoom", target="google_calendar")
                tool_name = "create_calendar_event"
                tool_input["add_meet_link"] = True
                if "topic" in tool_input:
                    tool_input["summary"] = tool_input.pop("topic")
            
            # Attendee Guard
            attendees = tool_input.get("attendees") or tool_input.get("attendee_emails", [])
            is_valid = False
            if isinstance(attendees, list) and len(attendees) > 0:
                if any("@" in str(a) for a in attendees):
                    is_valid = True
            
            # If attendees not in tool_input, try to extract from chat history
            if not is_valid and not state.get("confirmed"):
                import re
                email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
                found_emails = []
                for msg in state.get("chat_history", []):
                    if msg.get("role") == "user":
                        found_emails.extend(email_pattern.findall(msg.get("content", "")))
                found_emails.extend(email_pattern.findall(state.get("user_query", "")))
                found_emails = list(dict.fromkeys(found_emails))
                
                if found_emails:
                    logger.info("tool_selector_injected_attendees", emails=found_emails)
                    # Support both field names for robustness
                    tool_input["attendees"] = found_emails
                    tool_input["attendee_emails"] = found_emails
                    current_step = {**current_step, "tool_input": tool_input, "tool_name": tool_name}
                    plan = list(plan)
                    plan[step_index] = current_step
                    state = {**state, "plan": plan}
                    is_valid = True
            
            # [SOLO MEETING FIX]: Handle cases where the user explicitly wants a solo meeting
            # or didn't provide attendees and it's not a 'Meet' request.
            solo_intent_keywords = ["just me", "no other", "solo", "myself", "no attendees"]
            if any(kw in q for kw in solo_intent_keywords):
                logger.info("tool_selector_solo_meeting_detected")
                is_valid = True

            # CLEAN UP REASONING NOTES
            current_notes = state.get("reasoning_notes", "")
            cleaned_notes = current_notes.replace("\nGuard: Missing attendees for calendar event. Please provide attendee names and email addresses.", "")
            
            if not is_valid and not state.get("confirmed"):
                logger.info("tool_selector_missing_info_guard", tool=tool_name)
                return {
                    **state,
                    "pending_tool_calls": [],
                    "current_step_index": len(plan),
                    "reasoning_notes": cleaned_notes + "\nGuard: Missing attendees for calendar event. Please provide attendee names and email addresses.",
                }
            else:
                state["reasoning_notes"] = cleaned_notes
                state["plan"] = plan
    
    # ── Handle Confirmation Requirement ───────────────────────
    requires_conf = is_sensitive(tool_name)
    already_confirmed = (
        state.get("confirmed") is True 
        and state.get("confirmed_tool_name") == tool_name
    )

    # Build ToolCall object
    tool_call = ToolCall(
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=None,
        status="pending",
        error=None,
        requires_confirmation=requires_conf and not already_confirmed,
        confirm_id=str(uuid.uuid4()) if (requires_conf and not already_confirmed) else None,
    )

    sse_events = list(state.get("sse_events", []))

    # If sensitive and not already confirmed, emit a confirmation request event
    if tool_call["requires_confirmation"]:
        sse_events.append({
            "event": "confirm_request",
            "data": {
                "confirm_id": tool_call["confirm_id"],
                "tool_name": tool_name,
                "action_description": current_step.get("description", ""),
                "tool_input": tool_call["tool_input"],
                "message": f"⚠️ I need your approval to: **{current_step.get('description', tool_name)}**",
            },
        })

    return {
        **state,
        "pending_tool_calls": [tool_call],
        "awaiting_confirmation": tool_call["requires_confirmation"],
        "confirmation_id": tool_call["confirm_id"],
        "sse_events": sse_events,
    }
