"""Environment-based configuration for the restaurant bot.

Loads `.env` from the project root via python-dotenv and exposes the settings
used across the app. Secrets are never hardcoded.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
MENU_PATH = DATA_DIR / "menu.md"
DB_PATH = DATA_DIR / "menu.db"
CHROMA_DIR = DATA_DIR / "chroma"
STATIC_DIR = BASE_DIR / "app" / "kds" / "static"

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def has_openai_key() -> bool:
    """True when an OpenAI API key is present in the environment."""
    return bool(OPENAI_API_KEY)


def require_openai_key() -> str:
    """Return the OpenAI key or raise a clear, friendly error."""
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Copy `.env.example` to `.env`, add "
            "your key, then retry. Menu parsing (non-LLM), SQLite, the dashboard "
            "and the server all work without a key; only LLM calls and RAG need it."
        )
    return OPENAI_API_KEY


def has_telegram_token() -> bool:
    """True when a Telegram bot token is present in the environment."""
    return bool(TELEGRAM_BOT_TOKEN)


def redact(value: str) -> str:
    """Mask a secret so it never lands in logs (keys, tokens)."""
    if not value:
        return ""
    return f"{value[:4]}...{value[-4:]}"


def setup_logging() -> None:
    """Configure the root logger for the whole app (call once, at boot).

    Reads LOG_LEVEL from the environment (DEBUG/INFO/WARNING/ERROR), defaulting
    to INFO. The level applies app-wide. Secrets are never logged: settings are
    reported as booleans, and callers must redact any key/token before logging.
    """
    level = getattr(logging, LOG_LEVEL, None)
    if not isinstance(level, int):
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log_settings()
    logger.info("Logging level set to %s", logging.getLevelName(level))


def log_settings() -> None:
    """Log non-secret settings: paths, models, host/port and key presence only."""
    logger.info(
        "Paths: data=%s menu=%s db=%s chroma=%s static=%s",
        DATA_DIR, MENU_PATH, DB_PATH, CHROMA_DIR, STATIC_DIR,
    )
    logger.info(
        "Models: openai=%s embeddings=%s host=%s port=%s",
        OPENAI_MODEL, EMBEDDING_MODEL, HOST, PORT,
    )
    logger.info(
        "Secrets configured: openai_key=%s telegram_token=%s",
        has_openai_key(), has_telegram_token(),
    )
