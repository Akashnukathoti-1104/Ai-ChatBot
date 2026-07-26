"""Nani's fast local conversation layer.

A connected language model supplies broad, open-ended answers. This module stays
available when no provider is configured or a provider is temporarily unavailable:
it handles useful small-talk, owner details, simple arithmetic, and clear fallback
responses without downloading models at startup.
"""
from __future__ import annotations

import ast
import operator
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_settings

# Phrases are deliberately narrow so a word like "hi" in "this" is never
# incorrectly classified as a greeting.
INTENT_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "greeting": ("hello", "hi", "hey", "good morning", "good afternoon", "good evening", "howdy"),
    "farewell": ("bye", "goodbye", "see you", "take care", "farewell", "exit"),
    "thanks": ("thank you", "thanks", "thank", "appreciate it", "thx"),
    "identity": ("who are you", "what are you", "your name", "introduce yourself", "about you"),
    "owner_details": ("who made you", "who created you", "who owns you", "your owner", "about the owner"),
    "contact": ("contact", "email", "phone number", "support", "human agent", "real person", "representative"),
    "hours": ("opening hours", "working hours", "business hours", "when are you open", "availability"),
    "capabilities": ("what can you do", "how can you help", "your features", "your capabilities"),
}

_POSITIVE_WORDS = {"good", "great", "awesome", "love", "excellent", "amazing", "happy", "thanks"}
_NEGATIVE_WORDS = {"bad", "terrible", "awful", "hate", "worst", "angry", "frustrated", "upset", "broken"}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    """Match a phrase at word boundaries (with safe whitespace within phrases)."""
    words = [re.escape(word) for word in phrase.split()]
    return bool(re.search(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", text))


def detect_intent(text: str) -> Tuple[str, float]:
    normalised = _normalise(text)
    best_intent, best_score = "question", 0
    for intent, patterns in INTENT_PATTERNS.items():
        score = sum(1 for phrase in patterns if _contains_phrase(normalised, phrase))
        if score > best_score:
            best_intent, best_score = intent, score
    if not best_score:
        if _looks_like_math(normalised):
            return "calculation", 0.94
        if re.search(r"\b(date|time|day is it)\b", normalised):
            return "time", 0.82
        return "question", 0.45
    confidence = min(0.99, 0.74 + (best_score - 1) * 0.1)
    return best_intent, round(confidence, 2)


def get_sentiment(text: str) -> str:
    words = set(re.findall(r"[a-z']+", text.lower()))
    positive = len(words & _POSITIVE_WORDS)
    negative = len(words & _NEGATIVE_WORDS)
    if negative > positive:
        return "negative"
    if positive > negative:
        return "positive"
    return "neutral"


def _looks_like_math(text: str) -> bool:
    if re.search(r"\b(calculate|solve|what is|compute)\b", text) and re.search(r"\d", text):
        return True
    return bool(re.fullmatch(r"[\d\s().+\-*/%^]+", text)) and bool(re.search(r"\d", text))


_ALLOWED_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _extract_expression(text: str) -> str:
    match = re.search(r"(?:calculate|solve|compute|what is)\s+(.+?)(?:\?|$)", text, flags=re.I)
    return match.group(1).strip() if match else text.strip()


def _safe_calculate(expression: str) -> Optional[float]:
    """Evaluate only basic arithmetic AST nodes; never execute Python code."""
    expression = expression.replace("^", "**").replace(",", "")
    if len(expression) > 100 or not re.fullmatch(r"[\d\s().+\-*/%*]+", expression):
        return None
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError):
        return None

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPERATORS:
            return _ALLOWED_UNARY_OPERATORS[type(node.op)](evaluate(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINARY_OPERATORS:
            left, right = evaluate(node.left), evaluate(node.right)
            if type(node.op) is ast.Pow and (abs(right) > 10 or abs(left) > 1_000_000):
                raise ValueError("expression is too large")
            return _ALLOWED_BINARY_OPERATORS[type(node.op)](left, right)
        raise ValueError("unsupported expression")

    try:
        result = evaluate(tree)
        if not (-1e15 < result < 1e15):
            return None
        return result
    except (ArithmeticError, ValueError, OverflowError):
        return None


def _configured_contact() -> str:
    settings = get_settings()
    entries = []
    if settings.support_email:
        entries.append(f"email {settings.support_email}")
    if settings.support_phone:
        entries.append(f"phone {settings.support_phone}")
    if settings.business_hours:
        entries.append(f"hours: {settings.business_hours}")
    return "; ".join(entries)


def _last_user_message(history: List[Dict[str, Any]]) -> Optional[str]:
    for item in reversed(history):
        if item.get("role") == "user" and item.get("content"):
            return str(item["content"])
    return None


def build_local_response(intent: str, user_message: str, history: List[Dict[str, Any]]) -> str:
    """Create a useful response when a cloud LLM is not available."""
    settings = get_settings()
    name = settings.bot_name
    contact = _configured_contact()
    normalised = _normalise(user_message)

    if intent == "greeting":
        return f"Hello! I’m {name}, {settings.bot_tagline.lower()}. What would you like to explore?"
    if intent == "farewell":
        return f"Take care! I’m {name} and I’ll be here whenever you need a hand."
    if intent == "thanks":
        return "You’re very welcome. What else can I help with?"
    if intent == "identity":
        owner = f" I was set up for {settings.bot_owner_name}." if settings.bot_owner_name else ""
        return f"I’m {name}, {settings.bot_tagline.lower()}.{owner} I can chat, explain ideas, and help you work through questions."
    if intent == "owner_details":
        if settings.bot_owner_name:
            bio = f" {settings.bot_owner_bio}" if settings.bot_owner_bio else ""
            return f"{name} was created for {settings.bot_owner_name}.{bio}"
        return f"My owner details have not been configured yet. Add BOT_OWNER_NAME and BOT_OWNER_BIO in the deployment settings to personalize this answer."
    if intent == "contact":
        if contact:
            return f"You can reach the team via {contact}. I can also help here right now."
        return "No support contact details have been configured yet. Add SUPPORT_EMAIL, SUPPORT_PHONE, or BUSINESS_HOURS in the environment settings."
    if intent == "hours":
        if settings.business_hours:
            return f"{name} is available here 24/7. Human support hours: {settings.business_hours}."
        return f"I’m available here 24/7. Human-support hours have not been configured yet."
    if intent == "capabilities":
        if settings.llm_enabled:
            return f"I’m {name}. I can answer open-ended questions, explain concepts, brainstorm, draft text, summarize information you share, and remember the recent chat context."
        return (
            f"I’m {name}. I can handle conversation, configured contact details, dates, and basic arithmetic. "
            "For broad, open-ended answers, add LLM_API_KEY (or OPENAI_API_KEY) in Render and redeploy."
        )
    if intent == "calculation":
        expression = _extract_expression(user_message)
        result = _safe_calculate(expression)
        if result is not None:
            display = str(int(result)) if result.is_integer() else f"{result:.10g}"
            return f"{expression} = **{display}**"
        return "I can calculate basic arithmetic such as `25 * (8 + 2)`. Please try a simpler expression."
    if intent == "time":
        now = datetime.now(timezone.utc)
        if "time" in normalised:
            return f"The current UTC time is {now.strftime('%H:%M')} on {now.strftime('%A, %B %-d, %Y')}."
        return f"Today is {now.strftime('%A, %B %-d, %Y')} (UTC)."

    if re.search(r"\b(what did i (just )?say|repeat my message)\b", normalised):
        previous = _last_user_message(history)
        if previous:
            return f"Your previous message was: “{previous}”"
        return "This is the first message I can see in this chat."

    return (
        f"I’m {name}. To answer open-ended questions accurately, connect an OpenAI-compatible model by setting "
        "LLM_API_KEY in Render. Once it is connected, I can give detailed answers to general questions as well."
    )


def generate_response(user_message: str, session_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Synchronous local response API retained for integrations and tests."""
    started = time.perf_counter()
    intent, confidence = detect_intent(user_message)
    sentiment = get_sentiment(user_message)
    response = build_local_response(intent, user_message, session_history)
    return {
        "response": response,
        "intent": intent,
        "confidence": confidence,
        "sentiment": sentiment,
        "provider": "local",
        "response_time_ms": int((time.perf_counter() - started) * 1000),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
