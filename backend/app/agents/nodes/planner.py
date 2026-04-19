"""
Planner Node — decomposes the user's query into an ordered list of steps.
Uses the LLM to produce a structured JSON plan.
"""

import json
from datetime import datetime, timezone
from typing import List

from app.agents.state import AgentState, PlanStep
from app.services.llm_service import get_llm
from app.tools.registry import ALL_TOOL_SCHEMAS
from app.core.logging import get_logger

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the Planner for Omni Copilot, a unified AI assistant for the user Yasha.
Your job is to break down the user's query into a clear, ordered list of steps. 

Available tools:
{tool_list}

Rules:
1. Only include steps that are necessary.
2. For each step, specify which tool to use (if any).
3. Steps should be sequential — later steps can use results from earlier ones.
4. For meeting/calendar requests: ALWAYS plan a `create_calendar_event` step. Include attendee emails in the tool_input if the user has provided them in the conversation. If no attendees were mentioned, still plan the step — the system will ask the user automatically.
5. For file/document requests (read, summarize, analyze): 
   - ALWAYS check the "Previous conversation context" first. If the file content is already present in a preceding "system" or "user" message (look for "[FILE CONTENT]" or "Uploaded file:"), do NOT use `read_drive_file`. Just summarize the content from history.
   - If the user provides a filename but you don't have the `file_id` and the content isn't in history, you MUST plan a `search_drive_files` step first to obtain the ID.
   - NEVER use placeholder strings like "determine later" or "TBD" for any parameter. Use real values from the conversation or omit the parameter.
6. IMPORTANT: Honesty and Tool Usage.
   - NEVER claim to have completed a task unless you have actually planned and executed the corresponding tool in a PREVIOUS step and seen a "success": true result.
   - If you are planning a step to do something, use the future tense (e.g., "I will create...") rather than the past tense.
7. If no tool is needed for a step (e.g., reasoning/summarizing content already in history), set tool_name to null.
8. Keep steps concise and actionable.
9. GOOGLE MEET vs ZOOM: 
   - If the user asks for a 'Google Meet', ALWAYS use 'create_calendar_event' with 'add_meet_link: true'.
   - ONLY use 'create_zoom_meeting' if the user specifically says 'Zoom'.
   - If they just say 'Meeting' or 'Video Call' without specifying the platform, prefer 'Google Meet' (create_calendar_event).

Respond ONLY with valid JSON in this exact format:
{{
  "steps": [
    {{
      "step_number": 1,
      "description": "What this step does",
      "tool_name": "tool_function_name_or_null",
      "tool_input": {{"param": "value"}}
    }}
  ]
}}
"""


def _build_tool_list_text() -> str:
    """Build a concise tool list description for the planner prompt."""
    lines = []
    for schema in ALL_TOOL_SCHEMAS:
        name = schema["name"]
        desc = schema.get("description", "")[:100]
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


async def planner_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Planner.
    Converts user_query → structured list of PlanSteps.
    """
    logger.info("planner_node_start", query=state["user_query"][:80])
    
    # ── RESUME BYPASS ──────────────────────────────────────────
    # If this is a resume from a confirmation, jump straight to the action
    if state.get("confirmed") and state.get("confirmed_tool_name"):
        logger.info("planner_bypass_confirmed", tool=state["confirmed_tool_name"])
        confirmed_step = PlanStep(
            step_number=1,
            description=f"Proceed with confirmed action: {state['confirmed_tool_name']}",
            tool_name=state["confirmed_tool_name"],
            tool_input=state.get("confirmed_tool_input", {}),
            completed=False,
            result=None,
        )
        return {
            **state,
            "plan": [confirmed_step],
            "current_step_index": 0,
            "iterations": 0,
            "sse_events": state.get("sse_events", []) + [
                {"event": "thinking", "data": {"message": "Resuming approved action...", "plan": [confirmed_step["description"]]}}
            ],
        }

    llm = get_llm()
    tool_list_text = _build_tool_list_text()

    # Build conversation context for the planner
    history_str = ""
    for msg in state.get("chat_history", [])[-6:]:  # last 3 exchanges
        history_str += f"{msg['role'].upper()}: {msg['content']}\n"

    user_message = f"""User query: {state['user_query']}

Previous conversation context:
{history_str}

Create a step-by-step plan to answer this query."""

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT.format(tool_list=tool_list_text)},
        {"role": "user", "content": user_message},
    ]

    # Add current time context to help with relative dates (today, tomorrow, etc.)
    now = datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y, %I:%M %p")
    time_context = f"\n\nCURRENT_SYSTEM_TIME: {current_time_str}"

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        lc_messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT.format(tool_list=tool_list_text) + time_context),
            HumanMessage(content=user_message),
        ]
        response = await llm.ainvoke(lc_messages)
        raw = response.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        plan_data = json.loads(raw)
        steps: List[PlanStep] = []

        for s in plan_data.get("steps", []):
            steps.append(PlanStep(
                step_number=s.get("step_number", len(steps) + 1),
                description=s.get("description", ""),
                tool_name=s.get("tool_name"),
                tool_input=s.get("tool_input", {}),
                completed=False,
                result=None,
            ))

        logger.info("plan_created", step_count=len(steps))

        return {
            **state,
            "plan": steps,
            "current_step_index": 0,
            "iterations": 0,
            "sse_events": state.get("sse_events", []) + [
                {"event": "thinking", "data": {"message": f"Created a {len(steps)}-step plan", "plan": [s["description"] for s in steps]}}
            ],
        }

    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.error("planner_node_error", error=str(e))
        # STABILIZATION: Do NOT fallback to "answer directly" if it's an LLM error.
        # This prevents the responder from hallucinating success.
        return {
            **state,
            "plan": [], 
            "current_step_index": 0,
            "iterations": 0,
            "error": f"Planner Error: API Unavailable or Rate Limited. Detail: {str(e)}",
            "sse_events": state.get("sse_events", []) + [
                {"event": "error", "data": {"message": f"Critical AI Error: {str(e)}"}}
            ],
        }
