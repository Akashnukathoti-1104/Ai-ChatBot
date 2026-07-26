# ✦ Nani — Personal AI Assistant

Nani is a polished, deployable FastAPI chat assistant with recent-chat memory, optional **OpenAI-compatible AI answers**, feedback, rate limiting, an owner-configurable profile, and a protected analytics dashboard.

> **Important:** no chatbot can honestly guarantee a correct answer to every possible question. Nani gives broad, high-quality answers when an AI provider key is configured. Without a key, it still runs safely with local conversation, identity/contact details, time/date, and basic-calculator responses.

## What’s included

- **Nani identity** — bot name, your name/bio, business and support details are all configurable without editing code.
- **Open-ended answers** — connects to the OpenAI Chat Completions API or another OpenAI-compatible endpoint through environment variables.
- **Graceful fallback** — the UI remains usable if no key is set or the AI provider is unavailable; it never pretends a fallback answer came from the model.
- **Conversation memory** — the latest messages in a browser session are sent as context and can be restored after refresh.
- **Safe, responsive chat UI** — mobile layout, dark mode, copy, speech playback, export, feedback, typing state, and XSS-safe message rendering.
- **Private analytics** — `/admin`, `/api/logs`, and `/api/stats` require `ADMIN_TOKEN`.
- **Deployment basics** — a health check, Render Blueprint, SQLite migrations, defensive input validation, configurable CORS, and in-memory per-IP rate limiting.

## Quick start

### 1. Create an environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Add your details and secrets

Copy the example file and edit the values that identify you or your business:

```bash
cp .env.example .env
```

This app intentionally does **not** load `.env` automatically. For local development, export the values before starting (or configure them in your IDE):

```bash
export BOT_OWNER_NAME="Your Name"
export BOT_OWNER_BIO="A short description of you or your business."
export SUPPORT_EMAIL="you@example.com"
export ADMIN_TOKEN="use-a-long-random-secret"
export LLM_API_KEY="your-provider-key"       # enables broad AI answers
# Optional if using a provider other than the OpenAI API:
# export LLM_BASE_URL="https://your-provider.example/v1"
# export LLM_MODEL="your-model-name"
```

`LLM_API_KEY` and `OPENAI_API_KEY` are both recognized. The default API endpoint is `https://api.openai.com/v1`, with `gpt-4o-mini` as the default model. You can point `LLM_BASE_URL` and `LLM_MODEL` to any provider that implements the OpenAI **Chat Completions** format.

### 3. Start Nani

```bash
python main.py
```

Open these URLs:

- Chat: [http://localhost:8000](http://localhost:8000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)
- Dashboard: [http://localhost:8000/admin](http://localhost:8000/admin) — enter your `ADMIN_TOKEN`

## Personalization reference

Add these as environment variables in Render; do not hard-code private details in the repository.

| Variable | Purpose |
|---|---|
| `BOT_NAME` | Display name, defaults to `Nani` |
| `BOT_TAGLINE` | Short assistant description |
| `BOT_OWNER_NAME` | Your name, used when users ask who owns/created Nani |
| `BOT_OWNER_BIO` | Your short bio or business description |
| `BUSINESS_NAME` | Optional business name supplied to the AI context |
| `SUPPORT_EMAIL` / `SUPPORT_PHONE` | Details Nani can share when someone requests contact support |
| `BUSINESS_HOURS` | Human-support availability |
| `ADMIN_TOKEN` | **Required** to unlock the dashboard analytics APIs |
| `ALLOWED_ORIGINS` | Comma-separated allowed browser origins; `*` is fine for the standalone chat site |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | Per-IP chat rate-limit settings, default `30` requests per `60` seconds |

## Deploy on Render

The repository includes a ready-to-use `render.yaml` Blueprint.

1. Push this branch/repository to GitHub.
2. In Render, choose **New → Blueprint** and select the repository. Render reads `render.yaml`.
3. Create the service. The Blueprint:
   - installs only lightweight Python dependencies;
   - runs `uvicorn app.main:app --host 0.0.0.0 --port $PORT`;
   - checks `/health`;
   - generates a secret `ADMIN_TOKEN` automatically;
   - uses a Render-safe Python 3.11 runtime.
4. In the service’s **Environment** page, add your real details:

   ```text
   BOT_OWNER_NAME=Your Name
   BOT_OWNER_BIO=Your short bio or business description
   SUPPORT_EMAIL=you@example.com
   BUSINESS_HOURS=Monday–Friday, 9 AM–5 PM
   LLM_API_KEY=your-secret-provider-key
   LLM_MODEL=gpt-4o-mini
   ```

5. Save the environment changes and deploy. Never put an LLM API key or admin token in source control.
6. To access the dashboard, open `https://YOUR-SERVICE.onrender.com/admin`, then copy `ADMIN_TOKEN` from Render’s Environment page into the dashboard prompt.

### Persistence note

The free Render service filesystem is ephemeral. The supplied configuration writes SQLite analytics to `/tmp/data/nani.db`, so chat logs can disappear after a restart or redeploy. Nani still works normally. For durable conversation logs, attach a Render persistent disk on a paid web service and set `DB_PATH` to a path on that disk, or replace the SQLite layer with a managed database.

### CORS note

For Nani’s included standalone UI, `ALLOWED_ORIGINS=*` is appropriate. If you embed the API in another website, use exact origins instead, for example:

```text
ALLOWED_ORIGINS=https://www.example.com,https://app.example.com
```

## API summary

### `POST /api/chat`

```json
{
  "message": "Explain photosynthesis in simple terms",
  "session_id": "optional UUID from an earlier response"
}
```

Returns the answer, session ID, detected local intent/sentiment, provider mode, response timing, and an assistant-message ID for feedback.

### `POST /api/feedback`

```json
{ "message_id": 42, "rating": 1 }
```

A rating must be `1` or `-1` and can only target an assistant message.

### Other endpoints

| Endpoint | Access |
|---|---|
| `GET /api/config` | Public, only UI-safe profile details |
| `GET /api/history/{session_id}` | Public for a UUID session; returns only that session’s messages |
| `GET /health` | Public deployment health status |
| `GET /api/logs` | Requires `X-Admin-Token` |
| `GET /api/stats` | Requires `X-Admin-Token` |

Interactive schema documentation is available at `/docs`.

## Test

```bash
pytest -q
```

Tests use a temporary SQLite database and a local fallback, so no model key or internet access is required.

## Project layout

```text
app/
  ai_service.py      # OpenAI-compatible provider call + safe fallback
  config.py          # Environment-based settings and public profile
  database.py        # SQLite schema, migration, history, analytics
  nlp_engine.py      # Fast local intents, arithmetic, sentiment
  security.py        # Admin-token and rate-limit protections
  routers/           # Chat, feedback, dashboard API endpoints
templates/
  index.html         # Nani chat interface
  admin.html         # Token-protected dashboard interface
render.yaml          # Render Blueprint
.env.example         # Copyable personalization checklist
```
