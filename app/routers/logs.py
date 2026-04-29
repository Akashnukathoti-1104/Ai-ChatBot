from fastapi import APIRouter
from app.database import get_stats, get_recent_logs

router = APIRouter()

@router.get("/logs")
async def logs(limit: int = 50):
    return {"logs": get_recent_logs(limit)}

@router.get("/stats")
async def stats():
    return get_stats()
