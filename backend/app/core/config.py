"""
Core application configuration using Pydantic Settings.
All values are loaded from environment variables / .env file.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────
    app_name: str = "Omni Copilot"
    app_version: str = "1.0.0"
    debug: bool = False
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # ── CORS ──────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    # ── Security ──────────────────────────────────────────────
    secret_key: str = Field(default="change-me-in-production-32-chars!!")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── Database ──────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/omni_copilot"

    # ── LLM providers ─────────────────────────────────────────
    groq_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    llm_provider: str = "groq"           # groq | openai | gemini
    llm_model: str = "llama-3.3-70b-versatile"

    # ── Google OAuth ──────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_scopes: str = (
        "openid email profile "
        "https://www.googleapis.com/auth/drive.file "
        "https://www.googleapis.com/auth/drive.readonly "
        "https://www.googleapis.com/auth/documents.readonly "
        "https://www.googleapis.com/auth/gmail.modify "
        "https://www.googleapis.com/auth/calendar"
    )

    @property
    def google_scopes_list(self) -> List[str]:
        return self.google_scopes.split()

    # ── Slack OAuth ───────────────────────────────────────────
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_redirect_uri: str = "http://localhost:8000/api/auth/slack/callback"
    slack_signing_secret: str = ""

    # ── Notion OAuth ──────────────────────────────────────────
    notion_client_id: str = ""
    notion_client_secret: str = ""
    notion_redirect_uri: str = "http://localhost:8000/api/auth/notion/callback"

    # ── Zoom OAuth (Server-to-Server) ────────────────────────
    zoom_account_id: str = ""
    zoom_client_id: str = ""
    zoom_client_secret: str = ""
    zoom_redirect_uri: str = "http://localhost:8000/api/auth/zoom/callback"

    # ── Logging ───────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "logs/omni_copilot.log"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
