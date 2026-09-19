from datetime import datetime

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


class MessagePreview(BaseModel):
    """Feature #223 — ét indslag i admins read-only besked-design-katalog
    (Indstillinger → Beskeder). Bygget af message_preview_service fra de
    SAMME `_content_*`-byggefunktioner som de rigtige notify_*-funktioner i
    message_service.py selv bruger (med eksempel-data i stedet for en
    rigtig hændelse), så previewet aldrig kan vise en anden ordlyd end den
    der rent faktisk sendes. `html` er `None` for de få besked-typer der
    kun nogensinde har været almindelig tekst (bruger→admin-notifikationer
    om nye ønsker/anmodninger/forslag) — ingen rig e-mail-udgave findes for
    dem."""

    key: str
    name: str
    description: str
    subject: str
    body: str
    html: str | None = None
