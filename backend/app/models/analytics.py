from pydantic import BaseModel, Field, model_validator

from app.models.movie import NamedCount

# Feature #125 — besøgs-statistik. Et "besøg" er enten en side/fane (kind
# "page") eller en åbnet titel (kind "title", med reference til film/serie).


class VisitCreate(BaseModel):
    """Skrives af frontend ved fane-skift, /bio-visning og åbning af en
    detalje-modal. Offentligt endpoint (ingen auth) — brugernavnet udledes
    server-side af en evt. gyldig cookie, aldrig af payloaden, så et besøg
    ikke kan tilskrives en anden bruger end den der reelt er logget ind."""

    page: str = Field(min_length=1, max_length=64)
    kind: str = "page"
    resource_kind: str | None = None  # "movie" | "tv" for titel-besøg
    resource_id: str | None = None
    title: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def normalize_kind(self) -> "VisitCreate":
        # Ukendt kind degraderer til "page" frem for at fejle — et besøgs-kald
        # må aldrig kunne vælte klienten med en valideringsfejl.
        if self.kind not in ("page", "title"):
            self.kind = "page"
        return self


class VisitStats(BaseModel):
    total_visits: int
    visits_today: int
    unique_users: int
    guest_visits: int
    # name=YYYY-MM-DD, kontinuerlig serie over de sidste 14 dage (0-dage med).
    per_day: list[NamedCount] = Field(default_factory=list)
    # name=side-nøgle ("library"/"tv"/"bio"/...), oversættes i frontend.
    per_page: list[NamedCount] = Field(default_factory=list)
    top_titles: list[NamedCount] = Field(default_factory=list)
    # name=brugernavn, eller sentinel "__guest__" for anonyme besøg.
    per_user: list[NamedCount] = Field(default_factory=list)
