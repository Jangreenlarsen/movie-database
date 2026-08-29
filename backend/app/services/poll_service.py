"""Feature #162 (Jan, 2026-08-15: "Kunne man lave en afstemning side hvor
man kunne stemme på nogen udvalgte film hvor den/dem så blev vist på en
given dato?", taget op igen 2026-08-29 med scope afklaret via fire
spørgsmål): admin udvælger kandidat-film/serier, husstanden stemmer (én
stemme pr. bruger, ombestembelig mens afstemningen er åben, synlige
stemmetal undervejs), admin lukker afstemningen og vælger derefter manuelt
blandt en evt. uafgjort føring hvilken titel der rent faktisk programsættes
(genbruger screening_service.create_screening, samme "vælg dato" flow som
en almindelig visnings-anmodning)."""

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import InvalidPollCandidateError, PollNotFoundError, PollNotOpenError
from app.models.poll import Poll, PollCandidateResult, PollCreate
from app.repositories import poll_repository
from app.services import message_service, screening_service


async def _to_poll_model(db: AsyncIOMotorDatabase, document: dict, viewer_username: str) -> Poll:
    votes = document.get("votes", [])
    counts = [0] * len(document["candidates"])
    my_vote = None
    for vote in votes:
        idx = vote.get("candidate_index")
        if idx is not None and 0 <= idx < len(counts):
            counts[idx] += 1
        if vote.get("username") == viewer_username:
            my_vote = idx

    candidates = []
    for index, candidate in enumerate(document["candidates"]):
        # Genbruger screening_service's egen opslags-hjælper — samme
        # "enrich ved læsning, gem aldrig på selve dokumentet"-mønster som
        # Screening/ScreeningRequest allerede bruger, så en senere TMDb-sync
        # eller poster-ændring afspejles automatisk her også.
        display = await screening_service._resolve_display_info(
            db, candidate["media_kind"], candidate.get("movie_id"), candidate.get("tv_show_id")
        )
        candidates.append(
            PollCandidateResult(
                media_kind=candidate["media_kind"],
                movie_id=candidate.get("movie_id"),
                tv_show_id=candidate.get("tv_show_id"),
                title=display.get("title"),
                year=display.get("year"),
                poster_url=display.get("poster_url"),
                vote_count=counts[index],
            )
        )

    winner_indices: list[int] = []
    if document["status"] != "open" and any(counts):
        top = max(counts)
        winner_indices = [i for i, c in enumerate(counts) if c == top]

    return Poll(
        id=str(document["_id"]),
        title=document.get("title"),
        status=document["status"],
        candidates=candidates,
        total_votes=len(votes),
        my_vote=my_vote,
        winner_indices=winner_indices,
        scheduled_screening_id=document.get("scheduled_screening_id"),
        created_by=document["created_by"],
        created_at=document["created_at"],
        closed_at=document.get("closed_at"),
    )


async def create_poll(db: AsyncIOMotorDatabase, payload: PollCreate, admin: dict) -> Poll:
    now = datetime.now(timezone.utc)
    document = {
        "title": payload.title,
        "candidates": [c.model_dump() for c in payload.candidates],
        "votes": [],
        "status": "open",
        "created_by": admin["username"],
        "created_at": now,
        "closed_at": None,
        "scheduled_screening_id": None,
    }
    created = await poll_repository.insert(db, document)
    return await _to_poll_model(db, created, admin["username"])


async def list_polls(db: AsyncIOMotorDatabase, status: str | None, viewer_username: str) -> list[Poll]:
    documents = await poll_repository.find_all(db, status)
    return [await _to_poll_model(db, doc, viewer_username) for doc in documents]


async def get_poll(db: AsyncIOMotorDatabase, poll_id: str, viewer_username: str) -> Poll:
    document = await poll_repository.find_by_id(db, poll_id)
    if document is None:
        raise PollNotFoundError(poll_id)
    return await _to_poll_model(db, document, viewer_username)


async def cast_vote(db: AsyncIOMotorDatabase, poll_id: str, candidate_index: int, voter: dict) -> Poll:
    document = await poll_repository.find_by_id(db, poll_id)
    if document is None:
        raise PollNotFoundError(poll_id)
    if document["status"] != "open":
        raise PollNotOpenError()
    if not 0 <= candidate_index < len(document["candidates"]):
        raise InvalidPollCandidateError()

    updated = await poll_repository.upsert_vote(
        db, poll_id, voter["username"], candidate_index, datetime.now(timezone.utc)
    )
    return await _to_poll_model(db, updated, voter["username"])


async def close_poll(db: AsyncIOMotorDatabase, poll_id: str, admin: dict) -> Poll:
    document = await poll_repository.find_by_id(db, poll_id)
    if document is None:
        raise PollNotFoundError(poll_id)
    if document["status"] != "open":
        raise PollNotOpenError()

    updated = await poll_repository.set_status(db, poll_id, "closed", datetime.now(timezone.utc))
    model = await _to_poll_model(db, updated, admin["username"])
    # Best-effort, samme mønster som notify_screening_request_*: en fejl her
    # må aldrig vælte selve lukningen, som allerede er gennemført.
    try:
        await message_service.notify_poll_closed(db, updated, model, admin)
    except Exception:
        pass
    return model
