"""Feature #228 — "Samlet opdatering". Nye film/serier kan lægges i en fælles
kø i stedet for at udløse én besked pr. titel (#222); en admin eller
standardbruger sender så hele køen som ÉN besked til alle, når det passer.

Køen er fælles for hele husstanden (Jans valg 2026-09-23): enhver admin/
standardbruger kan se den, fjerne titler og sende den. Gæster kan hverken
tilføje til biblioteket eller røre køen (håndhævet med `require_not_guest`
på routerne)."""

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import AnnouncementNotFoundError, EmptyAnnouncementQueueError
from app.models.announcement import (
    AnnounceMode,
    AnnouncementSendResult,
    MediaKind,
    PendingAnnouncement,
)
from app.repositories import announcement_repository, movie_repository, tv_show_repository
from app.services import message_service


def resolve_mode(announce: AnnounceMode | None, notify_all: bool) -> AnnounceMode:
    """`announce` vinder, når den er sendt. Ellers er det ældre `notify_all`
    (#222) et alias for "now" — så en klient der ikke kender det nye felt,
    opfører sig præcis som før."""
    if announce is not None:
        return announce
    return "now" if notify_all else "none"


async def handle_library_addition(
    db: AsyncIOMotorDatabase,
    user: dict,
    media_kind: MediaKind,
    item_id: str,
    title: str | None,
    poster_url: str | None,
    mode: AnnounceMode,
) -> None:
    """Kaldt af movie_service/tv_show_service når en titel rammer
    biblioteket. Best-effort, som #222's broadcast: selve film-/serie-
    gemningen er allerede sket, så en fejl her må ikke vælte den."""
    if mode == "now":
        await message_service.notify_library_addition_broadcast(
            db, user, title, is_tv=media_kind == "tv", poster_url=poster_url
        )
    elif mode == "queue":
        try:
            await announcement_repository.insert_if_absent(
                db,
                {
                    "media_kind": media_kind,
                    "item_id": item_id,
                    "added_by": user.get("username"),
                    "created_at": datetime.now(timezone.utc),
                },
            )
        except Exception:
            # Samme begrundelse som notify_*-funktionernes try/except: titlen
            # er gemt; en manglende kø-post er en mindre skade end en fejl
            # på selve gemningen.
            pass


async def _find_item(db: AsyncIOMotorDatabase, media_kind: str, item_id: str) -> dict | None:
    if media_kind == "tv":
        return await tv_show_repository.find_by_id(db, item_id)
    return await movie_repository.find_by_id(db, item_id)


def _display_title(item: dict, media_kind: str) -> str:
    if media_kind == "tv":
        return item.get("name") or item.get("title") or "Ukendt titel"
    return item.get("title") or "Ukendt titel"


async def _live_queue(db: AsyncIOMotorDatabase) -> list[tuple[dict, PendingAnnouncement]]:
    """Køen beriget med titel/plakat fra selve film-/serie-dokumentet.
    Poster hvis titel siden er slettet eller flyttet tilbage til ønskelisten,
    ryddes væk her (CLAUDE.md regel 16) — de ville ellers stå som "Ukendt"
    for evigt, eller blive annonceret som ny i samlingen uden at være det."""
    result: list[tuple[dict, PendingAnnouncement]] = []
    for document in await announcement_repository.find_all(db):
        item = await _find_item(db, document["media_kind"], document["item_id"])
        if item is None or item.get("is_wishlist"):
            await announcement_repository.delete(db, str(document["_id"]))
            continue
        result.append(
            (
                document,
                PendingAnnouncement(
                    id=str(document["_id"]),
                    media_kind=document["media_kind"],
                    item_id=document["item_id"],
                    title=_display_title(item, document["media_kind"]),
                    poster_url=item.get("poster_url"),
                    added_by=document.get("added_by") or "",
                    created_at=document["created_at"],
                ),
            )
        )
    return result


async def list_pending(db: AsyncIOMotorDatabase) -> list[PendingAnnouncement]:
    return [model for _, model in await _live_queue(db)]


async def remove(db: AsyncIOMotorDatabase, announcement_id: str) -> None:
    if not await announcement_repository.delete(db, announcement_id):
        raise AnnouncementNotFoundError(announcement_id)


async def send(db: AsyncIOMotorDatabase, sender: dict) -> AnnouncementSendResult:
    """Sender hele køen som én besked og fjerner derefter PRÆCIS de sendte
    poster. En titel lagt i kø mens beskeden gik ud, er ikke nævnt i den og
    bliver derfor stående til næste gang. Fejler afsendelsen (fx test-
    tilstand), bobler fejlen op, og køen står urørt."""
    queue = await _live_queue(db)
    if not queue:
        raise EmptyAnnouncementQueueError()
    items = [
        {"title": model.title, "media_kind": model.media_kind, "poster_url": model.poster_url}
        for _, model in queue
    ]
    await message_service.send_library_additions_digest(db, sender, items)
    await announcement_repository.delete_many_by_ids(db, [document["_id"] for document, _ in queue])
    return AnnouncementSendResult(sent_count=len(queue))
