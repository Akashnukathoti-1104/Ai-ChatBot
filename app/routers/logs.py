from __future__ import annotations

from fastapi import APIRouter, Request

from app.database import get_recent_logs, get_stats
from app.security import require_admin

router = APIRouter()


@router.get("/logs")
async def logs(request: Request, limit: int = 50):
    require_admin(request)
    return {"logs": get_recent_logs(limit)}


@router.get("/stats")
async def stats(request: Request):
    require_admin(request)
    return get_stats()
