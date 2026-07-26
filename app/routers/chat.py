from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.ai_service import answer_message
from app.database import get_conversation_history, record_feedback, save_message
from app.security import enforce_chat_rate_limit

router = APIRouter()

MAX_MESSAGE_LENGTH = 4000


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    message_id: int
    rating: int  # 1 or -1


def _valid_session_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid session ID.")


@router.post("/chat")
async def chat(request: Request, payload: ChatRequest):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400, detail=f"Message too long (maximum {MAX_MESSAGE_LENGTH} characters)."
        )

    enforce_chat_rate_limit(request)
    session_id = _valid_session_id(payload.session_id) or str(uuid.uuid4())
    history = get_conversation_history(session_id, limit=12)

    # Save before answering so an interrupted request still keeps the user's
    # message. The model receives the preceding history, not a duplicate.
    save_message(session_id=session_id, role="user", content=message)
    result = await answer_message(message, history)
    message_id = save_message(
        session_id=session_id,
        role="assistant",
        content=result["response"],
        intent=result["intent"],
        confidence=result["confidence"],
        response_time_ms=result["response_time_ms"],
        provider=result["provider"],
    )

    return {"session_id": session_id, "message_id": message_id, **result}


@router.post("/feedback")
async def feedback(payload: FeedbackRequest):
    if payload.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="Rating must be 1 or -1.")
    if not record_feedback(payload.message_id, payload.rating):
        raise HTTPException(status_code=404, detail="Assistant message not found.")
    return {"status": "ok", "message": "Feedback recorded. Thank you!"}


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    valid_session = _valid_session_id(session_id)
    # UUID session IDs are intentionally unguessable. This endpoint returns no
    # global messages and lets the browser restore its own conversation.
    return {"session_id": valid_session, "messages": get_conversation_history(valid_session, limit=50)}
