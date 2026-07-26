"""FastAPI application for Nani."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import init_db
from app.routers import chat, logs

BASE_DIR = Path(__file__).resolve().parent.parent
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=f"{settings.bot_name} API",
    description="A configurable AI assistant with chat memory, optional LLM answers, feedback, and private analytics.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=settings.cors_allows_credentials,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(logs.router, prefix="/api", tags=["analytics"])


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin(request: Request):
    return templates.TemplateResponse(request, "admin.html")


@app.get("/api/config", tags=["chat"])
async def public_config():
    """Return UI-safe personalization only; secrets are never exposed."""
    return settings.public_profile


@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "healthy",
        "service": settings.bot_name,
        "version": app.version,
        "ai_mode": "connected" if settings.llm_enabled else "local",
    }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
