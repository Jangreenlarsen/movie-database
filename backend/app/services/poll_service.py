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

from app.core.errors import (
    InvalidPollCandidateError,
    PollNotFoundError,
    PollNotOpenError,
    PollNotPendingError,
)
from app.models.poll import Poll, PollCandidateCreate, PollCandidateResult, PollCreate
from app.repositories import poll_repository, screening_repository
from app.services import message_service, screening_service

# Feature #215 — "aktøren" bag en automatisk deadline-lukning. message_
# service.send() kræver et rigtigt _id/username (bruges bl.a. som
# document["sent_by"]) — et tomt dict ville kaste en KeyError, som ellers
# ville blive tavst slugt af _perform_close's try/except og efterlade ingen
# notifikation overhovedet. "system" er ikke et rigtigt brugernavn og slås
# aldrig op mod users-collection'en (sent_by er ren visningstekst).
_SYSTEM_ACTOR = {"_id": "system", "username": "system"}


def _can_view_pending(document: dict, viewer: dict) -> bool:
    """Feature #213 — en 'pending' afstemning (en ikke-admins forslag, endnu
    ikke godkendt) er kun synlig for forslagsstilleren selv og for admin.
    Bruges af både list_polls (filtrerer listen) og get_poll (skjuler et
    direkte id-opslag på samme måde, så der ikke er to forskellige adfærd
    afhængig af hvilken vej man kom ind)."""
    if document["status"] != "pending":
        return True
    return viewer.get("role") == "admin" or document["created_by"] == viewer.get("username")


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
        target_date=document.get("target_date"),
        voting_deadline=document.get("voting_deadline"),
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


async def create_poll(db: AsyncIOMotorDatabase, payload: PollCreate, creator: dict) -> Poll:
    """Feature #213 (Jan: "guest kan opret en afsteming ... men det er en
    adm som skal godkende at afsteming skal gøre global for alle") — enhver
    logget-ind rolle må nu oprette (require_admin fjernet fra selve
    endpointet, se api/polls.py), men KUN en admins afstemning starter
    'open' med det samme. Alle andres starter 'pending' — usynlig for andre
    end forslagsstilleren selv, indtil en admin godkender den
    (approve_poll). Admin skal ikke selv godkende sine egne afstemninger,
    som hidtil."""
    now = datetime.now(timezone.utc)
    is_admin = creator.get("role") == "admin"
    document = {
        "title": payload.title,
        "target_date": payload.target_date,
        "voting_deadline": payload.voting_deadline,
        "candidates": [c.model_dump() for c in payload.candidates],
        "votes": [],
        "status": "open" if is_admin else "pending",
        "created_by": creator["username"],
        "created_at": now,
        "closed_at": None,
        "scheduled_screening_id": None,
    }
    created = await poll_repository.insert(db, document)
    if not is_admin:
        # Best-effort, samme mønster som de øvrige notify_admins_new_*
        # funktioner — en fejl her må aldrig vælte selve oprettelsen.
        try:
            await message_service.notify_admins_new_poll_suggestion(db, creator, created)
        except Exception:
            pass
    return await _to_poll_model(db, created, creator["username"])


async def update_poll_candidates(
    db: AsyncIOMotorDatabase, poll_id: str, candidates: list[PollCandidateCreate], admin: dict
) -> Poll:
    """Feature #213 (Jan: "det er også adm som kan tilret listen som en
    guest vil laveafsteming på") — admin erstatter hele kandidatlisten på
    en 'pending' afstemning før den godkendes, fx for at fjerne en
    upassende foreslået titel. Kun muligt mens afstemningen stadig
    afventer — der er ingen stemmer at ugyldiggøre på det tidspunkt."""
    document = await poll_repository.find_by_id(db, poll_id)
    if document is None:
        raise PollNotFoundError(poll_id)
    if document["status"] != "pending":
        raise PollNotPendingError()

    updated = await poll_repository.set_candidates(
        db, poll_id, [c.model_dump() for c in candidates]
    )
    return await _to_poll_model(db, updated, admin["username"])


async def approve_poll(db: AsyncIOMotorDatabase, poll_id: str, admin: dict) -> Poll:
    """Feature #213 — gør en 'pending' afstemning global: fra nu af kan alle
    se og stemme på den, præcis som en admin-oprettet afstemning altid har
    kunnet."""
    document = await poll_repository.find_by_id(db, poll_id)
    if document is None:
        raise PollNotFoundError(poll_id)
    if document["status"] != "pending":
        raise PollNotPendingError()

    updated = await poll_repository.set_status(db, poll_id, "open")
    model = await _to_poll_model(db, updated, admin["username"])
    try:
        await message_service.notify_poll_approved(db, updated, admin)
    except Exception:
        pass
    return model


async def _has_premiered(db: AsyncIOMotorDatabase, document: dict) -> bool:
    """Feature #208-opfølgning (Jan: "de skal forsvinde efter film har haft
    premiære") — en planlagt afstemning forsvinder fra oversigten så snart
    dens fremvisning rent faktisk er overstået. Slår altid selve
    fremvisningen op live (aldrig et gemt tidspunkt på afstemningen selv):
    `scheduled_at` kan redigeres bagefter (PATCH /api/screenings/{id}), og
    en kopi på afstemningen ville kunne komme ud af trit med den ægte dato.
    Kan IKKE afgøres (fremvisningen findes ikke længere, fx slettet fra
    kalenderen) → vises fortsat, i stedet for at forsvinde uden forklaring."""
    if document["status"] != "scheduled" or not document.get("scheduled_screening_id"):
        return False
    screening = await screening_repository.find_by_id(db, document["scheduled_screening_id"])
    if screening is None:
        return False
    scheduled_at = screening["scheduled_at"]
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    return scheduled_at < datetime.now(timezone.utc)


