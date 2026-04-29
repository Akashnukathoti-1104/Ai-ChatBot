"""
Tests for NexusAI Chatbot API
Run: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Use temp DB for tests
os.environ["DB_PATH"] = "/tmp/test_chatbot.db"

from app.main import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_homepage():
    res = client.get("/")
    assert res.status_code == 200

def test_chat_basic():
    res = client.post("/api/chat", json={"message": "Hello!"})
    assert res.status_code == 200
    data = res.json()
    assert "response" in data
    assert "session_id" in data
    assert "intent" in data
    assert data["intent"] == "greeting"

def test_chat_pricing():
    res = client.post("/api/chat", json={"message": "What are your pricing plans?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "pricing"

def test_chat_session_persistence():
    # First message
    res1 = client.post("/api/chat", json={"message": "Hello"})
    session_id = res1.json()["session_id"]
    # Second message with same session
    res2 = client.post("/api/chat", json={"message": "Thanks", "session_id": session_id})
    assert res2.json()["session_id"] == session_id
    assert res2.json()["intent"] == "thanks"

def test_chat_empty_message():
    res = client.post("/api/chat", json={"message": ""})
    assert res.status_code == 400

def test_chat_too_long():
    res = client.post("/api/chat", json={"message": "x" * 2001})
    assert res.status_code == 400

def test_stats():
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_messages" in data
    assert "total_sessions" in data

def test_logs():
    res = client.get("/api/logs")
    assert res.status_code == 200
    assert "logs" in res.json()

def test_feedback():
    # Get a message ID first
    chat_res = client.post("/api/chat", json={"message": "Hello"})
    msg_id = chat_res.json()["message_id"]
    # Send feedback
    res = client.post("/api/feedback", json={"message_id": msg_id, "rating": 1})
    assert res.status_code == 200

def test_nlp_intents():
    from app.nlp_engine import detect_intent
    assert detect_intent("hello there")[0] == "greeting"
    assert detect_intent("bye bye")[0] == "farewell"
    assert detect_intent("how much does it cost?")[0] == "pricing"
    assert detect_intent("I have a bug in my code")[0] == "technical"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
