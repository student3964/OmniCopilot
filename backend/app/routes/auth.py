"""
Auth Routes — OAuth 2.0 flows for Google, Slack, and Notion.
Handles authorization URL generation → callback → token storage → JWT issuance.
"""

import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt

from app.models.db import get_db, User, OAuthToken
from app.models.schemas import TokenResponse, UserRead
from app.auth.google_oauth import (
    build_google_auth_url, exchange_google_code,
    get_google_user_info, compute_expiry, generate_state,
)
from app.auth.slack_oauth import build_slack_auth_url, exchange_slack_code
from app.auth.notion_oauth import build_notion_auth_url, exchange_notion_code
from app.auth.zoom_oauth import get_zoom_s2s_token
from app.services.token_service import save_token
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory state store (use Redis in production)
_oauth_states: dict[str, dict] = {}


# ── JWT helpers ────────────────────────────────────────────────

def create_jwt(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except Exception:
        return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency: extract and validate JWT from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth.split(" ", 1)[1]
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def _get_or_create_user(db: AsyncSession, email: str, name: str, avatar_url: str = "") -> User:
    """Upsert a user by email."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(email=email, name=name, avatar_url=avatar_url)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("user_created", email=email)
    else:
        if name:
            user.name = name
        if avatar_url:
            user.avatar_url = avatar_url
        await db.commit()

    return user


# ═══════════════════════════════════════════════════════════════
# Google OAuth
# ═══════════════════════════════════════════════════════════════

@router.get("/google/login")
async def google_login():
    """Step 1: Redirect user to Google OAuth consent screen."""
    state = generate_state()
    _oauth_states[state] = {"provider": "google"}
    auth_url = build_google_auth_url(state)
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Step 2: Handle Google OAuth callback, exchange code, create user + JWT."""
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    del _oauth_states[state]

    try:
        token_data = await exchange_google_code(code)
        user_info = await get_google_user_info(token_data["access_token"])
    except Exception as e:
        logger.error("google_callback_error", error=str(e))
        raise HTTPException(status_code=400, detail=f"Google auth failed: {str(e)}")

    user = await _get_or_create_user(
        db,
        email=user_info["email"],
        name=user_info.get("name", ""),
        avatar_url=user_info.get("picture", ""),
    )

    await save_token(db, user.id, "google", token_data)

    jwt_token = create_jwt(str(user.id))
    redirect_url = f"{settings.frontend_url}/auth/callback?token={jwt_token}"
    return RedirectResponse(url=redirect_url)


# ═══════════════════════════════════════════════════════════════
# Slack OAuth
# ═══════════════════════════════════════════════════════════════

@router.get("/slack/login")
async def slack_login(request: Request, token: Optional[str] = Query(None)):
    """Begin Slack OAuth — requires existing user session (JWT)."""
    state = generate_state()
    payload = decode_jwt(token) if token else None
    user_id = payload.get("sub") if payload else None
    _oauth_states[state] = {"provider": "slack", "user_id": user_id}
    auth_url = build_slack_auth_url(state)
    return RedirectResponse(url=auth_url)


@router.get("/slack/callback")
async def slack_callback(
    code: str = Query(...),
    state: str = Query(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Handle Slack OAuth callback and store bot token."""
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid Slack OAuth state")
    oauth_data = _oauth_states.pop(state)

    try:
        slack_data = await exchange_slack_code(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Slack auth failed: {str(e)}")

    user_id = oauth_data.get("user_id")

    if not user_id:
        redirect_url = f"{settings.frontend_url}/auth/callback?provider=slack&status=error"
    else:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            # Store bot token
            bot_token = slack_data.get("access_token", "")
            await save_token(db, user.id, "slack", {"access_token": bot_token, "raw": slack_data})
        redirect_url = f"{settings.frontend_url}/auth/callback?provider=slack&status=ok"

    return RedirectResponse(url=redirect_url)


# ═══════════════════════════════════════════════════════════════
# Notion OAuth
# ═══════════════════════════════════════════════════════════════

@router.get("/notion/login")
async def notion_login(token: Optional[str] = Query(None)):
    state = generate_state()
    payload = decode_jwt(token) if token else None
    user_id = payload.get("sub") if payload else None
    _oauth_states[state] = {"provider": "notion", "user_id": user_id}
    auth_url = build_notion_auth_url(state)
    return RedirectResponse(url=auth_url)


@router.get("/notion/callback")
async def notion_callback(
    code: str = Query(...),
    state: str = Query(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid Notion OAuth state")
    oauth_data = _oauth_states.pop(state)

    try:
        notion_data = await exchange_notion_code(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Notion auth failed: {str(e)}")

    user_id = oauth_data.get("user_id")

    if user_id:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            await save_token(db, user.id, "notion", {
                "access_token": notion_data.get("access_token", ""),
                "workspace_name": notion_data.get("workspace_name", ""),
            })

    return RedirectResponse(url=f"{settings.frontend_url}/auth/callback?provider=notion&status=ok")


# ═══════════════════════════════════════════════════════════════
# Zoom OAuth (Server-to-Server — no redirect needed)
# ═══════════════════════════════════════════════════════════════

@router.get("/zoom/login")
async def zoom_login(
    request: Request,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Connect Zoom using Server-to-Server OAuth.
    Directly fetches a token — no user redirect needed.
    Accepts JWT via ?token= query param (since browser redirect can't send headers).
    """
    try:
        zoom_data = await get_zoom_s2s_token()
    except Exception as e:
        logger.error("zoom_s2s_error", error=str(e))
        raise HTTPException(status_code=400, detail=f"Zoom connection failed: {str(e)}")

    # Find logged-in user from JWT query param (browser redirect can't send headers)
    jwt_token = token  # from Query param
    if not jwt_token:
        # Fallback: try Authorization header
        auth = request.headers.get("Authorization", "") if request else ""
        jwt_token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else ""
    
    payload = decode_jwt(jwt_token) if jwt_token else None

    if payload:
        result = await db.execute(select(User).where(User.id == payload["sub"]))
        user = result.scalar_one_or_none()
        if user:
            await save_token(db, user.id, "zoom", zoom_data)
            logger.info("zoom_connected", user_id=str(user.id))
    else:
        logger.warning("zoom_login_no_user", detail="No valid JWT found")

    return RedirectResponse(url=f"{settings.frontend_url}/auth/callback?provider=zoom&status=ok")


# ── Current user endpoint ──────────────────────────────────────

@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user
