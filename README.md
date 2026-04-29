# 🤖 NexusAI — Intelligent AI Chatbot

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![NLTK](https://img.shields.io/badge/NLTK-3.8-yellow)](https://nltk.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

A production-grade AI chatbot with **Natural Language Processing**, **intent detection**, **sentiment analysis**, **conversation memory**, and a **real-time analytics dashboard**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🧠 NLP Engine | NLTK-powered intent detection with lemmatization |
| 💬 Context Memory | Session-based conversation history |
| 😊 Sentiment Analysis | Detects user mood, empathetic responses |
| 📊 Admin Dashboard | Real-time analytics, interaction logs, charts |
| 👍 Feedback System | Per-message thumbs up/down with DB logging |
| ⚡ Fast API | FastAPI async backend — sub-50ms responses |
| 💾 SQLite Logging | All conversations logged with metadata |
| 🎨 Beautiful UI | Dark-themed, animated chat interface |

---

## 🚀 Quick Start (Local)

### 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/ai-chatbot.git
cd ai-chatbot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-light.txt
```

### 2. Run

```bash
python main.py
```

Open → **http://localhost:8000**  
Admin → **http://localhost:8000/admin**  
API Docs → **http://localhost:8000/docs**

---

## 📁 Project Structure

```
ai-chatbot/
├── app/
│   ├── main.py          # FastAPI app, routes, startup
│   ├── nlp_engine.py    # NLP: intent detection, sentiment, responses
│   ├── database.py      # SQLite: init, save, query helpers
│   └── routers/
│       ├── chat.py      # POST /api/chat, POST /api/feedback
│       └── logs.py      # GET /api/logs, GET /api/stats
├── templates/
│   ├── index.html       # Chat UI
│   └── admin.html       # Analytics dashboard
├── tests/
│   └── test_api.py      # Pytest test suite
├── data/                # SQLite DB (auto-created, gitignored)
├── main.py              # Entry point
├── requirements.txt     # Full deps (with PyTorch)
├── requirements-light.txt  # Lightweight (recommended for Render free)
├── render.yaml          # Render deployment config
├── Procfile             # Heroku/Render process file
└── README.md
```

---

## 🌐 API Reference

### `POST /api/chat`
```json
{
  "message": "What are your pricing plans?",
  "session_id": "optional-uuid"
}
```
**Response:**
```json
{
  "session_id": "abc-123",
  "message_id": 42,
  "response": "💰 Our pricing plans...",
  "intent": "pricing",
  "confidence": 0.96,
  "sentiment": "neutral",
  "response_time_ms": 12,
  "timestamp": "2025-01-01T12:00:00"
}
```

### `GET /api/stats` — Dashboard statistics  
### `GET /api/logs?limit=50` — Recent interaction logs  
### `POST /api/feedback` — `{ "message_id": 42, "rating": 1 }` (1 or -1)

Full docs at **`/docs`** (Swagger UI).

---

## 🎯 Supported Intents

| Intent | Example Triggers |
|---|---|
| `greeting` | "Hello", "Hi", "Hey there" |
| `farewell` | "Bye", "Goodbye", "See you" |
| `thanks` | "Thank you", "Thanks a lot" |
| `pricing` | "How much?", "Pricing plans", "Cost" |
| `features` | "What can you do?", "Features", "Capabilities" |
| `technical` | "Bug", "Error", "Not working", "Fix" |
| `about` | "Who are you?", "Tell me about yourself" |
| `human` | "Speak to a person", "Live agent" |
| `hours` | "Working hours", "When are you open?" |
| `refund` | "Refund", "Cancel subscription" |
| `default` | Fallback for unrecognized inputs |

---

## ☁️ Deploy to Render (Free)

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "🚀 Initial commit — NexusAI Chatbot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ai-chatbot.git
git push -u origin main
```

### Step 2 — Create Render Web Service

1. Go to [render.com](https://render.com) → **New +** → **Web Service**
2. Connect your GitHub repo
3. Configure:
   - **Name**: `nexusai-chatbot`
   - **Runtime**: `Python 3`
   - **Build Command**: 
     ```
     pip install -r requirements-light.txt && python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords'); nltk.download('wordnet')"
     ```
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free
4. Add Environment Variable:
   - `DB_PATH` = `/tmp/data/chatbot.db`
5. Click **Deploy** 🚀

### Step 3 — Access Your App

Your app will be live at:  
`https://nexusai-chatbot.onrender.com`

> **Note**: Free Render services spin down after inactivity. First request after sleep takes ~30s. Upgrade to Starter ($7/mo) for always-on.

---

## 🧪 Running Tests

```bash
pip install pytest httpx
pytest tests/ -v
```

---

## 🛠 Extending the Bot

### Add a new intent (in `app/nlp_engine.py`):

```python
"shipping": {
    "patterns": ["shipping", "delivery", "ship", "how long", "arrive"],
    "responses": [
        "📦 Standard shipping takes 3-5 business days. Express is 1-2 days!"
    ]
}
```

### Connect to OpenAI (optional upgrade):

Replace `generate_response()` in `nlp_engine.py` with OpenAI API call for more dynamic responses using your API key via environment variable.

---

## 📄 License

MIT — free to use, modify, and deploy.

---

**Made with 🤖 NexusAI**
