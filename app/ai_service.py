"""OpenAI-compatible model integration with a dependable local fallback."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from app.config import get_settings
from app.nlp_engine import detect_intent, generate_response, get_sentiment

logger = logging.getLogger(__name__)


class ModelProviderError(RuntimeError):
    """A model provider could not return a usable answer."""


def _system_prompt() -> str:
    settings = get_settings()
    profile_lines = [
        f"Your name is {settings.bot_name}.",
        f"Your role: {settings.bot_tagline}.",
        "Be warm, practical, accurate, and concise by default.",
        "Answer the user's actual question directly. Use clear formatting when it helps.",
        "Never invent personal, business, pricing, contact, or policy details that are not supplied below.",
        "If a question needs current information, say what you know may be out of date rather than pretending you browsed the web.",
        "Do not claim to have completed actions outside this chat.",
    ]
    if settings.bot_owner_name:
        profile_lines.append(f"Owner name: {settings.bot_owner_name}.")
    if settings.bot_owner_bio:
        profile_lines.append(f"Owner background: {settings.bot_owner_bio}")
    if settings.business_name:
        profile_lines.append(f"Business name: {settings.business_name}.")
    if settings.support_email:
        profile_lines.append(f"Support email: {settings.support_email}.")
    if settings.support_phone:
        profile_lines.append(f"Support phone: {settings.support_phone}.")
    if settings.business_hours:
        profile_lines.append(f"Business hours: {settings.business_hours}.")
    return "\n".join(profile_lines)


def _provider_messages(history: List[Dict[str, Any]], user_message: str) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [{"role": "system", "content": _system_prompt()}]
    # Keep a bounded history. The database already limits this, but defensive
    # trimming makes the outgoing request predictable if another caller uses it.
    for item in history[-12:]:
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content", "")).strip()
        if content:
            messages.append({"role": role, "content": content[:2500]})
    messages.append({"role": "user", "content": user_message[:4000]})
    return messages


def _answer_from_payload(payload: Dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelProviderError("The provider returned an unexpected response.") from exc
    if isinstance(content, list):
        # Some compatible APIs return structured message content.
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    answer = str(content or "").strip()
    if not answer:
        raise ModelProviderError("The provider returned an empty answer.")
    return answer[:12000]


async def _ask_model(user_message: str, history: List[Dict[str, Any]]) -> str:
    settings = get_settings()
    if not settings.llm_enabled:
        raise ModelProviderError("No model key is configured.")

    payload = {
        "model": settings.llm_model,
        "messages": _provider_messages(history, user_message),
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Nani-Chatbot/2.0",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions", json=payload, headers=headers
            )
        if response.is_error:
            # Do not surface upstream body; it can contain account details or
            # provider-specific diagnostics. The server log only has the code.
            logger.warning("Nani model request failed with HTTP %s", response.status_code)
            raise ModelProviderError("The model provider is temporarily unavailable.")
        return _answer_from_payload(response.json())
    except httpx.HTTPError as exc:
        logger.warning("Nani model request failed: %s", type(exc).__name__)
        raise ModelProviderError("The model provider is temporarily unavailable.") from exc
    except ValueError as exc:
        logger.warning("Nani model returned invalid JSON")
        raise ModelProviderError("The model provider returned invalid data.") from exc


async def answer_message(user_message: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Answer with the configured model, falling back gracefully when needed."""
    started = time.perf_counter()
    intent, confidence = detect_intent(user_message)
    sentiment = get_sentiment(user_message)
    settings = get_settings()

    if settings.llm_enabled:
        try:
            response = await _ask_model(user_message, history)
            provider = "llm"
        except ModelProviderError:
            # A chat UI should remain usable during provider failures. The local
            # answer explains how to restore broad-answer capability without
            # pretending that an answer came from the model.
            local_result = generate_response(user_message, history)
            response = local_result["response"]
            provider = "local_fallback"
    else:
        local_result = generate_response(user_message, history)
        response = local_result["response"]
        provider = "local"

    return {
        "response": response,
        "intent": intent,
        "confidence": confidence,
        "sentiment": sentiment,
        "provider": provider,
        "response_time_ms": int((time.perf_counter() - started) * 1000),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
