"""Small, dependable SQLite persistence layer for Nani."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import get_settings

_initialized_paths: set[str] = set()
_init_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    intent TEXT,
    confidence REAL,
    response_time_ms INTEGER,
    provider TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id),
    rating INTEGER NOT NULL CHECK(rating IN (1, -1)),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id, id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_feedback_message ON feedback(message_id);
"""


def _db_path() -> str:
    return get_settings().database_path


def _prepare_parent(path: str) -> None:
    if path == ":memory:":
        return
    parent = Path(path).expanduser().parent
    # pathlib returns '.' for a bare filename, which is already available.
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)


def _connect(path: Optional[str] = None) -> sqlite3.Connection:
    db_path = path or _db_path()
    _prepare_parent(db_path)
    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    # WAL is safe for file-backed SQLite and makes dashboard reads less likely
    # to block a concurrent chat write. It is not supported for :memory:.
    if db_path != ":memory:":
        connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _ensure_initialized() -> None:
    path = _db_path()
    if path in _initialized_paths:
        return
    with _init_lock:
        if path in _initialized_paths:
            return
        connection = _connect(path)
        try:
            connection.executescript(_SCHEMA)
            # Migration for databases created by the original NexusAI app.
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(messages)")}
            if "provider" not in columns:
                connection.execute("ALTER TABLE messages ADD COLUMN provider TEXT")
            connection.commit()
            _initialized_paths.add(path)
        finally:
            connection.close()


def init_db() -> None:
    """Create tables and perform lightweight schema upgrades."""
    _ensure_initialized()


def get_db() -> sqlite3.Connection:
    _ensure_initialized()
    return _connect()


def save_message(
    session_id: str,
    role: str,
    content: str,
    intent: Optional[str] = None,
    confidence: Optional[float] = None,
    response_time_ms: Optional[int] = None,
    provider: Optional[str] = None,
) -> int:
    """Store a message and return its durable ID."""
    connection = get_db()
    try:
        with connection:
            connection.execute(
                "INSERT OR IGNORE INTO conversations (session_id) VALUES (?)", (session_id,)
            )
            cursor = connection.execute(
                """
                INSERT INTO messages
                    (session_id, role, content, intent, confidence, response_time_ms, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, role, content, intent, confidence, response_time_ms, provider),
            )
        return int(cursor.lastrowid)
    finally:
        connection.close()


def get_conversation_history(session_id: str, limit: int = 12) -> List[Dict[str, Any]]:
    """Return the most recent messages in chronological order."""
    safe_limit = max(1, min(int(limit), 100))
    connection = get_db()
    try:
        rows = connection.execute(
            """
            SELECT id, role, content, intent, timestamp
            FROM messages WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (session_id, safe_limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        connection.close()


def record_feedback(message_id: int, rating: int) -> bool:
    """Record feedback only for an existing assistant message.

    Returns False when the message does not exist or belongs to a user.
    """
    connection = get_db()
    try:
        with connection:
            message = connection.execute(
                "SELECT id FROM messages WHERE id = ? AND role = 'assistant'", (message_id,)
            ).fetchone()
            if message is None:
                return False
            connection.execute(
                "INSERT INTO feedback (message_id, rating) VALUES (?, ?)",
                (message_id, rating),
            )
        return True
    finally:
        connection.close()


def get_stats() -> Dict[str, Any]:
    connection = get_db()
    try:
        total_messages = connection.execute(
            "SELECT COUNT(*) AS total FROM messages WHERE role = 'user'"
        ).fetchone()["total"]
        total_sessions = connection.execute(
            "SELECT COUNT(*) AS total FROM conversations"
        ).fetchone()["total"]
        avg_time = connection.execute(
            """
            SELECT AVG(response_time_ms) AS avg FROM messages
            WHERE role = 'assistant' AND response_time_ms IS NOT NULL
            """
        ).fetchone()["avg"] or 0
        top_intents = [
            {"intent": row["intent"], "count": row["count"]}
            for row in connection.execute(
                """
                SELECT intent, COUNT(*) AS count FROM messages
                WHERE role = 'assistant' AND intent IS NOT NULL
                GROUP BY intent ORDER BY count DESC, intent ASC LIMIT 6
                """
            ).fetchall()
        ]
        daily_messages = [
            {"date": row["date"], "count": row["count"]}
            for row in connection.execute(
                """
                SELECT DATE(timestamp) AS date, COUNT(*) AS count
                FROM messages WHERE role = 'user'
                GROUP BY DATE(timestamp) ORDER BY date DESC LIMIT 7
                """
            ).fetchall()
        ]
        feedback = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END), 0) AS positive
            FROM feedback
            """
        ).fetchone()
        return {
            "total_messages": total_messages,
            "total_sessions": total_sessions,
            "avg_response_time_ms": round(float(avg_time), 1),
            "top_intents": top_intents,
            "daily_messages": daily_messages,
            "feedback_total": feedback["total"],
            "feedback_positive": feedback["positive"],
        }
    finally:
        connection.close()


def get_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 100))
    connection = get_db()
    try:
        rows = connection.execute(
            """
            SELECT id, session_id, role, content, intent, confidence,
                   response_time_ms, provider, timestamp
            FROM messages ORDER BY id DESC LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()
