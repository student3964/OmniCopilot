"""
Pydantic schemas for API request/response validation.
Separate from ORM models — used at the HTTP layer.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, EmailStr, Field


# ═══════════════════════════════════════════════════════════════
# User Schemas
# ═══════════════════════════════════════════════════════════════

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# OAuth / Token Schemas
# ═══════════════════════════════════════════════════════════════

class OAuthTokenRead(BaseModel):
    provider: str
    scope: Optional[str]
    expires_at: Optional[datetime]

    model_config = {"from_attributes": True}


class IntegrationStatus(BaseModel):
    provider: str
    connected: bool
    scope: Optional[str] = None
    expires_at: Optional[datetime] = None


class IntegrationsStatusResponse(BaseModel):
    integrations: List[IntegrationStatus]


# ═══════════════════════════════════════════════════════════════
# Message / Chat Schemas
# ═══════════════════════════════════════════════════════════════

class ChatMessageIn(BaseModel):
    """Incoming message from the user."""
    content: str = Field(..., min_length=1, max_length=10_000)
    conversation_id: Optional[uuid.UUID] = None
    confirmed: Optional[bool] = None
    confirm_id: Optional[str] = None


class ToolCallInfo(BaseModel):
    """Represents a single tool call with its result (for display)."""
    tool_name: str
    tool_input: Dict[str, Any] = Field(default_factory=dict)
    tool_output: Optional[Any] = None
    status: Literal["pending", "running", "success", "error"] = "pending"
    error: Optional[str] = None


class MessageRead(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    tool_calls: Optional[List[ToolCallInfo]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationRead(BaseModel):
    id: uuid.UUID
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationWithMessages(ConversationRead):
    messages: List[MessageRead] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# SSE Event Schemas (streamed to frontend)
# ═══════════════════════════════════════════════════════════════

class SSEEventType:
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    CONFIRM_REQUEST = "confirm_request"     # Sensitive action needs approval
    THINKING = "thinking"
    DELTA = "delta"                         # Streaming text token
    DONE = "done"
    ERROR = "error"


class SSEEvent(BaseModel):
    event: str
    data: Dict[str, Any] = Field(default_factory=dict)


class ConfirmActionRequest(BaseModel):
    """Frontend sends this to approve/reject a sensitive action."""
    confirm_id: str
    approved: bool


# ═══════════════════════════════════════════════════════════════
# Auth Schemas
# ═══════════════════════════════════════════════════════════════

class TokenResponse(BaseModel):
    """JWT access token returned after OAuth login."""
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class OAuthCallbackParams(BaseModel):
    code: str
    state: str


# ═══════════════════════════════════════════════════════════════
# Generic Response
# ═══════════════════════════════════════════════════════════════

class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "OK"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
