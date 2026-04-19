"""
Responder Node — generates the final markdown response from all collected tool results.
"""

from app.agents.state import AgentState
from app.services.llm_service import get_llm
from app.core.logging import get_logger
from langchain_core.messages import HumanMessage, SystemMessage

logger = get_logger(__name__)

RESPONDER_SYSTEM_PROMPT = """You are Omni Copilot, a powerful AI assistant that helps the user Yasha manage their digital workspace.

You have just executed a series of tools to gather information. Now synthesize everything into a clear, helpful, and well-formatted response for Yasha.
When drafting emails or messages, always use "Yasha" as the sender name or signature if a name is required.

Guidelines:
- Use markdown formatting (headers, bullet points, tables) where appropriate
- Be concise yet thorough — don't pad the response
- If you fetched emails, list them clearly. If the user asked to fetch, show, or read specifically, ALWAYS include the full body content in your response rather than just a summary.
- If you fetched calendar events, list them with time, title, attendees.
- If you read documents, provide the key points or summary requested.
- NEVER claim that a task is complete (especially sending emails or creating calendar events) unless the "Tool execution results" section explicitly shows a status of "success" for that specific action.
- If the "Agent Notes" section mentions missing attendees or missing information, your ENTIRE response should be a friendly, conversational request asking the user for that specific information. Do NOT say "unable to arrange" — instead ask for what's needed.
- If the tool execution results show "FAILED" or "error", explain that the task could not be completed and report the error accurately.
- Never reveal raw API responses — always translate to human-friendly language.
- End with any follow-up suggestions if relevant.
- RELY COMPLETELY on the "Tool execution results" section for the status of actions.
- CLICKABLE HYPERLINKS: When reporting a meeting link (Google Meet join_url, Zoom join_url, or event html_link), ALWAYS format it as a clickable markdown hyperlink like this: [Join Meeting](URL_HERE).
- GOOGLE MEET LINKS: When reporting or notifying about a Google Meet conference, ALWAYS use the specific "google_meet_link" or "join_url" from the tool output.
- NO REPEAT CONFIRMATIONS: If a delicate action (like creating an event or sending an email) has already been executed successfully (shows "success" in results), do NOT ask the user for approval or confirmation for that action again. The task is finished.
"""


async def responder_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Responder.
    Produces the final user-facing markdown response.
    """
    logger.info("responder_node_start")

    # Build context from all collected results
    tool_summary = state.get("tool_results_summary", "")
    completed_calls = state.get("completed_tool_calls", [])

    # Build detailed tool outputs for the LLM
    detailed_results = []
    for call in completed_calls:
        tool_name = call.get("tool_name", "")
        output = call.get("tool_output", {})
        status = call.get("status", "")

        if status == "success" and isinstance(output, dict):
            detailed_results.append(
                f"### {tool_name} result:\n```json\n{_truncate_output(output)}\n```"
            )
        elif status == "error":
            detailed_results.append(
                f"### {tool_name} — FAILED: {call.get('error', 'unknown error')}"
            )

    detailed_text = "\n\n".join(detailed_results) if detailed_results else "No tools were executed."

    # Build chat history context
    history_str = ""
    for msg in state.get("chat_history", [])[-6:]:
        history_str += f"**{msg['role'].upper()}**: {msg['content']}\n\n"

    user_prompt = f"""User query: {state['user_query']}

Previous conversation:
{history_str}

Tool execution results:
{detailed_text}

Agent Notes:
{state.get('reasoning_notes', 'None')}

Planner/System Errors:
{state.get('error', 'None')}

IMPORTANT: If Agent Notes mention missing attendees AND we are NOT currently awaiting_confirmation, your response must ask the user for attendee names and email addresses in a friendly, conversational way. Do NOT say the task failed.
If we ARE awaiting_confirmation, your response should be focused entirely on the confirmation task and ignore any 'Missing attendees' notes.

{f"CRITICAL: The system has gathered all necessary details and is currently PAUSED waiting for the user to click the Approve/Reject button. Your response MUST acknowledge that you have everything and are just waiting for their approval to proceed. DO NOT ask for more info." if state.get('awaiting_confirmation') else ""}

Now write a clear, helpful response to the user's query based on the above information. Respond as Omni Copilot.
"""

    try:
        llm = get_llm()
        response = await llm.ainvoke([
            SystemMessage(content=RESPONDER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        final_response = response.content.strip()
        logger.info("responder_node_done", chars=len(final_response))

    except Exception as e:
        logger.error("responder_node_error", error=str(e))
        final_response = (
            f"I encountered an error while generating the response: {str(e)}\n\n"
            f"Here is what I collected:\n{tool_summary}"
        )

    sse_events = list(state.get("sse_events", []))
    sse_events.append({
        "event": "done",
        "data": {"response": final_response},
    })

    return {
        **state,
        "final_response": final_response,
        "sse_events": sse_events,
    }


def _truncate_output(output: dict, max_chars: int = 10000) -> str:
    """Serialize and truncate tool output for the LLM prompt (allows more for email content)."""
    import json
    try:
        text = json.dumps(output, indent=2, default=str)
        if len(text) > max_chars:
            return text[:max_chars] + "\n... [truncated]"
        return text
    except Exception:
        return str(output)[:max_chars]
