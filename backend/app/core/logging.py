"""
Structured logging setup using structlog + rich.
Provides consistent JSON-structured logs in production and
pretty colored logs in development.
"""

import logging
import sys
from pathlib import Path
import structlog
from rich.logging import RichHandler
from app.core.config import settings


def setup_logging() -> None:
    """Configure structlog and stdlib logging."""

    # ── Ensure log directory exists ───────────────────────────
    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # ── Shared processors ─────────────────────────────────────
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.debug:
        # Pretty-print for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        handler = RichHandler(
            rich_tracebacks=True,
            show_time=False,
            show_path=True,
            markup=True,
        )
    else:
        # JSON for production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
        handler = logging.FileHandler(settings.log_file)

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ── Root stdlib logger ────────────────────────────────────
    logging.basicConfig(
        level=log_level,
        handlers=[handler, logging.StreamHandler(sys.stdout)],
        format="%(message)s",
    )

    # Suppress noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a named structured logger."""
    return structlog.get_logger(name)
