from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Feature #228 — hvad der skal ske med beskeden til alle, når en film/serie
# rammer biblioteket (oprettet direkte, eller flyttet ind fra ønskelisten):
#   "queue" — læg titlen i den samlede opdatering (sendes senere, samlet)
#   "now"   — send en besked om netop denne titel med det samme (#222)
#   "none"  — ingen besked
AnnounceMode = Literal["none", "queue", "now"]
MediaKind = Literal["movie", "tv"]


class PendingAnnouncement(BaseModel):
    id: str
    media_kind: MediaKind
    item_id: str
    # Slået op fra selve film-/serie-dokumentet ved læsning, så en rettet
    # titel eller plakat slår igennem uden at køen skal opdateres.
    title: str
    poster_url: str | None = None
    added_by: str
    created_at: datetime


class AnnouncementSendResult(BaseModel):
    sent_count: int
