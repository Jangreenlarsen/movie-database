from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.plex import PlexAvailabilityMap, PlexDiagnostics, PlexKind
from app.services import plex_service

router = APIRouter(prefix="/api/plex", tags=["plex"], dependencies=[Depends(get_current_user)])


@router.get("/availability", response_model=PlexAvailabilityMap)
async def get_availability(
    kind: PlexKind = Query(default="movie"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Hele bibliotekets Plex-status i ét kald (feature #88). Svarer altid
    200 — en slukket eller ukonfigureret Plex-server rapporteres via
    `ok`/`error` i kroppen, så et badge der mangler aldrig kan vælte
    biblioteksvisningen."""
    return await plex_service.get_availability_map(db, kind)


@router.post("/refresh", response_model=PlexAvailabilityMap)
async def refresh_availability(
    kind: PlexKind = Query(default="movie"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Tvinger et nyt hent uden om cachen — til lige efter man har lagt en
    ny film i Plex og ikke vil vente på at TTL'en løber ud."""
    return await plex_service.get_availability_map(db, kind, force_refresh=True)


@router.get("/diagnostics", response_model=PlexDiagnostics, dependencies=[Depends(require_admin)])
async def get_diagnostics(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Admin-only fejlsøgning: forbindelse, sektioner, guid-dækning og hvor
    mange af *vores* film/serier der faktisk matchede. Henter altid friskt,
    så en netop rettet URL/token afprøves med det samme."""
    return await plex_service.get_diagnostics(db)
