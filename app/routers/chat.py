from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

from app.nlp_engine import generate_response
from app.database import save_message, get_conversation_history

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class FeedbackRequest(BaseModel):
    message_id: int
    rating: int  # 1 or -1

@router.post("/chat")
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    if len(request.message) > 2000:
        raise HTTPException(status_code=400, detail="Message too long (max 2000 chars)")

    # Generate or use existing session
    session_id = request.session_id or str(uuid.uuid4())
    
    # Fetch conversation history for context
    history = get_conversation_history(session_id, limit=6)
    
    # Save user message
    save_message(session_id=session_id, role="user", content=request.message)
    
    # Generate AI response
    result = generate_response(request.message, history)
    
    # Save assistant response
    msg_id = save_message(
        session_id=session_id,
        role="assistant",
        content=result["response"],
        intent=result["intent"],
        confidence=result["confidence"],
        response_time_ms=result["response_time_ms"]
    )
    
    return {
        "session_id": session_id,
        "message_id": msg_id,
        "response": result["response"],
        "intent": result["intent"],
        "confidence": result["confidence"],
        "sentiment": result["sentiment"],
        "response_time_ms": result["response_time_ms"],
        "timestamp": result["timestamp"]
    }

@router.post("/feedback")
async def feedback(request: FeedbackRequest):
    if request.rating not in [1, -1]:
        raise HTTPException(status_code=400, detail="Rating must be 1 or -1")
    from app.database import get_db
    conn = get_db()
    conn.execute(
        "INSERT INTO feedback (message_id, rating) VALUES (?, ?)",
        (request.message_id, request.rating)
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Feedback recorded. Thank you!"}

@router.get("/history/{session_id}")
async def get_history(session_id: str):
    history = get_conversation_history(session_id, limit=50)
    return {"session_id": session_id, "messages": history}
