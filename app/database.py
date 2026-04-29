import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "data/chatbot.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
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
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER REFERENCES messages(id),
            rating INTEGER CHECK(rating IN (1, -1)),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

def save_message(session_id: str, role: str, content: str, 
                  intent: str = None, confidence: float = None, 
                  response_time_ms: int = None) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO messages (session_id, role, content, intent, confidence, response_time_ms)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, role, content, intent, confidence, response_time_ms))
    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
    return msg_id

def get_conversation_history(session_id: str, limit: int = 10) -> list:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM messages 
        WHERE session_id = ? 
        ORDER BY timestamp DESC LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def get_stats() -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM messages WHERE role='user'")
    total_msgs = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(DISTINCT session_id) as total FROM messages")
    total_sessions = cursor.fetchone()["total"]
    cursor.execute("SELECT AVG(response_time_ms) as avg FROM messages WHERE role='assistant' AND response_time_ms IS NOT NULL")
    avg_time = cursor.fetchone()["avg"] or 0
    cursor.execute("""
        SELECT intent, COUNT(*) as count FROM messages 
        WHERE role='assistant' AND intent IS NOT NULL 
        GROUP BY intent ORDER BY count DESC LIMIT 5
    """)
    top_intents = [{"intent": r["intent"], "count": r["count"]} for r in cursor.fetchall()]
    cursor.execute("""
        SELECT DATE(timestamp) as date, COUNT(*) as count 
        FROM messages WHERE role='user' 
        GROUP BY DATE(timestamp) ORDER BY date DESC LIMIT 7
    """)
    daily = [{"date": r["date"], "count": r["count"]} for r in cursor.fetchall()]
    conn.close()
    return {
        "total_messages": total_msgs,
        "total_sessions": total_sessions,
        "avg_response_time_ms": round(avg_time, 1),
        "top_intents": top_intents,
        "daily_messages": daily
    }

def get_recent_logs(limit: int = 50) -> list:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, session_id, role, content, intent, confidence, 
               response_time_ms, timestamp 
        FROM messages ORDER BY timestamp DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
