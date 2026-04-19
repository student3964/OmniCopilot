"""
AgentState — the shared state TypedDict passed between all LangGraph nodes.
Every node reads from and writes to this state.
"""

from typing import Any, Dict, List, Optional, TypedDict
import uuid


class PlanStep(TypedDict):
    step_number: int
    description: str
    tool_name: Optional[str]
    tool_input: Optional[Dict[str, Any]]
    completed: bool
    result: Optional[Any]


class ToolCall(TypedDict):
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Optional[Any]
    status: str        # pending | running | success | error
    error: Optional[str]
    requires_confirmation: bool
    confirm_id: Optional[str]


class AgentState(TypedDict):
    # ── Identity ──────────────────────────────────────────────
    user_id: str                          # UUID of authenticated user
    conversation_id: str                  # UUID of conversation

    # ── Input ─────────────────────────────────────────────────
    user_query: str                       # Original user query/message
    chat_history: List[Dict[str, str]]    # Previous messages [{role, content}]

    # ── Planning ──────────────────────────────────────────────
    plan: List[PlanStep]                  # Decomposed task steps
    current_step_index: int               # Which step we're executing

    # ── Tool Execution ────────────────────────────────────────
    pending_tool_calls: List[ToolCall]    # Tools queued for execution
    completed_tool_calls: List[ToolCall]  # History of all executed tools
    tool_results_summary: str            # Running summary of tool results
    awaiting_confirmation: bool          # True when waiting for user to confirm
    confirmation_id: Optional[str]       # ID for the pending confirmation
    confirmed: Optional[bool]            # User's yes/no answer
    confirmed_tool_name: Optional[str]   # Pre-filled tool name when resuming
    confirmed_tool_input: Optional[dict] # Pre-filled tool input when resuming

    # ── Reasoning ─────────────────────────────────────────────
    reasoning_notes: str                 # LLM's internal reasoning accumulation
    iterations: int                      # Loop iteration counter (prevent infinite loops)
    max_iterations: int                  # Limit (default 8)

    # ── Output ────────────────────────────────────────────────
    final_response: str                  # Final answer to display to user
    error: Optional[str]                 # Error message if something went wrong

    # ── Streaming (not persisted, used for SSE) ───────────────
    sse_events: List[Dict[str, Any]]     # Accumulated SSE events to stream
