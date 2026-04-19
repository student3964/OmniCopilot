"""
Omni Copilot — FastAPI Application Entry Point
Startup: DB table creation, logging setup, CORS, route registration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.models.db import create_tables

# Routes
from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.integrations import router as integrations_router
from app.routes.upload import router as upload_router

# Setup logging before anything else
setup_logging()
logger = get_logger(__name__)


# ── Lifespan ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("omni_copilot_starting", version=settings.app_version)

    # Create DB tables if they don't exist
    await create_tables()
    logger.info("database_tables_ready")

    yield

    logger.info("omni_copilot_shutting_down")


# ── App instance ───────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Unified AI assistant connecting Google, Slack, Notion and more.",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)


# ── CORS ───────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-Id"],
)


# ── Routes ─────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(integrations_router)
app.include_router(upload_router)


# ── Health check ───────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "llm_provider": settings.llm_provider,
    }


# ── Global error handler ───────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": str(exc)}},
    )
