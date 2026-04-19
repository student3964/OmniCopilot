"""
LangGraph Agent Graph — wires all nodes into the multi-step reasoning loop.

Flow:
  START → planner → tool_selector → tool_executor → reasoning
                         ↑                               |
                         └───── (continue loop) ─────────┘
                                                         |
                                               (finalize) ↓
                                                      responder → END
"""

from typing import AsyncGenerator, Any, Dict, Optional
from functools import partial

from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState
from app.agents.nodes.planner import planner_node
from app.agents.nodes.tool_selector import tool_selector_node
from app.agents.nodes.tool_executor import tool_executor_node
from app.agents.nodes.reasoning import reasoning_node, should_continue
from app.agents.nodes.responder import responder_node
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_agent_graph(db: AsyncSession) -> StateGraph:
    """
    Build and compile the LangGraph StateGraph.
    The db session is injected into tool_executor via functools.partial.
    """

    # Bind db session to tool_executor
    executor_with_db = partial(tool_executor_node, db=db)

    # ── Build graph ───────────────────────────────────────────
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("planner", planner_node)
    graph.add_node("tool_selector", tool_selector_node)
    graph.add_node("tool_executor", executor_with_db)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("responder", responder_node)

    # ── Entry point ────────────────────────────────────────────
    graph.set_entry_point("planner")

    # ── Linear edges ──────────────────────────────────────────
    graph.add_edge("planner", "tool_selector")
    graph.add_edge("tool_selector", "tool_executor")
    graph.add_edge("tool_executor", "reasoning")

    # ── Conditional loop edge ─────────────────────────────────
    graph.add_conditional_edges(
        "reasoning",
        should_continue,
        {
            "continue": "tool_selector",   # Loop: select tool for next step
            "finalize": "responder",        # Done: generate final answer
            "wait_confirm": "responder",    # Paused for confirmation (responder will emit confirm event)
        },
    )

    # ── Terminal edge ─────────────────────────────────────────
    graph.add_edge("responder", END)

    return graph.compile()


async def run_agent(
    user_query: str,
    user_id: str,
    conversation_id: str,
    chat_history: list,
    db: AsyncSession,
    confirmed: Optional[bool] = None,
    confirm_id: Optional[str] = None,
    confirmed_tool_name: Optional[str] = None,
    confirmed_tool_input: Optional[dict] = None,
    plan: Optional[list] = None,
    current_step_index: int = 0,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Run the agent graph and yield SSE events as they are produced.

    Yields dicts of shape: {"event": str, "data": dict}
    """
    # Build initial state
    initial_state: AgentState = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "user_query": user_query,
        "chat_history": chat_history,
        "plan": plan or [],
        "current_step_index": current_step_index,
        "pending_tool_calls": [],
        "completed_tool_calls": [],
        "tool_results_summary": "",
        "awaiting_confirmation": True if confirmed is not None else False,
        "confirmation_id": confirm_id,
        "confirmed": confirmed,
        "confirmed_tool_name": confirmed_tool_name,
        "confirmed_tool_input": confirmed_tool_input,
        "reasoning_notes": "",
        "iterations": 0,
        "max_iterations": 8,
        "final_response": "",
        "error": None,
        "sse_events": [],
    }

    compiled_graph = build_agent_graph(db)
    emitted_event_count = 0

    logger.info("agent_run_start", query=user_query[:80], user_id=user_id)

    try:
        # Stream graph state updates
        async for state_update in compiled_graph.astream(initial_state):
            # Each update is a dict: {node_name: updated_state}
            for node_name, node_state in state_update.items():
                if not isinstance(node_state, dict):
                    continue

                new_events = node_state.get("sse_events", [])
                # Yield only new events (avoid duplicates)
                for event in new_events[emitted_event_count:]:
                    yield event
                    emitted_event_count = len(new_events)

    except Exception as e:
        logger.error("agent_run_error", error=str(e))
        yield {
            "event": "error",
            "data": {"message": f"Agent error: {str(e)}"},
        }
