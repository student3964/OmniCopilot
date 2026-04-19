"""
Chat Routes — SSE streaming chat endpoint + confirmation handler.
POST /api/chat       → stream agent events via SSE
POST /api/chat/confirm → approve/reject sensitive action
GET  /api/chat/conversations → list conversations
GET  /api/chat/conversations/{id}/messages → get messages
"""

import json
import uuid
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import get_db, User
from app.models.schemas import (
    ChatMessageIn, ConversationRead, ConversationWithMessages,
    MessageRead, ConfirmActionRequest, SuccessResponse,
)
from app.agents.graph import run_agent
from app.services.chat_service import (
    get_or_create_conversation, get_conversation_history,
    save_message, update_conversation_title, list_conversations,
    rename_conversation,
)
from app.routes.auth import get_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Pending confirmation store {confirm_id: asyncio.Event}
# In production, use Redis pub/sub
import asyncio
_pending_confirmations: dict[str, asyncio.Event] = {}
_confirmation_results: dict[str, bool] = {}
_pending_tool_calls: dict[str, dict] = {} # {confirm_id: {tool_name, tool_input}}


# ═══════════════════════════════════════════════════════════════
# SSE Chat Endpoint
# ═══════════════════════════════════════════════════════════════

@router.post("/")
async def chat(
    body: ChatMessageIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Main chat endpoint. Streams Server-Sent Events (SSE) back to the client.
    Each event is JSON-encoded with an 'event' type and 'data' payload.

    Event types:
    - thinking      : Agent is planning
    - tool_start    : A tool is being called
    - tool_result   : Tool completed successfully
    - tool_error    : Tool failed
    - confirm_request: Sensitive action needs approval
    - done          : Final response ready
    - error         : Unrecoverable error
    """
    # Get or create conversation
    conversation = await get_or_create_conversation(
        db, current_user.id, body.conversation_id
    )

    # Auto-title conversation from first message
    await update_conversation_title(db, conversation.id, body.content[:80])

    # Load chat history
    history_msgs = await get_conversation_history(db, conversation.id, limit=20)
    chat_history = [
        {"role": msg.role, "content": msg.content}
        for msg in history_msgs
    ]

    # Save user message
    await save_message(db, conversation.id, "user", body.content)

    async def event_stream() -> AsyncGenerator[str, None]:
        full_response = ""
        tool_calls_log = []

        try:
            async for event in run_agent(
                user_query=body.content,
                user_id=str(current_user.id),
                conversation_id=str(conversation.id),
                chat_history=chat_history,
                db=db,
                confirmed=body.confirmed,
                confirm_id=body.confirm_id,
                confirmed_tool_name=_pending_tool_calls.get(body.confirm_id, {}).get("tool_name") if body.confirmed else None,
                confirmed_tool_input=_pending_tool_calls.get(body.confirm_id, {}).get("tool_input") if body.confirmed else None,
                plan=_pending_tool_calls.get(body.confirm_id, {}).get("plan", []) if body.confirmed else None,
                current_step_index=_pending_tool_calls.get(body.confirm_id, {}).get("current_step_index", 0) if body.confirmed else 0,
            ):
                event_type = event.get("event", "")
                event_data = event.get("data", {})

                # Track tool calls for persistence
                if event_type == "tool_result":
                    tool_calls_log.append({
                        "tool_name": event_data.get("tool_name"),
                        "status": event_data.get("status"),
                        "result_summary": event_data.get("result_summary"),
                    })

                # Capture final response
                if event_type == "done":
                    full_response = event_data.get("response", "")

                # Register confirmation event
                if event_type == "confirm_request":
                    confirm_id = event_data.get("confirm_id", "")
                    _pending_confirmations[confirm_id] = asyncio.Event()
                    # Store the tool call details for later resumption
                    _pending_tool_calls[confirm_id] = {
                        "tool_name": event_data.get("tool_name"),
                        "tool_input": event_data.get("tool_input"),
                        "plan": event_data.get("plan", []),
                        "current_step_index": event_data.get("current_step_index", 0),
                    }

                # Stream event to client
                sse_payload = f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
                yield sse_payload

            # Also send conversation_id so frontend can track it
            yield f"event: meta\ndata: {json.dumps({'conversation_id': str(conversation.id)})}\n\n"

        except Exception as e:
            logger.error("chat_stream_error", error=str(e))
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
            full_response = f"Error: {str(e)}"

        finally:
            # Persist assistant response
            if full_response:
                await save_message(
                    db, conversation.id, "assistant", full_response,
                    tool_calls=tool_calls_log if tool_calls_log else None,
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ═══════════════════════════════════════════════════════════════
# Confirmation Endpoint
# ═══════════════════════════════════════════════════════════════

@router.post("/confirm", response_model=SuccessResponse)
async def confirm_action(
    body: ConfirmActionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Approve or reject a pending sensitive action.
    The agent graph pauses until this endpoint is called.
    """
    confirm_id = body.confirm_id
    if confirm_id not in _pending_confirmations:
        raise HTTPException(status_code=404, detail="Confirmation request not found or already resolved")

    _confirmation_results[confirm_id] = body.approved
    _pending_confirmations[confirm_id].set()

    action = "approved" if body.approved else "rejected"
    logger.info("action_confirmed", confirm_id=confirm_id, action=action)
    return SuccessResponse(message=f"Action {action}")


# ═══════════════════════════════════════════════════════════════
# Conversation History Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/conversations", response_model=list[ConversationRead])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all conversations for the current user."""
    convs = await list_conversations(db, current_user.id)
    return convs


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
async def get_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch messages for a specific conversation."""
    msgs = await get_conversation_history(db, conversation_id, limit=50)
    return msgs


@router.delete("/conversations/{conversation_id}", response_model=SuccessResponse)
async def delete_conv(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific conversation."""
    from app.services.chat_service import delete_conversation
    deleted = await delete_conversation(db, current_user.id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return SuccessResponse(message="Conversation deleted")


from app.models.schemas import ConversationUpdate

@router.patch("/conversations/{conversation_id}", response_model=SuccessResponse)
async def rename_conv(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually rename a conversation."""
    success = await rename_conversation(db, current_user.id, conversation_id, body.title)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return SuccessResponse(message="Conversation renamed")
