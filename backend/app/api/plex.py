from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.plex import (
    PlexAvailabilityMap,
    PlexDiagnostics,
    PlexImportRequest,
    PlexImportResult,
    PlexKind,
)
from app.services import audit_log_service, plex_service

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


@router.post("/import", response_model=PlexImportResult, dependencies=[Depends(require_admin)])
async def import_from_plex(
    payload: PlexImportRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Opretter alt det Plex har, som portalen ikke har i forvejen (feature
    #90). `dry_run: true` (default) viser hvad der ville ske uden at oprette
    noget. **Kræver admin** — en enkelt udførelse kan oprette hundredvis af
    poster."""
    result = await plex_service.import_from_plex(db, payload, current_user["username"])
    # Kun den faktiske import logges — en forhåndsvisning ændrer intet, og
    # ville drukne loggen hvis man klikker sig frem og tilbage.
    if not payload.dry_run and result.ok:
        await audit_log_service.record(
            db,
            current_user["username"],
            "plex.imported",
            f"{len(result.imported)} oprettet, {result.already_present} fandtes i forvejen",
        )
    return result


@router.get("/diagnostics", response_model=PlexDiagnostics, dependencies=[Depends(require_admin)])
async def get_diagnostics(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Admin-only fejlsøgning: forbindelse, sektioner, guid-dækning og hvor
    mange af *vores* film/serier der faktisk matchede. Henter altid friskt,
    så en netop rettet URL/token afprøves med det samme."""
    return await plex_service.get_diagnostics(db)
