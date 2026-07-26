"""API tests for Nani. Run with: pytest -q"""
from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from pathlib import Path

# Configure before importing the application because configuration is loaded once
# for each process.
TEST_DB = "/tmp/nani_test_chatbot.db"
Path(TEST_DB).unlink(missing_ok=True)
os.environ.update(
    {
        "DB_PATH": TEST_DB,
        "ADMIN_TOKEN": "test-admin-token",
        "BOT_NAME": "Nani",
        "BOT_OWNER_NAME": "Test Owner",
        "BOT_OWNER_BIO": "A test profile.",
        "SUPPORT_EMAIL": "owner@example.test",
        "RATE_LIMIT_REQUESTS": "100",
    }
)
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}


def test_health_reports_nani_status():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "Nani"
    assert response.json()["ai_mode"] == "local"


def test_homepage_and_dashboard_render():
    assert client.get("/").status_code == 200
    assert "Nani" in client.get("/").text
    assert client.get("/admin").status_code == 200


def test_public_config_contains_only_safe_profile_data():
    data = client.get("/api/config").json()
    assert data["bot_name"] == "Nani"
    assert data["owner_name"] == "Test Owner"
    assert data["support_email"] == "owner@example.test"
    assert "admin_token" not in data
    assert "llm_api_key" not in data


def test_chat_basic_creates_a_uuid_session():
    response = client.post("/api/chat", json={"message": "Hello!"})
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]
    assert data["message_id"] > 0
    assert data["intent"] == "greeting"
    assert data["provider"] == "local"
    assert "Nani" in data["response"]


def test_chat_supports_session_history():
    first = client.post("/api/chat", json={"message": "Hello"}).json()
    second = client.post(
        "/api/chat", json={"message": "What did I just say?", "session_id": first["session_id"]}
    )
    assert second.status_code == 200
    assert second.json()["session_id"] == first["session_id"]
    assert "Hello" in second.json()["response"]

    history = client.get(f"/api/history/{first['session_id']}")
    assert history.status_code == 200
    assert len(history.json()["messages"]) == 4


def test_local_calculator_answer():
    response = client.post("/api/chat", json={"message": "Calculate 125 * 18"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "calculation"
    assert "2250" in data["response"]


def test_chat_validation():
    assert client.post("/api/chat", json={"message": ""}).status_code == 400
    assert client.post("/api/chat", json={"message": "x" * 4001}).status_code == 400
    assert client.post("/api/chat", json={"message": "Hello", "session_id": "not-a-uuid"}).status_code == 400
    assert client.get("/api/history/not-a-uuid").status_code == 400


def test_dashboard_api_requires_token_then_allows_admin():
    assert client.get("/api/stats").status_code == 401
    assert client.get("/api/logs").status_code == 401

    stats = client.get("/api/stats", headers=ADMIN_HEADERS)
    assert stats.status_code == 200
    assert "total_messages" in stats.json()
    assert "feedback_total" in stats.json()

    logs = client.get("/api/logs?limit=500", headers=ADMIN_HEADERS)
    assert logs.status_code == 200
    assert "logs" in logs.json()
    assert len(logs.json()["logs"]) <= 100


def test_feedback_targets_an_assistant_message_only():
    chat = client.post("/api/chat", json={"message": "Thanks"}).json()
    successful = client.post("/api/feedback", json={"message_id": chat["message_id"], "rating": 1})
    assert successful.status_code == 200
    assert client.post("/api/feedback", json={"message_id": chat["message_id"], "rating": 0}).status_code == 400
    assert client.post("/api/feedback", json={"message_id": 999999, "rating": 1}).status_code == 404


def test_connected_model_uses_openai_compatible_chat_endpoint(monkeypatch):
    """The production provider path is tested without sending a real network call."""
    import httpx
    from app import ai_service
    from app.config import get_settings

    configured = replace(
        get_settings(),
        llm_api_key="not-a-real-key",
        llm_base_url="https://provider.example/v1",
        llm_model="test-model",
    )
    monkeypatch.setattr(ai_service, "get_settings", lambda: configured)

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, json, headers):
            assert url == "https://provider.example/v1/chat/completions"
            assert json["model"] == "test-model"
            assert json["messages"][-1]["content"] == "Answer this question"
            assert headers["Authorization"] == "Bearer not-a-real-key"
            return httpx.Response(200, json={"choices": [{"message": {"content": "A model answer"}}]})

    monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda **_: FakeClient())
    result = asyncio.run(ai_service.answer_message("Answer this question", []))
    assert result["provider"] == "llm"
    assert result["response"] == "A model answer"


def test_local_intent_engine_is_precise():
    from app.nlp_engine import detect_intent

    assert detect_intent("hello there")[0] == "greeting"
    assert detect_intent("bye bye")[0] == "farewell"
    assert detect_intent("who created you?")[0] == "owner_details"
    # "this" must not be detected as a greeting because it contains "hi".
    assert detect_intent("Can you explain this concept?")[0] == "question"
