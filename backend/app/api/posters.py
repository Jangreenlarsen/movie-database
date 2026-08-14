from fastapi import APIRouter, Depends, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_database
from app.services import poster_cache_service

# Feature #153 — permanent lokal poster-cache. Bevidst UDEN login-krav,
# samme princip som TMDb's egen CDN havde før (ren billed-visning, ingen
# følsom data): postere skal også kunne vises på den offentlige /bio-side
# for uindloggede besøgende (CinemaPublic.jsx).
router = APIRouter(prefix="/api/posters", tags=["posters"])


@router.get("/{size}/{path:path}")
async def get_poster(
    size: str, path: str, db: AsyncIOMotorDatabase = Depends(get_database)
) -> Response:
    result = await poster_cache_service.get_or_fetch(db, size, path)
    if result is None:
        return Response(status_code=404)
    data, content_type = result
    return Response(
        content=data,
        media_type=content_type,
        # Cachet permanent i backend'en, og (size, path) peger altid på
        # nøjagtig samme bytes — så browseren må også gerne gemme den for altid.
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
