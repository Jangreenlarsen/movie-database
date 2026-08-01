from fastapi import APIRouter

from app.core.version_info import VERSION_INFO
from app.db import get_database

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health() -> dict:
    mongo_ok = True
    try:
        await get_database().command("ping")
    except Exception:
        mongo_ok = False

    return {"status": "ok", "mongo": mongo_ok, **VERSION_INFO}
