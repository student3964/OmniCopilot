"""
Tool Executor Node — dispatches the pending tool call using the token service.
Fetches the user's OAuth token for the required provider and calls the tool.
"""

import uuid
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState, ToolCall
from app.tools.registry import get_tool_fn, get_provider_for_tool
from app.services.token_service import get_valid_token
from app.core.logging import get_logger
import inspect

logger = get_logger(__name__)


def filter_tool_args(func, args_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter the args_dict to include only arguments that the function accepts.
    Prevents 'unexpected keyword argument' errors.
    """
    sig = inspect.signature(func)
    valid_params = sig.parameters.keys()
    
    # If function has **kwargs, it accepts everything
    has_kwargs = any(
        p.kind == inspect.Parameter.VAR_KEYWORD 
        for p in sig.parameters.values()
    )
    if has_kwargs:
        return args_dict
        
    filtered = {k: v for k, v in args_dict.items() if k in valid_params}
    
    # Log if we had to strip anything for debugging
    stripped = set(args_dict.keys()) - set(filtered.keys())
    if stripped:
        logger.warning("tool_executor_args_stripped", tool=func.__name__, stripped=list(stripped))
        
    return filtered


async def tool_executor_node(state: AgentState, db: AsyncSession) -> AgentState:
    """
    LangGraph node: Tool Executor.
    Executes the tool call prepared by the Tool Selector.
    Injects the correct OAuth access token into tool kwargs.
    """
    pending = state.get("pending_tool_calls", [])

    if not pending:
        # No tool to execute — advance to next step
        return _advance_step(state)

    tool_call: ToolCall = pending[0]
    tool_name = tool_call["tool_name"]

    # If awaiting user confirmation and not yet confirmed, pause
    if tool_call.get("requires_confirmation") and state.get("awaiting_confirmation"):
        if state.get("confirmed") is None:
            logger.info("tool_executor_waiting_for_confirmation", tool=tool_name)
            return state  # Graph will stay here until confirmed
        if state.get("confirmed") is False:
            # User rejected — skip this tool
            tool_call = {**tool_call, "status": "error", "error": "User rejected this action."}
            return _complete_tool(state, tool_call, result={"success": False, "error": "Rejected by user."})

    # Get the tool function
    tool_fn = get_tool_fn(tool_name)
    if not tool_fn:
        tool_call = {**tool_call, "status": "error", "error": f"Tool {tool_name} not found."}
        return _complete_tool(state, tool_call, result={"success": False, "error": f"Unknown tool: {tool_name}"})

    # Get OAuth token for the provider
    provider = get_provider_for_tool(tool_name)
    access_token = None
    if provider:
        access_token = await get_valid_token(
            db=db,
            user_id=uuid.UUID(state["user_id"]),
            provider=provider,
        )
        if not access_token:
            error_msg = f"Not connected to {provider}. Please connect via Settings → Integrations."
            tool_call = {**tool_call, "status": "error", "error": error_msg}
            return _complete_tool(state, tool_call, result={"success": False, "error": error_msg})

    # Execute the tool
    logger.info("tool_executor_running", tool=tool_name, provider=provider)
    try:
        kwargs: Dict[str, Any] = dict(tool_call.get("tool_input", {}))
        if access_token:
            kwargs["access_token"] = access_token

        # SAFETY SHIELD: Filter out unexpected keyword arguments
        filtered_kwargs = filter_tool_args(tool_fn, kwargs)
        
        result = await tool_fn(**filtered_kwargs)

        tool_call = {**tool_call, "status": "success", "tool_output": result}
        logger.info("tool_executor_success", tool=tool_name)

    except Exception as e:
        logger.error("tool_executor_error", tool=tool_name, error=str(e))
        result = {"success": False, "error": str(e)}
        tool_call = {**tool_call, "status": "error", "error": str(e), "tool_output": result}

    return _complete_tool(state, tool_call, result=result)


def _complete_tool(state: AgentState, tool_call: ToolCall, result: Any) -> AgentState:
    """Mark tool as complete and update state."""
    completed = list(state.get("completed_tool_calls", [])) + [tool_call]

    # Build running summary of tool results for the reasoning node
    summary = state.get("tool_results_summary", "")
    status_icon = "✅" if tool_call["status"] == "success" else "❌"
    summary += f"\n{status_icon} **{tool_call['tool_name']}**: {_summarise_result(result)}"

    sse_events = list(state.get("sse_events", []))
    sse_events.append({
        "event": "tool_result" if tool_call["status"] == "success" else "tool_error",
        "data": {
            "tool_name": tool_call["tool_name"],
            "status": tool_call["status"],
            "result_summary": _summarise_result(result),
            "error": tool_call.get("error"),
        },
    })

    plan = list(state.get("plan", []))
    idx = state.get("current_step_index", 0)
    if idx < len(plan):
        plan[idx] = {**plan[idx], "completed": True}

    return {
        **state,
        "plan": plan,
        "pending_tool_calls": [],
        "completed_tool_calls": completed,
        "tool_results_summary": summary.strip(),
        "awaiting_confirmation": False,
        "confirmed": None,
        "sse_events": sse_events,
    }


def _advance_step(state: AgentState) -> AgentState:
    """Move to the next plan step (no-tool step advances immediately)."""
    plan = list(state.get("plan", []))
    idx = state.get("current_step_index", 0)
    if idx < len(plan):
        plan[idx] = {**plan[idx], "completed": True}
    return {**state, "plan": plan, "current_step_index": idx + 1}


def _summarise_result(result: Any) -> str:
    """Create a short human-readable summary of a tool result."""
    if not isinstance(result, dict):
        return str(result)[:200]
    if not result.get("success", True):
        return f"Error: {result.get('error', 'unknown')}"

    # Custom summaries per result type
    if "emails" in result:
        return f"Fetched {result.get('count', len(result['emails']))} emails"
    if "files" in result:
        return f"Found {result.get('count', len(result['files']))} Drive files"
    if "events" in result:
        return f"Found {result.get('count', len(result['events']))} calendar events"
    if "event" in result:
        ev = result["event"]
        meet = ev.get("meet_link") or ev.get("hangout_link") or ""
        link_info = f" | Meet link: {meet}" if meet else ""
        return f"Created event: {ev.get('summary', 'event')} at {ev.get('start', '?')}{link_info}"
    if "messages" in result:
        return f"Fetched {len(result.get('messages', []))} messages"
    if "results" in result:
        return f"Found {len(result.get('results', []))} Notion results"
    if "content" in result:
        chars = result.get("char_count", len(result.get("content", "")))
        return f"Read document ({chars:,} chars)"
    if "transcript" in result:
        return f"Got Zoom transcript ({result.get('char_count', 0):,} chars)"
    return "Completed successfully"
