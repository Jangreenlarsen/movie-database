from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MessageCreate(BaseModel):
    """Feature #100 — en besked fra en admin.

    `recipient_user_id: None` betyder rundsendt til alle aktive brugere;
    ellers går den til præcis den ene bruger."""

    subject: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)
    recipient_user_id: str | None = None

    @field_validator("subject", "body")
    @classmethod
    def not_blank(cls, value: str) -> str:
        """`min_length` tæller mellemrum med, så " " ville slippe igennem og
        blive til en tom besked når den trimmes ved gem. Trim derfor her, og
        afvis hvis der ikke er noget tilbage — samme "tjek alle former for
        tom"-princip som CLAUDE.md regel 16 beskriver."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Feltet må ikke være tomt")
        return trimmed


class MessageRecipient(BaseModel):
    user_id: str
    # Kopieret ind ved afsendelse, så afsender-oversigten kan vise navnet
    # også efter en bruger er slettet — ellers ville "læst af 3 af 5" pege
    # på brugere der ikke længere kan slås op.
    username: str
    read_at: datetime | None = None


class Message(BaseModel):
    """Én besked set fra afsenderens side — med hele modtagerlisten."""

    id: str
    subject: str
    body: str
    sent_by: str
    created_at: datetime
    recipients: list[MessageRecipient]
    # Udledt af `recipients`, men beregnet i service-laget så frontend ikke
    # skal tælle det samme igen for hver besked i listen.
    read_count: int
    recipient_count: int
    # True når beskeden gik til alle frem for til én udvalgt bruger. Kan
    # ikke udledes af antallet: en rundsendt besked i en portal med én
    # bruger ville ellers se ud som en personlig.
    is_broadcast: bool


class InboxMessage(BaseModel):
    """Én ulæst besked set fra modtagerens side. Modtagerlisten er bevidst
    ikke med — hvem der ellers har fået beskeden, er afsenderens oplysning,
    ikke de øvrige modtageres."""

    id: str
    subject: str
    body: str
    sent_by: str
    created_at: datetime


class MarkAllReadResult(BaseModel):
    """Feature #226 — svar fra "Ryd alle" i Indstillinger → Beskeder."""

    marked_count: int


class MessageTemplateFields(BaseModel):
    """Feature #225 — de RÅ, redigerbare skabelon-felter for én besked-type,
    stadig med bogstavelige `{pladsholder}`-navne (IKKE substitueret med
    eksempel-data) — det en rediger-formular skal forudfyldes med.
    `headline`/`tagline`/`accent`/`cta_label` er `None` for de fire
    bruger→admin-notifikationer uden en rig e-mail-udgave."""

    subject: str
    body: str
    headline: str | None = None
    tagline: str | None = None
    accent: Literal["gold", "muted"] | None = None
    cta_label: str | None = None


class MessagePreview(BaseModel):
    """Feature #223 — ét indslag i admins besked-design-katalog
    (Indstillinger → Beskeder). Bygget af message_preview_service fra de
    SAMME `_content_*`-byggefunktioner som de rigtige notify_*-funktioner i
    message_service.py selv bruger (med eksempel-data i stedet for en
    rigtig hændelse), så previewet aldrig kan vise en anden ordlyd end den
    der rent faktisk sendes. `html` er `None` for de få besked-typer der
    kun nogensinde har været almindelig tekst (bruger→admin-notifikationer
    om nye ønsker/anmodninger/forslag) — ingen rig e-mail-udgave findes for
    dem.

    Feature #225 — `editable` er `False` for `poll_cancelled_1..5` (en fast
    tilfældig-varianter-pulje, ikke én skabelon med pladsholdere, se
    message_service.py's modul-docstring); alle øvrige typer er
    redigerbare. `template`/`placeholders`/`is_customized` er kun sat når
    `editable` er sandt."""

    key: str
    name: str
    description: str
    subject: str
    body: str
    html: str | None = None
    editable: bool = False
    is_customized: bool = False
    placeholders: list[str] = Field(default_factory=list)
    template: MessageTemplateFields | None = None


class MessageTemplateUpdate(BaseModel):
    """Feature #225 — en admins tilpasning af én besked-types skabelon. Kun
    de felter der rent faktisk ændres er med (`exclude_unset` i service-
    laget) — et delvist kald ændrer ikke felter det ikke selv rørte.
    `.format(**sample)`-valideres i `message_template_service` mod
    `message_service.TEMPLATE_DEFS[key].sample`, IKKE her — den validering
    kræver at kende den specifikke nøgles pladsholder-sæt, som modellen her
    ikke selv har adgang til."""

    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=2000)
    headline: str | None = Field(default=None, max_length=200)
    tagline: str | None = Field(default=None, max_length=300)
    accent: Literal["gold", "muted"] | None = None
    cta_label: str | None = Field(default=None, max_length=60)

    @field_validator("subject", "body", "headline", "tagline", "cta_label")
    @classmethod
    def not_blank(cls, value: str | None) -> str | None:
        """Samme "tjek alle former for tom"-princip som MessageCreate.not_blank
        ovenfor (CLAUDE.md regel 16) — `None` betyder "dette felt er slet
        ikke med i kaldet" og skal bevares som `None` (`exclude_unset`
        afgør senere om feltet overhovedet skrives), men en tilstedeværende,
        men whitespace-only streng er reelt en tom skabelon-tekst."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Feltet må ikke være tomt")
        return trimmed
