"""
Tool Selector Node — identifies which tool to call for the current plan step.
Validates tool availability and prepares the tool call payload.
Injected with Parameter Resolver to handle dynamic value extraction (e.g., file_ids).
"""

import uuid
from typing import Optional
import json

from app.agents.state import AgentState, ToolCall
from app.tools.registry import (
    get_tool_fn, get_provider_for_tool, is_sensitive, ALL_TOOL_SCHEMAS
)
from app.core.logging import get_logger

logger = get_logger(__name__)


async def _resolve_tool_parameters(state: AgentState, tool_name: str, tool_input: dict, step_description: str) -> dict:
    """
    Use a lightweight LLM call to resolve missing or placeholder parameters
    (like file_id or email) from previous tool results.
    """
    completed_calls = state.get("completed_tool_calls", [])
    detailed_results = []
    for call in completed_calls:
        if call.get("status") == "success":
            out = call.get("tool_output", {})
            import json
            text = json.dumps(out, default=str)
            if len(text) > 3000:
                text = text[:3000] + "... [truncated]"
            detailed_results.append(f"Tool {call.get('tool_name')}: {text}")
            
    results_summary = "\n".join(detailed_results)
    if not results_summary:
        results_summary = state.get("tool_results_summary", "")

    if not results_summary:
        return tool_input

    # Use the LLM to inspect the tool input against previous results
    # We let the LLM decide if it needs to swap a placeholder with a real ID
    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_llm()
        prompt = f"""You are the Parameter Resolver for Omni Copilot. 
Your job is to fill in the parameters for the current tool call based on previous results.

Current Tool: {tool_name}
Step Description: {step_description}
Proposed Input (may have placeholders): {json.dumps(tool_input)}

Previous Tool Results:
{results_summary}

Task:
1. Identify missing values like 'file_id', 'email', 'doc_id', 'thread_id', etc.
2. Find the correct values in the Previous Tool Results.
3. Return the COMPLETE, updated JSON tool_input.
4. If there are multiple possible values, use the ONE most relevant to the Step Description.
5. LINK INJECTION (CRITICAL): If the tool_input contains a 'body', 'message', or 'content' text field with `[JOIN_LINK]` or `[MEETING_LINK]` or `[MEETING_LINK_HERE]`:
   - For Zoom meetings: replace the placeholder with the `join_url` value from the previous Zoom tool result.
   - For Google Meet: replace the placeholder with the `google_meet_link` value from the previous calendar event result.
   - NEVER leave [JOIN_LINK] or [MEETING_LINK] unreplaced in the output.
6. If you cannot find a value, keep the original placeholder.

Respond ONLY with valid JSON.
"""
        response = await llm.ainvoke([
            SystemMessage(content="You are a precise JSON parameter resolver."),
            HumanMessage(content=prompt)
        ])
        
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        resolved_input = json.loads(raw.strip())
        logger.info("tool_selector_resolved_params", tool=tool_name, resolved=resolved_input)
        return resolved_input
    except Exception as e:
        logger.error("tool_selector_resolution_error", error=str(e))
        return tool_input


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
    description = current_step.get("description", "")

    logger.info(
        "tool_selector_node",
        step=step_index + 1,
        description=description[:60],
        tool=tool_name,
    )

    # No tool needed for this step (reasoning-only step)
    if not tool_name:
        logger.info("tool_selector_no_tool_step")
        return {
            **state,
            "pending_tool_calls": [],
        }

    # ── Resolve Dynamic Parameters ───────────────────────────
    if step_index > 0 or ("None" in str(tool_input)) or ("null" in str(tool_input)):
        tool_input = await _resolve_tool_parameters(state, tool_name, tool_input, description)

    # Validate tool exists in registry
    tool_fn = get_tool_fn(tool_name)
    if not tool_fn:
        logger.warning("tool_selector_unknown_tool", tool=tool_name)
        return {
            **state,
            "pending_tool_calls": [
                {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "status": "error",
                    "error": f"Unknown tool: {tool_name}",
                    "requires_confirmation": False
                }
            ],
            "error": f"Unknown tool: {tool_name}",
        }

    # ── Pre-flight check for Calendar/Zoom tools (Platform Guard) ──
    if tool_name in ["create_calendar_event", "create_zoom_meeting"]:
        q = state.get("user_query", "").lower()
        # Platform Safety Override — only redirect to Google Calendar if user explicitly says "google meet"
        if tool_name == "create_zoom_meeting" and ("google meet" in q or "google calendar" in q):
            logger.warning("tool_selector_platform_override", original="zoom", target="google_calendar")
            tool_name = "create_calendar_event"
            tool_input["add_meet_link"] = True
            if "topic" in tool_input:
                tool_input["summary"] = tool_input.pop("topic")
        
        # Attendee Injection — always extract emails from the user query
        attendees = tool_input.get("attendees") or tool_input.get("attendee_emails", [])
        is_valid = False
        if isinstance(attendees, list) and len(attendees) > 0:
            if any("@" in str(a) for a in attendees):
                is_valid = True
        
        # Try to extract attendees from query and chat history if missing
        if not is_valid:
            import re
            email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
            found_emails = []
            # Always scan user query first (highest priority)
            found_emails.extend(email_pattern.findall(state.get("user_query", "")))
            # Then scan recent chat history
            for msg in state.get("chat_history", []):
                if msg.get("role") == "user":
                    found_emails.extend(email_pattern.findall(msg.get("content", "")))
            found_emails = list(dict.fromkeys(found_emails))
            
            if found_emails:
                logger.info("tool_selector_injected_attendees", emails=found_emails)
                tool_input["attendees"] = found_emails
                is_valid = True
        
        # Solo Meeting Detection
        solo_intent_keywords = ["just me", "no other", "solo", "myself", "no attendees", "private"]
        if any(kw in q for kw in solo_intent_keywords):
            logger.info("tool_selector_solo_meeting_detected")
            is_valid = True
    
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
                "action_description": description,
                "tool_input": tool_call["tool_input"],
                "message": f"⚠️ I need your approval to: **{description or tool_name}**",
                "plan": plan,
                "current_step_index": step_index,
            },
        })

    return {
        **state,
        "pending_tool_calls": [tool_call],
        "awaiting_confirmation": tool_call["requires_confirmation"],
        "confirmation_id": tool_call["confirm_id"],
        "sse_events": sse_events,
    }
