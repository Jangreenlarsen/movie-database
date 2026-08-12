from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_optional_user, require_not_guest
from app.db import get_database
from app.models.analytics import VisitCreate, VisitStats
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.post("/visit", status_code=204)
async def record_visit(
    payload: VisitCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user: dict | None = Depends(get_optional_user),
) -> None:
    """Feature #125 — offentligt (ingen auth): /bio-siden skal kunne poste
    uden login. Brugernavnet kommer fra `get_optional_user` (serverens egen
    cookie-opslag), aldrig fra payloaden."""
    await analytics_service.record_visit(db, payload, user.get("username") if user else None)


@router.get(
    "/summary",
    response_model=VisitStats,
    dependencies=[Depends(require_not_guest)],
)
async def visit_summary(db: AsyncIOMotorDatabase = Depends(get_database)) -> VisitStats:
    return await analytics_service.get_visit_stats(db)
