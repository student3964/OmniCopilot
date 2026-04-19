"""
Reasoning Node — evaluates tool results and decides whether to continue
looping through plan steps or finalize the response.
"""

from app.agents.state import AgentState
from app.services.llm_service import get_llm
from app.core.logging import get_logger
from langchain_core.messages import HumanMessage, SystemMessage

logger = get_logger(__name__)

REASONING_SYSTEM_PROMPT = """You are the Reasoning Engine for Omni Copilot.
Your job is to evaluate the results collected so far and decide the next action.

You will receive:
- The original user query
- The execution plan
- Tool results collected so far

Respond with a JSON object:
{
  "decision": "continue" | "done" | "error",
  "next_step_notes": "Brief note about what to do next (if continuing)",
  "reasoning": "Your brief reasoning (1-2 sentences)"
}

Rules:
- Return "done" if all necessary information has been collected to answer the user.
- Return "continue" if more steps are needed.
- Return "error" only if there's an unrecoverable error.
- Do NOT include anything outside the JSON.
"""


async def reasoning_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Reasoning.
    Evaluates current state and decides: continue looping or finalize.
    """
    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)
    iterations = state.get("iterations", 0) + 1
    max_iter = state.get("max_iterations", 8)

    # ── Guard: max iterations ─────────────────────────────────
    if iterations >= max_iter:
        logger.warning("reasoning_max_iterations_reached", iterations=iterations)
        return {
            **state,
            "iterations": iterations,
            "reasoning_notes": state.get("reasoning_notes", "") + "\n[Max iterations reached — finalizing.]",
        }

    # ── Guard: all steps completed ────────────────────────────
    completed_count = sum(1 for s in plan if s.get("completed"))
    all_done = current_index >= len(plan)

    if all_done:
        logger.info("reasoning_all_steps_done", completed=completed_count)
        return {
            **state,
            "iterations": iterations,
            "reasoning_notes": state.get("reasoning_notes", "") + "\nAll plan steps completed.",
        }

    # ── LLM reasoning call ────────────────────────────────────
    # Only advance the index if the current step was marked as completed by the executor 
    # OR if it's a reasoning-only step (tool_name is None).
    is_step_done = plan[current_index].get("completed", False) or plan[current_index].get("tool_name") is None
    
    # [LOOP FIX]: If this was a confirmed action and it's done, FORCE FINALIZE.
    if is_step_done and state.get("confirmed"):
        logger.info("reasoning_confirmed_action_finished_forcing_done")
        return {
            **state,
            "current_step_index": len(plan), # This triggers finalize
            "iterations": iterations,
            "reasoning_notes": state.get("reasoning_notes", "") + "\nConfirmed action completed successfully. Finalizing conversation.",
        }

    prompt = _build_reasoning_prompt(state, current_index + 1 if is_step_done else current_index, len(plan))

    try:
        llm = get_llm()
        response = await llm.ainvoke([
            SystemMessage(content=REASONING_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        import json
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())

        decision = data.get("decision", "continue")
        notes = data.get("reasoning", "")

        logger.info("reasoning_decision", decision=decision, step=current_index, is_done=is_step_done)

        new_notes = state.get("reasoning_notes", "") + f"\nStep {current_index + 1}: {notes}"

        # Calculate final index based on step completion AND decision
        final_index = current_index + 1 if is_step_done else current_index
        if decision == "done":
            final_index = len(plan)

        return {
            **state,
            "current_step_index": final_index,
            "iterations": iterations,
            "reasoning_notes": new_notes,
        }

    except Exception as e:
        logger.error("reasoning_node_error", error=str(e))
        # On error, advance anyway
        return {
            **state,
            "current_step_index": current_index + 1,
            "iterations": iterations,
            "reasoning_notes": state.get("reasoning_notes", "") + f"\nReasoning error: {e}",
        }


def _build_reasoning_prompt(state: AgentState, current_index: int, total_steps: int) -> str:
    plan_text = "\n".join(
        f"Step {s['step_number']}: {s['description']} [{'✅ done' if s.get('completed') else '⏳ pending'}]"
        for s in state.get("plan", [])
    )
    return f"""Original query: {state['user_query']}

Plan ({current_index}/{total_steps} steps done):
{plan_text}

Tool results collected so far:
{state.get('tool_results_summary', 'None yet')}

Should I continue to the next step or finalize the response?"""


def _extract_last_result(state: AgentState) -> str:
    completed = state.get("completed_tool_calls", [])
    if completed:
        last = completed[-1]
        output = last.get("tool_output", {})
        if isinstance(output, dict):
            return str(output)[:500]
    return ""


def should_continue(state: AgentState) -> str:
    """
    LangGraph conditional edge function.
    Returns 'continue' to keep looping or 'finalize' to end.
    """
    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)
    iterations = state.get("iterations", 0)
    max_iter = state.get("max_iterations", 8)
    awaiting = state.get("awaiting_confirmation", False)

    # If waiting for user confirmation, pause the graph
    if awaiting and state.get("confirmed") is None:
        return "wait_confirm"

    # Cap iterations
    if iterations >= max_iter:
        return "finalize"

    # All plan steps done
    if current_index >= len(plan):
        return "finalize"

    return "continue"