async def list_polls(db: AsyncIOMotorDatabase, status: str | None, viewer: dict) -> list[Poll]:
    documents = [await _auto_close_if_expired(db, doc) for doc in await poll_repository.find_all(db, status)]
    visible = [
        doc
        for doc in documents
        if not await _has_premiered(db, doc) and _can_view_pending(doc, viewer)
    ]
    return [await _to_poll_model(db, doc, viewer["username"]) for doc in visible]


async def delete_poll(db: AsyncIOMotorDatabase, poll_id: str, admin: dict) -> None:
    """Feature #208-opfølgning (Jan: "eller adm vælger at de skal
    forsvinde") — admin kan til enhver tid fjerne en afstemning fra
    oversigten manuelt, uanset status. Rører ALDRIG en evt. tilknyttet
    fremvisning (`scheduled_screening_id`) — den er en selvstændig, ægte
    kalender-post nu, ikke længere blot afstemningens data; at slette
    afstemningen er ren oprydning af selve stemme-optællingen, ikke en
    aflysning af aftenen.

    Feature #213 — samme endpoint dobler nu som "afvis" for en 'pending'
    afstemning: der er ikke bedt om en separat afvis-handling, og en admin
    der fjerner en endnu-ikke-godkendt afstemning MENER reelt at afvise
    forslaget. Forslagsstilleren får besked i det tilfælde (ikke ved
    fjernelse af en allerede afgjort afstemning, hvor alle involverede
    allerede har set udfaldet).

    Feature #216 (Jan: "når man sletter en afstemning så få users ikke
    notet om det") — det manglende tilfælde var en ENDNU ÅBEN afstemning:
    hverken 'pending'-grenen ovenfor (ingen forslagsstiller-besked, den er
    jo allerede godkendt) eller den bevidste tavshed for en afgjort
    afstemning (allerede set udfaldet) dækkede den. Voterne på en 'open'
    afstemning får nu en munter aflysnings-besked (notify_poll_cancelled)."""
    document = await poll_repository.find_by_id(db, poll_id)
    if document is None:
        raise PollNotFoundError(poll_id)
    was_pending = document["status"] == "pending"
    was_open = document["status"] == "open"

    if not await poll_repository.delete(db, poll_id):
        raise PollNotFoundError(poll_id)

    if was_pending and document["created_by"] != admin.get("username"):
        try:
            await message_service.notify_poll_suggestion_rejected(db, document, admin)
        except Exception:
            pass
    elif was_open:
        try:
            await message_service.notify_poll_cancelled(db, document, admin)
        except Exception:
            pass


async def get_poll(db: AsyncIOMotorDatabase, poll_id: str, viewer: dict) -> Poll:
    document = await poll_repository.find_by_id(db, poll_id)
    if document is None or not _can_view_pending(document, viewer):
        raise PollNotFoundError(poll_id)
    document = await _auto_close_if_expired(db, document)
    return await _to_poll_model(db, document, viewer["username"])


async def cast_vote(db: AsyncIOMotorDatabase, poll_id: str, candidate_index: int, voter: dict) -> Poll:
    document = await poll_repository.find_by_id(db, poll_id)
    if document is None:
        raise PollNotFoundError(poll_id)
    document = await _auto_close_if_expired(db, document)
    if document["status"] != "open":
        raise PollNotOpenError()
    if not 0 <= candidate_index < len(document["candidates"]):
        raise InvalidPollCandidateError()

    updated = await poll_repository.upsert_vote(
        db, poll_id, voter["username"], candidate_index, datetime.now(timezone.utc)
    )
    return await _to_poll_model(db, updated, voter["username"])


async def _perform_close(db: AsyncIOMotorDatabase, document: dict, actor: dict) -> dict:
    """Delt lukke-logik for admins manuelle 'Luk afstemning' (close_poll) og
    den automatiske lukning når en sat stemme-frist er overskredet
    (_auto_close_if_expired, feature #215) — samme skrivning og
    notifikation, uanset hvad der udløste den. `actor` er _SYSTEM_ACTOR ved
    automatisk lukning (ingen menneskelig aktør — notify_poll_closed
    udelader den fra modtagerlisten på samme måde som en rigtig admin,
    blot under brugernavnet "system", som ingen rigtig bruger kan hedde)."""
    updated = await poll_repository.set_status(db, str(document["_id"]), "closed", datetime.now(timezone.utc))
    model = await _to_poll_model(db, updated, actor.get("username", ""))
    # Best-effort, samme mønster som notify_screening_request_*: en fejl her
    # må aldrig vælte selve lukningen, som allerede er gennemført.
    try:
        await message_service.notify_poll_closed(db, updated, model, actor)
    except Exception:
        pass
    return updated


async def close_poll(db: AsyncIOMotorDatabase, poll_id: str, admin: dict) -> Poll:
    document = await poll_repository.find_by_id(db, poll_id)
    if document is None:
        raise PollNotFoundError(poll_id)
    if document["status"] != "open":
        raise PollNotOpenError()

    updated = await _perform_close(db, document, admin)
    return await _to_poll_model(db, updated, admin["username"])


async def _auto_close_if_expired(db: AsyncIOMotorDatabase, document: dict) -> dict:
    """Feature #215 — ingen baggrundsjob i denne app; en overskredet
    stemme-frist opdages og lukkes lazily ved næste opslag/stemme-forsøg,
    samme "computed on read"-princip som _has_premiered ovenfor."""
    if document["status"] != "open":
        return document
    deadline = document.get("voting_deadline")
    if deadline is None:
        return document
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) < deadline:
        return document
    return await _perform_close(db, document, _SYSTEM_ACTOR)
