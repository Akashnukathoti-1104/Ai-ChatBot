"""Configuration for Nani.

All deployment-specific details are read from environment variables so secrets and
personal contact details never need to be committed to the repository.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Tuple


def _value(*names: str, default: str = "") -> str:
    """Return the first non-empty environment value from ``names``."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _origins() -> Tuple[str, ...]:
    raw = os.getenv("ALLOWED_ORIGINS", "*").strip()
    origins = tuple(origin.strip() for origin in raw.split(",") if origin.strip())
    return origins or ("*",)


@dataclass(frozen=True)
class Settings:
    """Runtime settings.  Values marked secret are never returned by the API."""

    app_env: str
    bot_name: str
    bot_tagline: str
    bot_owner_name: str
    bot_owner_bio: str
    business_name: str
    support_email: str
    support_phone: str
    business_hours: str
    database_path: str
    allowed_origins: Tuple[str, ...]
    admin_token: str
    rate_limit_requests: int
    rate_limit_window_seconds: int
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    llm_timeout_seconds: int

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def cors_allows_credentials(self) -> bool:
        # Browsers reject Access-Control-Allow-Credentials with a wildcard origin.
        return "*" not in self.allowed_origins

    @property
    def public_profile(self) -> dict:
        """Only non-sensitive configuration safe to send to the chat UI."""
        return {
            "bot_name": self.bot_name,
            "tagline": self.bot_tagline,
            "owner_name": self.bot_owner_name,
            "owner_bio": self.bot_owner_bio,
            "business_name": self.business_name,
            "support_email": self.support_email,
            "support_phone": self.support_phone,
            "business_hours": self.business_hours,
            "ai_mode": "connected" if self.llm_enabled else "local",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per running process."""
    return Settings(
        app_env=_value("APP_ENV", default="development").lower(),
        bot_name=_value("BOT_NAME", default="Nani")[:60],
        bot_tagline=_value("BOT_TAGLINE", default="Your thoughtful AI assistant")[:160],
        bot_owner_name=_value("BOT_OWNER_NAME")[:120],
        bot_owner_bio=_value("BOT_OWNER_BIO")[:500],
        business_name=_value("BUSINESS_NAME")[:120],
        support_email=_value("SUPPORT_EMAIL")[:254],
        support_phone=_value("SUPPORT_PHONE")[:80],
        business_hours=_value("BUSINESS_HOURS")[:160],
        database_path=_value("DB_PATH", default="data/nani.db"),
        allowed_origins=_origins(),
        admin_token=_value("ADMIN_TOKEN"),
        rate_limit_requests=_integer("RATE_LIMIT_REQUESTS", 30, 1, 10000),
        rate_limit_window_seconds=_integer("RATE_LIMIT_WINDOW_SECONDS", 60, 1, 3600),
        # LLM_API_KEY works with any OpenAI-compatible provider. OPENAI_API_KEY
        # is accepted as a convenient alias for users who already have one.
        llm_api_key=_value("LLM_API_KEY", "OPENAI_API_KEY"),
        llm_base_url=_value("LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.openai.com/v1").rstrip("/"),
        llm_model=_value("LLM_MODEL", "OPENAI_MODEL", default="gpt-4o-mini")[:160],
        llm_temperature=_float("LLM_TEMPERATURE", 0.45, 0.0, 2.0),
        llm_max_tokens=_integer("LLM_MAX_TOKENS", 700, 64, 4000),
        llm_timeout_seconds=_integer("LLM_TIMEOUT_SECONDS", 45, 5, 120),
    )
