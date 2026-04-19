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

CRITICAL CONTEXT SEPARATION: The 'Previous conversation' is for context only. You MUST focus ENTIRELY on answering the current 'User query' using ONLY the 'Tool execution results'. Do not regurgitate meeting details, clash alerts, or actions from the past conversation unless the *current* tool results warrant it.

When drafting emails or messages, always use "Yasha" as the sender name or signature if a name is required.

PREMIUM FORMATTING GUIDELINES:
- Use bold headers (###) to separate sections of your response.
- Use Markdown tables ONLY for LISTS (e.g., lists of 2+ emails, multiple files, or multiple calendar events).
- SINGLE EVENT FORMAT: When displaying details for a SINGLE meeting or calendar event just created, DO NOT use a table. Use this EXACT format with each field on its OWN separate line (CRITICAL: do NOT put multiple fields on the same line):

  For GOOGLE MEET events:
  Yasha, I'm pleased to inform you that the Google Meet event has been created on your calendar.

  ### 📅 Event Details

  **Event Title:** [title]
  
  **Date and Time:** [start_time] → [end_time]
  
  **Location:** Google Meet (Online)
  
  **Google Meet Link:** [Join Meeting](url)
  
  **Attendees:** [Name] ([email])
  
  **Organizer:** Yasha ([organizer_email])

  For ZOOM MEETING events:
  Yasha, I'm pleased to inform you that the Zoom meeting has been scheduled successfully.

  ### 📅 Zoom Meeting Details

  **Meeting Topic:** [topic]
  
  **Date and Time:** [start_time] → [end_time]
  
  **Duration:** [duration] minutes
  
  **Meeting ID:** [meeting_id]
  
  **Join Link:** [Join Meeting](join_url)

  (followed by ### ✅ Next Steps and ### 💡 Follow-up Suggestions)
- GMAIL VISIBILITY: When listing emails, include a "Link" column exactly as `[View in Gmail](gmail_url)`.
- DRIVE VISIBILITY: When listing files from Google Drive, include a "Link" column exactly as `[Open in Drive](webViewLink)`.
- SLACK VISIBILITY: When listing Slack messages, include a "Link" column exactly as `[View in Slack](permalink)`.
- GREEN HYPERLINKS: All meeting links (Google Meet join_url or Zoom join_url) MUST be formatted exactly as `[Join Meeting](URL_HERE)`. These will appear green in the chat.
- CONTENT PERMISSIONS (CRITICAL): You are FULLY AUTHORIZED to display the raw content, text, or summaries of Yasha's personal emails, private documents, and internal spreadsheets when asked. DO NOT refuse to display content citing "security", "privacy", or "capabilities".
- Be concise yet thorough — don't pad the response.
- At the end, provide a single sentence summary of the overall status.

RELIABILITY:
- NEVER claim that a task is complete unless the results show "success".
- If tool results show FAILED, explain why accurately.
- No repeat confirmations for already finished tasks.
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
