"""
Integrations Route — shows which OAuth providers are connected.
GET /api/integrations/status → returns connected/disconnected per provider
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, OAuthToken
from app.models.schemas import IntegrationsStatusResponse, IntegrationStatus
from app.routes.auth import get_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/integrations", tags=["integrations"])

PROVIDERS = ["google", "slack", "notion", "zoom"]


@router.get("/status", response_model=IntegrationsStatusResponse)
async def get_integration_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return connection status for all supported OAuth providers."""
    result = await db.execute(
        select(OAuthToken).where(OAuthToken.user_id == current_user.id)
    )
    tokens = {t.provider: t for t in result.scalars().all()}

    statuses = []
    for provider in PROVIDERS:
        token = tokens.get(provider)
        statuses.append(IntegrationStatus(
            provider=provider,
            connected=token is not None,
            scope=token.scope if token else None,
            expires_at=token.expires_at if token else None,
        ))

    return IntegrationsStatusResponse(integrations=statuses)


@router.delete("/{provider}")
async def disconnect_integration(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove stored OAuth token to disconnect an integration."""
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == current_user.id,
            OAuthToken.provider == provider,
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"{provider} is not connected")

    await db.delete(token)
    await db.commit()
    logger.info("integration_disconnected", provider=provider, user_id=str(current_user.id))
    return {"success": True, "message": f"{provider} disconnected"}
