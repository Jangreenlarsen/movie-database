from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.poll import Poll, PollCandidatesUpdate, PollCreate, PollVoteRequest
from app.services import poll_service

# Feature #162 — admin udvælger kandidater og lukker/afgør afstemningen
# (require_admin på de skrive-endpoints der ændrer selve afstemningen);
# at STEMME er derimod åbent for enhver logget-ind rolle, inklusive gæster —
# samme princip som feature #72 gav gæster lov til at anmode om en
# forvisning: den ene skrive-handling de reelt har adgang til.
#
# Feature #213 (Jan: "guest kan opret en afsteming ... men det er en adm som
# skal godkende at afsteming skal gøre global for alle") — OPRETTELSE er nu
# også åbent for enhver rolle (require_admin fjernet fra create_poll
# herunder), men resultatet afhænger af hvem der opretter: kun en admins
# afstemning starter synlig for alle med det samme (se
# poll_service.create_poll). Godkendelse og kandidat-redigering af andres
# forslag forbliver strengt admin-only.
router = APIRouter(
    prefix="/api/polls", tags=["polls"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[Poll])
async def list_polls(
    status: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await poll_service.list_polls(db, status, current_user)


@router.get("/{poll_id}", response_model=Poll)
async def get_poll(
    poll_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await poll_service.get_poll(db, poll_id, current_user)


@router.post("", response_model=Poll, status_code=201)
async def create_poll(
    payload: PollCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await poll_service.create_poll(db, payload, current_user)


@router.patch(
    "/{poll_id}/candidates", response_model=Poll, dependencies=[Depends(require_admin)]
)
async def update_poll_candidates(
    poll_id: str,
    payload: PollCandidatesUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await poll_service.update_poll_candidates(db, poll_id, payload.candidates, current_user)


@router.post("/{poll_id}/approve", response_model=Poll, dependencies=[Depends(require_admin)])
async def approve_poll(
    poll_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await poll_service.approve_poll(db, poll_id, current_user)


@router.post("/{poll_id}/vote", response_model=Poll)
async def vote(
    poll_id: str,
    payload: PollVoteRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await poll_service.cast_vote(db, poll_id, payload.candidate_index, current_user)


@router.post("/{poll_id}/close", response_model=Poll, dependencies=[Depends(require_admin)])
async def close_poll(
    poll_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await poll_service.close_poll(db, poll_id, current_user)


@router.delete("/{poll_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_poll(
    poll_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await poll_service.delete_poll(db, poll_id, current_user)
