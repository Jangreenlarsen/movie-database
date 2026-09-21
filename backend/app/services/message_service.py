"""Beskeder fra admin til brugerne (feature #100).

Feature #223 (Jan: "hvordan kan jeg se hvordan en besked se ud, kan vi
lave en besked design editor hvor alle de besked typer som er i spil kan
se og edit") — hver `notify_*`-funktion nedenfor har sin tekst-opbygning
(emne/brødtekst/e-mail-indhold) udtrukket til en lille, ren `_content_*`-
funktion umiddelbart ovenfor den.

Feature #225 (samme Jan-citat, anden halvdel: "... og edit") — den
egentlige redigering. Hver besked-types STANDARD-ordlyd bor nu i ét
centralt register, `TEMPLATE_DEFS` nedenfor, som ren skabelon-tekst med
`{pladsholder}`-syntaks (Pythons eget `str.format`). `_render()` slår en
evt. admin-gemt tilpasning op i `overrides` (hentet ÉN gang pr.
notify_*-kald fra `message_template_repository`, aldrig pr. modtager i en
løkke) og falder tilbage til `TEMPLATE_DEFS` hvis intet er tilpasset —
samme "override eller kode-standard"-mønster som `system_settings_
repository` allerede bruger til API-nøgler. `message_preview_service.py`
kalder de SAMME `_content_*`-funktioner (med eksempel-data OG de samme
`overrides`) for at bygge admins preview-katalog, så previewet garanteret
aldrig kan vise en anden ordlyd end den der rent faktisk sendes.

Bevidst UDELADT fra skabelon-systemet: `notify_poll_cancelled`s pulje af
5 faste "aflyst"-varianter (feature #216) — den er strukturelt en
tilfældig-vittighed-pulje, ikke én skabelon med pladsholdere, og forbliver
hardkodet uændret."""

import logging
import random
from datetime import datetime, timezone
from typing import NamedTuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.errors import (
    EmailRateLimitedError,
    MessageNotFoundError,
    NoRecipientsError,
    TestModeActiveError,
    UserNotFoundError,
)
from app.integrations import email_client, email_templates
from app.models.message import InboxMessage, Message, MessageCreate, MessageRecipient
from app.models.poll import Poll, PollCandidateResult
from app.models.user import UserStatus
from app.repositories import message_repository, message_template_repository, user_repository

logger = logging.getLogger("moviedb")


class MessageContent(NamedTuple):
    """Feature #223 — returtypen for hver `_content_*`-byggefunktion.
    `html_kwargs`, når sat, gives direkte videre som
    `email_templates.render_notification_email(**html_kwargs)`; `None`
    betyder at denne besked-type aldrig har haft en rig e-mail-udgave (de
    interne bruger→admin-notifikationer sender kun almindelig tekst)."""

    subject: str
    body: str
    html_kwargs: dict | None = None


class MessageTemplateDef(NamedTuple):
    """Feature #225 — statisk definition af én redigerbar besked-type:
    dens STANDARD-ordlyd (brugt hvis ingen admin-tilpasning er gemt) og de
    eksempel-pladsholderværdier der bruges BÅDE til preview-kataloget og
    til at validere en gemt tilpasning (renderet mod netop disse værdier
    ved gem — en tastefejl i et pladsholder-navn som `{titel}` i stedet
    for `{title}` fanges dermed med det samme, ikke først ved den næste
    rigtige afsendelse). `headline`/`tagline`/`accent`/`cta_label` er
    `None` for de fire bruger→admin-notifikationer, som aldrig har haft
    en rig e-mail-udgave — `_render()` springer så hele HTML-opbygningen
    over, præcis som før #225."""

    subject: str
    body: str
    headline: str | None
    tagline: str | None
    accent: str | None
    cta_label: str | None
    sample: dict[str, str]


# Feature #225 — hver nøgle her matcher `message_preview_service.py`s
# katalog-nøgler 1:1 (minus `poll_cancelled_1..5`, se modul-docstringen).
# `{title}`/`{kind}`/`{poll_title}`/`{titles}`/`{when}`/`{username}`/
# `{site_url}` er de eneste pladsholder-navne der findes i hele registret —
# holdt bevidst få og genkendelige på tværs af typer.
TEMPLATE_DEFS: dict[str, MessageTemplateDef] = {
    "wishlist_moved": MessageTemplateDef(
        subject="Din ønskede {kind} er nu i biblioteket",
        body='Den {kind} du satte på indkøbslisten — "{title}" — er nu købt og lagt i biblioteket. 🎬',
        headline="Nu står den på hylden!",
        tagline='"{title}" er købt og klar til filmaften.',
        accent="gold",
        cta_label=None,
        sample={"title": "Dune: Part Two", "kind": "film"},
    ),
    "wishlist_approved": MessageTemplateDef(
        subject='Dit ønske "{title}" er godkendt',
        body='Den {kind} du ønskede — "{title}" — er nu godkendt og står på indkøbslisten. 🎬',
        headline="Dit ønske er godkendt!",
        tagline='"{title}" er nu godkendt og på vej til samlingen.',
        accent="gold",
        cta_label=None,
        sample={"title": "The Bear", "kind": "serie"},
    ),
    "wishlist_ordered": MessageTemplateDef(
        subject='Dit ønske "{title}" er bestilt',
        body='Den {kind} du ønskede — "{title}" — er nu bestilt. 🎬',
        headline="Bestilt!",
        tagline='"{title}" er nu bestilt — snart klar til filmaften.',
        accent="gold",
        cta_label=None,
        sample={"title": "Dune: Part Two", "kind": "film"},
    ),
    "wishlist_rejected": MessageTemplateDef(
        subject='Dit ønske "{title}" blev ikke godkendt',
        body='Den {kind} du ønskede — "{title}" — er desværre ikke blevet godkendt.',
        headline="Om dit ønske",
        tagline='"{title}" blev desværre ikke til noget denne gang.',
        accent="muted",
        cta_label=None,
        sample={"title": "Dune: Part Two", "kind": "film"},
    ),
    "admins_new_wishlist": MessageTemplateDef(
        subject="Nyt ønske på indkøbslisten",
        body='{username} har tilføjet "{title}" ({kind}) til ønskelisten.',
        headline=None,
        tagline=None,
        accent=None,
        cta_label=None,
        sample={"username": "anna", "title": "Dune: Part Two", "kind": "film"},
    ),
    "admins_new_screening_request": MessageTemplateDef(
        subject="Nyt ønske om visning i Voldby BIO",
        body='{username} ønsker at se "{title}" ({kind}) i Voldby BIO.',
        headline=None,
        tagline=None,
        accent=None,
        cta_label=None,
        sample={"username": "anna", "title": "The Bear", "kind": "serie"},
    ),
    "admins_new_poll_suggestion": MessageTemplateDef(
        subject="Nyt afstemnings-forslag afventer godkendelse",
        body='{username} har foreslået afstemningen "{poll_title}" — godkend eller afvis den under Voldby BIO.',
        headline=None,
        tagline=None,
        accent=None,
        cta_label=None,
        sample={"username": "anna", "poll_title": "Fredagsfilm"},
    ),
    "admins_new_candidate_suggestion": MessageTemplateDef(
        subject="Nyt kandidat-forslag afventer godkendelse",
        body=(
            '{username} har foreslået at tilføje "{title}" til afstemningen '
            '"{poll_title}" — godkend eller afvis den under Voldby BIO.'
        ),
        headline=None,
        tagline=None,
        accent=None,
        cta_label=None,
        sample={"username": "anna", "title": "Dune: Part Two", "poll_title": "Fredagsfilm"},
    ),
    "poll_candidate_approved": MessageTemplateDef(
        subject="Dit kandidat-forslag er godkendt",
        body='Dit forslag om at tilføje "{title}" til "{poll_title}" er godkendt — den er nu en rigtig kandidat, klar til at få stemmer.',
        headline="Dit kandidat-forslag er godkendt!",
        tagline='Dit forslag om at tilføje "{title}" til "{poll_title}" er godkendt — den er nu en rigtig kandidat, klar til at få stemmer.',
        accent="gold",
        cta_label=None,
        sample={"title": "Dune: Part Two", "poll_title": "Fredagsfilm"},
    ),
    "poll_candidate_rejected": MessageTemplateDef(
        subject="Om dit kandidat-forslag",
        body='Dit forslag om at tilføje "{title}" til "{poll_title}" blev desværre ikke godkendt denne gang.',
        headline="Om dit kandidat-forslag",
        tagline='Dit forslag om at tilføje "{title}" til "{poll_title}" blev desværre ikke godkendt denne gang.',
        accent="muted",
        cta_label=None,
        sample={"title": "Dune: Part Two", "poll_title": "Fredagsfilm"},
    ),
    "screening_request_declined": MessageTemplateDef(
        subject='Dit ønske om at se "{title}" blev afvist',
        body='Dit ønske om at se "{title}" i Voldby BIO er desværre ikke blevet til noget.',
        headline="Om din forvisnings-anmodning",
        tagline='Visningen af "{title}" blev desværre ikke til noget denne gang.',
        accent="muted",
        cta_label=None,
        sample={"title": "Dune: Part Two"},
    ),
    "screening_request_scheduled": MessageTemplateDef(
        subject='Din ønskede visning "{title}" er planlagt!',
        body='"{title}" er nu planlagt til visning i Voldby BIO{when}. 🎬',
        headline="Biografen venter!",
        tagline='"{title}" er nu planlagt til visning i Voldby BIO{when}.',
        accent="gold",
        cta_label=None,
        sample={"title": "Dune: Part Two", "when": " d. 12/12/2026 kl. 20:00"},
    ),
    "screening_scheduled_broadcast": MessageTemplateDef(
        subject='"{title}" er planlagt i Voldby BIO!',
        body='"{title}" er nu planlagt til visning i Voldby BIO{when}. 🎬',
        headline="Biografen venter!",
        tagline='"{title}" er nu planlagt til visning i Voldby BIO{when}.',
        accent="gold",
        cta_label=None,
        sample={"title": "Dune: Part Two", "when": " d. 12/12/2026 kl. 20:00"},
    ),
    "library_addition_broadcast": MessageTemplateDef(
        subject="Ny {kind} i samlingen: {title}!",
        body='"{title}" er lige blevet en del af Voldby BIO-samlingen! 🎬 Log ind og anmod om en visning: {site_url}',
        headline="Ny i samlingen!",
        tagline='"{title}" er nu en del af Voldby BIOs samling — anmod om en visning!',
        accent="gold",
        cta_label="Gå til Voldby BIO",
        sample={"title": "Dune: Part Two", "kind": "film", "site_url": "https://movie.laces.dk"},
    ),
    "poll_closed_single": MessageTemplateDef(
        subject="Afstemningen er afgjort",
        body='"{title}" vandt afstemningen!',
        headline="Afstemningen er afgjort!",
        tagline='"{title}" vandt afstemningen!',
        accent="gold",
        cta_label=None,
        sample={"title": "Dune: Part Two"},
    ),
    "poll_closed_tie": MessageTemplateDef(
        subject="Afstemningen er afgjort",
        body="Uafgjort mellem {titles} — admin vælger snart hvilken der bliver til noget.",
        headline="Afstemningen er afgjort!",
        tagline="Uafgjort mellem {titles} — admin vælger snart hvilken der bliver til noget.",
        accent="gold",
        cta_label=None,
        sample={"titles": "Dune: Part Two, Arrival"},
    ),
    "poll_scheduled": MessageTemplateDef(
        subject='Afstemningens vinder "{title}" er planlagt!',
        body='"{title}" er nu planlagt til visning i Voldby BIO{when}. 🎬',
        headline="Biografen venter!",
        tagline='"{title}" er nu planlagt til visning i Voldby BIO{when}.',
        accent="gold",
        cta_label=None,
        sample={"title": "Dune: Part Two", "when": " d. 12/12/2026 kl. 20:00"},
    ),
    "poll_approved": MessageTemplateDef(
        subject="Din afstemning er godkendt",
        body='"{poll_title}" er nu godkendt og åben for alle i Voldby BIO — alle kan stemme.',
        headline="Din afstemning er godkendt!",
        tagline='"{poll_title}" er nu godkendt og åben for alle i Voldby BIO — alle kan stemme.',
        accent="gold",
        cta_label=None,
        sample={"poll_title": "Fredagsfilm"},
    ),
    "poll_suggestion_rejected": MessageTemplateDef(
        subject="Om dit afstemnings-forslag",
        body='"{poll_title}" blev desværre ikke godkendt som afstemning denne gang.',
        headline="Om dit afstemnings-forslag",
        tagline='"{poll_title}" blev desværre ikke godkendt som afstemning denne gang.',
        accent="muted",
        cta_label=None,
        sample={"poll_title": "Fredagsfilm"},
    ),
}


def _render(
    key: str,
    placeholders: dict[str, str],
    poster_url: str | None,
    overrides: dict[str, dict],
) -> MessageContent:
    """Feature #225 — genbrugt af hver `_content_*`-funktion nedenfor.
    `overrides` er hele det gemte tilpasnings-sæt
    (`message_template_repository.find_all`, hentet ÉN gang pr.
    notify_*-kald — se disses egne kommentarer), ikke ét Mongo-opslag pr.
    besked-type/modtager. En manglende nøgle i `overrides` betyder "ingen
    tilpasning" — `TEMPLATE_DEFS[key]`s standard-ordlyd bruges så, med
    UÆNDRET output i forhold til før #225 (verificeret ved den fulde,
    allerede-eksisterende test-suite, som asserter eksakt ordlyd for
    stort set alle disse beskeder)."""
    definition = TEMPLATE_DEFS[key]
    override = overrides.get(key) or {}
    subject = override.get("subject", definition.subject).format(**placeholders)
    body = override.get("body", definition.body).format(**placeholders)
    html_kwargs = None
    if definition.headline is not None:
        html_kwargs = dict(
            headline=override.get("headline", definition.headline).format(**placeholders),
            tagline=override.get("tagline", definition.tagline).format(**placeholders),
            body_text=body,
            poster_url=poster_url,
            accent=override.get("accent", definition.accent),
        )
        if definition.cta_label is not None:
            # cta_url er altid den rigtige, faktiske URL — data, ikke
            # redigerbar ordlyd, samme princip som poster_url.
            html_kwargs["cta_url"] = settings.public_site_url
            html_kwargs["cta_label"] = override.get("cta_label", definition.cta_label).format(**placeholders)
    return MessageContent(subject=subject, body=body, html_kwargs=html_kwargs)


def _to_model(document: dict) -> Message:
    recipients = [MessageRecipient(**recipient) for recipient in document.get("recipients", [])]
    return Message(
        id=str(document["_id"]),
        subject=document["subject"],
        body=document["body"],
        sent_by=document["sent_by"],
        created_at=document["created_at"],
        recipients=recipients,
        read_count=sum(1 for recipient in recipients if recipient.read_at is not None),
        recipient_count=len(recipients),
        is_broadcast=document.get("is_broadcast", False),
    )


async def _resolve_recipients(
    db: AsyncIOMotorDatabase, payload: MessageCreate, sender_id: str
) -> list[dict]:
    """Modtagerlisten som den ser ud *nu* (Jans valg 2026-08-09).

    Et øjebliksbillede frem for en stående meddelelse: en besked om fredagens
    visning skal ikke møde en bruger der opretter sig tre måneder senere.
    Listen gemmes derfor på beskeden i stedet for at blive slået op ved hver
    visning.

    Kun aktive konti — en `pending`/`rejected`/`disabled` bruger kan ikke
    bruge appen og ville bare stå som "ulæst" for evigt. Afsenderen selv
    springes over: man skal ikke have en banner om sin egen besked.

    Feature #197 — hvert dict bærer desuden en TRANSIENT `_email`-nøgle
    (brugerens e-mail, hvis sat), brugt af `send()`s e-mail-udsendelse
    nedenfor. Den fjernes igen før `recipients` skrives til Mongo (se
    `send()`) — ellers ville en brugers e-mail på det tidspunkt beskeden
    blev sendt ligge frosset fast i hvert historisk beskeddokument for
    evigt, uafhængigt af om brugeren senere skifter eller rydder den."""
    if payload.recipient_user_id is not None:
        target = await user_repository.find_by_id(db, payload.recipient_user_id)
        if target is None:
            raise UserNotFoundError(payload.recipient_user_id)
        return [
            {
                "user_id": str(target["_id"]),
                "username": target["username"],
                "read_at": None,
                "_email": target.get("email"),
            }
        ]

    return [
        {
            "user_id": str(user["_id"]),
            "username": user["username"],
            "read_at": None,
            "_email": user.get("email"),
        }
        for user in await user_repository.list_all(db)
        if user.get("status") == UserStatus.ACTIVE.value and str(user["_id"]) != sender_id
    ]


async def _send_emails(
    recipients: list[dict], subject: str, body: str, html: str | None = None
) -> None:
    """Feature #197 — best-effort side-kanal, kaldes fra `send()` EFTER selve
    in-app-beskeden er skrevet. Rent, ulogget fravalg (ikke engang forsøgt)
    når Resend slet ikke er konfigureret — samme "unconfigured" vs. "error"-
    skel som frontendens usePlexAvailability allerede bruger. En 429 stopper
    resten af udsendelsen med det samme (CLAUDE.md regel 16 — bulk-kald mod
    en ekstern API skal ikke blive ved med at ramme en allerede rate-limitet
    tjeneste). Kaster aldrig selv ud af sig selv, men kaldes alligevel kun
    fra callere der allerede pakker `send()` i try/except (notify_wishlist_*
    nedenfor) — én ekstra sikkerhedslinje, ikke den eneste.

    Feature #204 — `html` er en valgfri, rigere version af samme besked
    (poster-billede + inspirerende tagline), sat af de admin→bruger-svar-
    funktioner nedenfor. `body` (ren tekst) sendes altid, uanset `html`."""
    if not settings.resend_api_key or not settings.email_from_address:
        return
    for recipient in recipients:
        email = recipient.get("_email")
        if not email:
            continue
        try:
            ok = await email_client.send_email(to=email, subject=subject, text=body, html=html)
            if not ok:
                logger.warning("E-mail-notifikation fejlede for %s (%r)", recipient["username"], subject)
        except EmailRateLimitedError:
            logger.warning(
                "Resend rate-limit ramt — stopper resten af e-mail-udsendelsen (besked %r)", subject
            )
            return
        except Exception:
            logger.exception("Uventet fejl ved e-mail-notifikation for %s", recipient["username"])


async def send(
    db: AsyncIOMotorDatabase,
    payload: MessageCreate,
    sender: dict,
    email_html: str | None = None,
) -> Message:
    """`email_html` (feature #204) er bevidst IKKE en del af `MessageCreate` —
    den er kun tilgængelig for interne kaldere (de admin→bruger-svar-
    funktioner nedenfor), aldrig noget en admin kan sætte via den offentlige
    "send besked"-API'en. Portal-beskeden (`payload.body`) er uændret ren
    tekst i begge tilfælde — `email_html` er udelukkende en rigere
    E-MAIL-repræsentation af samme indhold.

    Feature #217 — `send()` er det ENESTE sted en Message nogensinde
    oprettes (verificeret ved grep), så et kast her FØR noget som helst
    rører databasen eller Resend dækker automatisk EVERY notify_*-funktion
    i denne fil, uden at hver af dem selv skal tjekke `settings.test_mode`.
    Deres eksisterende `try/except: pass` sluger den tavst, ligesom enhver
    anden uventet fejl. `POST /api/messages` (admins manuelle "send besked")
    lader den derimod boble op til en registreret exception-handler (409) —
    en tydelig fejl er bedre end et stille no-op der ser ud som en succes
    for en handling admin bevidst udførte."""
    if settings.test_mode:
        raise TestModeActiveError()
    sender_id = str(sender["_id"])
    resolved = await _resolve_recipients(db, payload, sender_id)
    if not resolved:
        # Ellers ville beskeden se ud som sendt, men ligge uden modtagere —
        # typisk når man er den eneste aktive bruger i portalen.
        raise NoRecipientsError()

    # Feature #197 — `_email` er kun til e-mail-udsendelsen nedenfor, aldrig
    # persisteret på selve beskeddokumentet (se _resolve_recipients' note).
    recipients = [
        {"user_id": r["user_id"], "username": r["username"], "read_at": r["read_at"]}
        for r in resolved
    ]
    document = {
        # Allerede trimmet af MessageCreate.not_blank.
        "subject": payload.subject,
        "body": payload.body,
        "sent_by": sender["username"],
        "created_at": datetime.now(timezone.utc),
        "recipients": recipients,
        "is_broadcast": payload.recipient_user_id is None,
    }
    message = _to_model(await message_repository.insert(db, document))
    await _send_emails(resolved, message.subject, message.body, html=email_html)
    return message


def _content_wishlist_moved(
    display_title: str, is_tv: bool, poster_url: str | None, overrides: dict[str, dict]
) -> MessageContent:
    kind = "serie" if is_tv else "film"
    return _render("wishlist_moved", {"title": display_title, "kind": kind}, poster_url, overrides)


async def notify_wishlist_moved(
    db: AsyncIOMotorDatabase,
    wishlist_doc: dict,
    mover: dict,
    title: str | None,
    is_tv: bool,
) -> None:
    """Feature #141 — når et ønske flyttes fra indkøbslisten ind i biblioteket
    (dvs. er blevet købt), får den bruger der oprindeligt satte det på listen
    besked. Best-effort sidekanal i try/except, så en fejl i notifikationen
    aldrig vælter selve flytningen (CLAUDE.md regel 16). Springes over hvis
    flytteren selv er den der ønskede det — man skal ikke have besked om sin
    egen handling. Bor her (message-laget) frem for i begge medie-services, så
    logikken ikke duplikeres og kan divergere."""
    owner_username = wishlist_doc.get("registered_by")
    if not owner_username or owner_username == mover.get("username"):
        return
    owner = await user_repository.find_by_username_normalized(db, owner_username.lower())
    if owner is None:
        return
    overrides = await message_template_repository.find_all(db)
    display_title = title or wishlist_doc.get("title") or wishlist_doc.get("name") or ("serie" if is_tv else "film")
    content = _content_wishlist_moved(display_title, is_tv, wishlist_doc.get("poster_url"), overrides)
    payload = MessageCreate(
        subject=content.subject,
        body=content.body,
        recipient_user_id=str(owner["_id"]),
    )
    try:
        await send(
            db,
            payload,
            mover,
            email_html=email_templates.render_notification_email(**content.html_kwargs),
        )
    except Exception:
        pass


def _content_wishlist_approved(
    display_title: str, is_tv: bool, poster_url: str | None, overrides: dict[str, dict]
) -> MessageContent:
    kind = "serie" if is_tv else "film"
    return _render("wishlist_approved", {"title": display_title, "kind": kind}, poster_url, overrides)


async def notify_wishlist_approved(
    db: AsyncIOMotorDatabase,
    wishlist_doc: dict,
    admin: dict,
    title: str | None,
    is_tv: bool,
) -> None:
    """Feature #166 — Jan: "ved 'Godkend ønske' skal der sendes en besked til
    user som har sag den på listen". Modparten til `notify_wishlist_rejected`
    (og strukturelt en tro kopi af `notify_wishlist_moved`, med en fast
    besked frem for #165s frie admin-tekst — godkendelse har intet
    begrundelsesfelt at give videre). Samme best-effort try/except og
    "spring over hvis opretteren ikke kan slås op"-mønster (regel 16)."""
    owner_username = wishlist_doc.get("registered_by")
    if not owner_username or owner_username == admin.get("username"):
        return
    owner = await user_repository.find_by_username_normalized(db, owner_username.lower())
    if owner is None:
        return
    overrides = await message_template_repository.find_all(db)
    display_title = title or wishlist_doc.get("title") or wishlist_doc.get("name") or ("serie" if is_tv else "film")
    content = _content_wishlist_approved(display_title, is_tv, wishlist_doc.get("poster_url"), overrides)
    payload = MessageCreate(
        subject=content.subject,
        body=content.body,
        recipient_user_id=str(owner["_id"]),
    )
    try:
        await send(
            db,
            payload,
            admin,
            email_html=email_templates.render_notification_email(**content.html_kwargs),
        )
    except Exception:
        pass


def _content_wishlist_ordered(
    display_title: str, is_tv: bool, poster_url: str | None, overrides: dict[str, dict]
) -> MessageContent:
    kind = "serie" if is_tv else "film"
    return _render("wishlist_ordered", {"title": display_title, "kind": kind}, poster_url, overrides)


async def notify_wishlist_ordered(
    db: AsyncIOMotorDatabase,
    wishlist_doc: dict,
    admin: dict,
    title: str | None,
    is_tv: bool,
) -> None:
    """Feature #189 — Jan: "hvis så en adm ændre film/tv til at den er
    bestilt så skal user have besked". Tredje "status ændret"-besked ved
    siden af `notify_wishlist_approved`/`notify_wishlist_moved` — samme
    struktur, samme best-effort try/except og samme "spring over hvis
    opretteren ikke kan slås op"-mønster (CLAUDE.md regel 16). Kaldes kun ved
    selve OVERGANGEN fra ikke-bestilt til bestilt (mirroring #166's
    pending→approved-afgrænsning), ikke ved hver eneste `order_status`-skrivning
    — et skift af BESTILLINGSSTED på et allerede bestilt ønske er ikke en
    ny nyhed for brugeren."""
    owner_username = wishlist_doc.get("registered_by")
    if not owner_username or owner_username == admin.get("username"):
        return
    owner = await user_repository.find_by_username_normalized(db, owner_username.lower())
    if owner is None:
        return
    overrides = await message_template_repository.find_all(db)
    display_title = title or wishlist_doc.get("title") or wishlist_doc.get("name") or ("serie" if is_tv else "film")
    content = _content_wishlist_ordered(display_title, is_tv, wishlist_doc.get("poster_url"), overrides)
    payload = MessageCreate(
        subject=content.subject,
        body=content.body,
        recipient_user_id=str(owner["_id"]),
    )
    try:
        await send(
            db,
            payload,
            admin,
            email_html=email_templates.render_notification_email(**content.html_kwargs),
        )
    except Exception:
        pass


def _content_wishlist_rejected(
    display_title: str,
    is_tv: bool,
    poster_url: str | None,
    reason: str | None,
    overrides: dict[str, dict],
) -> MessageContent:
    kind = "serie" if is_tv else "film"
    content = _render("wishlist_rejected", {"title": display_title, "kind": kind}, poster_url, overrides)
    # `reason` er adminens egen, frie begrundelses-TEKST (feature #165) —
    # bevidst IKKE en pladsholder i selve skabelonen, men altid tilføjet
    # samme måde bagefter, uanset hvad admin har redigeret subject/body
    # til. Uændret adfærd fra før #225.
    if not reason or not reason.strip():
        return content
    new_body = f"{content.body}\n\n{reason.strip()}"
    html_kwargs = dict(content.html_kwargs, body_text=new_body) if content.html_kwargs else None
    return MessageContent(subject=content.subject, body=new_body, html_kwargs=html_kwargs)


async def notify_wishlist_rejected(
    db: AsyncIOMotorDatabase,
    wishlist_doc: dict,
    admin: dict,
    title: str | None,
    is_tv: bool,
    reason: str | None,
) -> None:
    """Feature #165 — modparten til `notify_wishlist_moved`: en admin har
    afvist (ikke godkendt) et ønske i stedet for at godkende det. Samme
    best-effort try/except og samme "spring over hvis opretteren ikke kan
    slås op"-mønster (CLAUDE.md regel 16) — en fejl her må aldrig vælte selve
    afvisningen, som allerede har slettet ønsket når denne kaldes. `reason`
    er adminens egen, valgfrie begrundelse (feature #165s "med besked til
    user") — tom/None giver en generisk besked i stedet for ingenting."""
    owner_username = wishlist_doc.get("registered_by")
    if not owner_username or owner_username == admin.get("username"):
        return
    owner = await user_repository.find_by_username_normalized(db, owner_username.lower())
    if owner is None:
        return
    overrides = await message_template_repository.find_all(db)
    display_title = title or wishlist_doc.get("title") or wishlist_doc.get("name") or ("serie" if is_tv else "film")
    content = _content_wishlist_rejected(display_title, is_tv, wishlist_doc.get("poster_url"), reason, overrides)
    payload = MessageCreate(
        subject=content.subject,
        body=content.body,
        recipient_user_id=str(owner["_id"]),
    )
    try:
        await send(
            db,
            payload,
            admin,
            email_html=email_templates.render_notification_email(**content.html_kwargs),
        )
    except Exception:
        pass


def _content_admins_new_wishlist(
    wisher_username: str, display_title: str, is_tv: bool, overrides: dict[str, dict]
) -> MessageContent:
    kind = "serie" if is_tv else "film"
    return _render(
        "admins_new_wishlist",
        {"username": wisher_username, "title": display_title, "kind": kind},
        None,
        overrides,
    )


async def notify_admins_new_wishlist(
    db: AsyncIOMotorDatabase,
    wisher: dict,
    title: str | None,
    is_tv: bool,
) -> None:
    """Feature #202 — Jan: "besked system skal kunne sende hvis user
    opretter ønsker til ... ønskeliste". Modparten til de fire
    notify_wishlist_*-funktioner ovenfor (som går admin→bruger): her går
    beskeden bruger→ALLE aktive admins, så de opdager et nyt ønske uden selv
    at skulle tjekke biblioteket først. Springer den enkelte admin over hvis
    de selv er ønskeren (ingen grund til en besked om sin egen handling)."""
    admins = await user_repository.list_active_admins(db)
    if not admins:
        return
    overrides = await message_template_repository.find_all(db)
    display_title = title or ("serie" if is_tv else "film")
    content = _content_admins_new_wishlist(wisher.get("username"), display_title, is_tv, overrides)
    for admin_doc in admins:
        if admin_doc.get("username") == wisher.get("username"):
            continue
        payload = MessageCreate(
            subject=content.subject,
            body=content.body,
            recipient_user_id=str(admin_doc["_id"]),
        )
        try:
            await send(db, payload, wisher)
        except Exception:
            pass


def _content_admins_new_screening_request(
    requester_username: str, display_title: str, is_tv: bool, overrides: dict[str, dict]
) -> MessageContent:
    kind = "serie" if is_tv else "film"
    return _render(
        "admins_new_screening_request",
        {"username": requester_username, "title": display_title, "kind": kind},
        None,
        overrides,
    )


async def notify_admins_new_screening_request(
    db: AsyncIOMotorDatabase,
    requester: dict,
    title: str | None,
    is_tv: bool,
) -> None:
    """Feature #202 — Jan: "... og forvisning". Samme bruger→admin-retning
    som notify_admins_new_wishlist ovenfor, for et nyt (eller et yderligere,
    fra en anden bruger) ønske om at se en titel i Voldby BIO."""
    admins = await user_repository.list_active_admins(db)
    if not admins:
        return
    overrides = await message_template_repository.find_all(db)
    display_title = title or ("serie" if is_tv else "film")
    content = _content_admins_new_screening_request(requester.get("username"), display_title, is_tv, overrides)
    for admin_doc in admins:
        if admin_doc.get("username") == requester.get("username"):
            continue
        payload = MessageCreate(
            subject=content.subject,
            body=content.body,
            recipient_user_id=str(admin_doc["_id"]),
        )
        try:
            await send(db, payload, requester)
        except Exception:
            pass


def _content_admins_new_poll_suggestion(
    creator_username: str, poll_title: str, overrides: dict[str, dict]
) -> MessageContent:
    return _render(
        "admins_new_poll_suggestion",
        {"username": creator_username, "poll_title": poll_title},
        None,
        overrides,
    )


async def notify_admins_new_poll_suggestion(
    db: AsyncIOMotorDatabase, creator: dict, poll_document: dict
) -> None:
    """Feature #213 (Jan: "guest kan opret en afsteming ... men det er en
    adm som skal godkende") — samme bruger→admin-retning som
    notify_admins_new_wishlist/notify_admins_new_screening_request ovenfor,
    men for et nyt afstemnings-FORSLAG der afventer godkendelse. `admin_doc`
    skal aldrig kunne være forslagsstilleren selv (kun ikke-admins opretter
    en 'pending' afstemning i første omgang, se poll_service.create_poll),
    men samme skip-guard bevares alligevel for konsistens med de øvrige
    notify_admins_new_*-funktioner."""
    admins = await user_repository.list_active_admins(db)
    if not admins:
        return
    title = poll_document.get("title") or "En ny afstemning"
    overrides = await message_template_repository.find_all(db)
    content = _content_admins_new_poll_suggestion(creator.get("username"), title, overrides)
    for admin_doc in admins:
        if admin_doc.get("username") == creator.get("username"):
            continue
        payload = MessageCreate(
            subject=content.subject,
            body=content.body,
            recipient_user_id=str(admin_doc["_id"]),
        )
        try:
            await send(db, payload, creator)
        except Exception:
            pass


def _content_admins_new_candidate_suggestion(
    suggester_username: str, display_title: str, poll_title: str, overrides: dict[str, dict]
) -> MessageContent:
    return _render(
        "admins_new_candidate_suggestion",
        {"username": suggester_username, "title": display_title, "poll_title": poll_title},
        None,
        overrides,
    )


async def notify_admins_new_candidate_suggestion(
    db: AsyncIOMotorDatabase, suggester: dict, poll_document: dict, candidate_title: str | None
) -> None:
    """Feature #218 (Jan: "andre guester skal kun indsætte ny film forslag
    til afsteming i en relateret kørende afsteming, en adm skal dog
    godkende") — samme bruger→admin-retning som
    notify_admins_new_poll_suggestion ovenfor, men for et foreslået
    KANDIDAT-tilføjelse til en allerede kørende afstemning, ikke en helt ny
    afstemning."""
    admins = await user_repository.list_active_admins(db)
    if not admins:
        return
    poll_title = poll_document.get("title") or "en afstemning"
    display_title = candidate_title or "en titel"
    overrides = await message_template_repository.find_all(db)
    content = _content_admins_new_candidate_suggestion(
        suggester.get("username"), display_title, poll_title, overrides
    )
    for admin_doc in admins:
        if admin_doc.get("username") == suggester.get("username"):
            continue
        payload = MessageCreate(
            subject=content.subject,
            body=content.body,
            recipient_user_id=str(admin_doc["_id"]),
        )
        try:
            await send(db, payload, suggester)
        except Exception:
            pass


def _content_poll_candidate_approved(
    display_title: str, poll_title: str, overrides: dict[str, dict]
) -> MessageContent:
    return _render(
        "poll_candidate_approved", {"title": display_title, "poll_title": poll_title}, None, overrides
    )


async def notify_poll_candidate_approved(
    db: AsyncIOMotorDatabase,
    suggestion: dict,
    candidate_title: str | None,
    poll_document: dict,
    admin: dict,
) -> None:
    """Feature #218 — svar til den der foreslog kandidaten, når admin
    godkender forslaget og gør den til en rigtig, stemme-bar kandidat.
    Samme "kort bekræftelse, ingen poster endnu" tone som
    notify_poll_approved ovenfor."""
    suggester_username = suggestion.get("suggested_by")
    if not suggester_username or suggester_username == admin.get("username"):
        return
    suggester = await user_repository.find_by_username_normalized(db, suggester_username.lower())
    if suggester is None:
        return

    poll_title = poll_document.get("title") or "afstemningen"
    display_title = candidate_title or "titlen"
    overrides = await message_template_repository.find_all(db)
    content = _content_poll_candidate_approved(display_title, poll_title, overrides)
    payload = MessageCreate(
        subject=content.subject,
        body=content.body,
        recipient_user_id=str(suggester["_id"]),
    )
    try:
        await send(
            db,
            payload,
            admin,
            email_html=email_templates.render_notification_email(**content.html_kwargs),
        )
    except Exception:
        pass


def _content_poll_candidate_rejected(
    display_title: str, poll_title: str, overrides: dict[str, dict]
) -> MessageContent:
    return _render(
        "poll_candidate_rejected", {"title": display_title, "poll_title": poll_title}, None, overrides
    )


async def notify_poll_candidate_rejected(
    db: AsyncIOMotorDatabase,
    suggestion: dict,
    candidate_title: str | None,
    poll_document: dict,
    admin: dict,
) -> None:
    """Feature #218 — modparten til notify_poll_candidate_approved: admin
    afviste forslaget i stedet. Samme dæmpede tone som
    notify_poll_suggestion_rejected ovenfor — det er ikke en fejl, bare et
    nej."""
    suggester_username = suggestion.get("suggested_by")
    if not suggester_username or suggester_username == admin.get("username"):
        return
    suggester = await user_repository.find_by_username_normalized(db, suggester_username.lower())
    if suggester is None:
        return

    poll_title = poll_document.get("title") or "afstemningen"
    display_title = candidate_title or "titlen"
    overrides = await message_template_repository.find_all(db)
    content = _content_poll_candidate_rejected(display_title, poll_title, overrides)
    payload = MessageCreate(
        subject=content.subject,
        body=content.body,
        recipient_user_id=str(suggester["_id"]),
    )
    try:
        await send(
            db,
            payload,
            admin,
            email_html=email_templates.render_notification_email(**content.html_kwargs),
        )
    except Exception:
        pass


def _content_screening_request_declined(
    display_title: str, poster_url: str | None, overrides: dict[str, dict]
) -> MessageContent:
    return _render("screening_request_declined", {"title": display_title}, poster_url, overrides)


async def notify_screening_request_declined(
    db: AsyncIOMotorDatabase,
    request_doc: dict,
    admin: dict,
    title: str | None,
    poster_url: str | None = None,
) -> None:
    """Feature #202 — Jan: "svar skal sendes return hvis adm lave
    forandring for de ønsker/forvisninger". Flere brugere kan stå bag samme
    forvisnings-ønske (feature #62/#85s delte requested_by-liste) — hver af
    dem får deres egen besked, samme "én send() pr. modtager"-mønster som de
    fire notify_wishlist_*-funktioner ovenfor bruger for én bruger ad
    gangen. Feature #204 — `poster_url` er valgfri, da `request_doc` (det
    rå dokument) ikke selv bærer den; kalderen (screening_service) sender
    den allerede-opslåede værdi fra den resolvede model."""
    requesters = request_doc.get("requested_by", [])
    if not requesters:
        return
    display_title = title or "titlen"
    overrides = await message_template_repository.find_all(db)
    content = _content_screening_request_declined(display_title, poster_url, overrides)
    for entry in requesters:
        username = entry.get("username")
        if not username or username == admin.get("username"):
            continue
        requester = await user_repository.find_by_username_normalized(db, username.lower())
        if requester is None:
            continue
        payload = MessageCreate(
            subject=content.subject,
            body=content.body,
            recipient_user_id=str(requester["_id"]),
        )
        try:
            await send(
                db,
                payload,
                admin,
                email_html=email_templates.render_notification_email(**content.html_kwargs),
            )
        except Exception:
            pass


def _content_screening_request_scheduled(
    display_title: str, when: str, poster_url: str | None, overrides: dict[str, dict]
) -> MessageContent:
    return _render(
        "screening_request_scheduled", {"title": display_title, "when": when}, poster_url, overrides
    )


async def notify_screening_request_scheduled(
    db: AsyncIOMotorDatabase,
    request_doc: dict,
    admin: dict,
    title: str | None,
    scheduled_at: datetime | None,
    poster_url: str | None = None,
) -> None:
    """Feature #202 — modparten til notify_screening_request_declined
    ovenfor: ønsket blev til en rigtig, planlagt visning i stedet for
    afvist. Feature #204 — se den identiske note om `poster_url` ovenfor.

    BUGS.md #97 (Jan, efter at have testet #221s "Send e-mail til
    anmodningsstiller(e)"-flueben mod sin egen anmodning: intet blev
    sendt, og intet dukkede op i Indstillinger → Beskeder) — denne
    funktion sprang tidligere altid en anmodningsstiller over hvis
    vedkommendes brugernavn matchede den planlæggende admin ("man skal
    ikke have besked om sin egen handling", samme mønster som resten af
    besked-systemet). Det var usynligt så længe planlægning ALTID
    notificerede automatisk (#202) — men #221 gjorde det til et
    EKSPLICIT flueben admin selv slår til, og har (verificeret ved grep)
    kun ét kaldested: screening_service.create_screening, netop når
    dette flueben er valgt. Selv-skip giver derfor ikke længere mening
    her — et bevidst tilvalgt "send til anmodningsstiller(e)" skal også
    virke når admin selv er (ene) anmodningsstiller, ikke stille fejle."""
    requesters = request_doc.get("requested_by", [])
    if not requesters:
        return
    display_title = title or "titlen"
    when = f" d. {scheduled_at.strftime('%d/%m/%Y kl. %H:%M')}" if scheduled_at else ""
    overrides = await message_template_repository.find_all(db)
    content = _content_screening_request_scheduled(display_title, when, poster_url, overrides)
    for entry in requesters:
        username = entry.get("username")
        if not username:
            continue
        requester = await user_repository.find_by_username_normalized(db, username.lower())
        if requester is None:
            continue
        payload = MessageCreate(
            subject=content.subject,
            body=content.body,
            recipient_user_id=str(requester["_id"]),
        )
        try:
            await send(
                db,
                payload,
                admin,
                email_html=email_templates.render_notification_email(**content.html_kwargs),
            )
        except Exception:
            pass


def _content_screening_scheduled_broadcast(
    display_title: str, when: str, poster_url: str | None, overrides: dict[str, dict]
) -> MessageContent:
    return _render(
        "screening_scheduled_broadcast", {"title": display_title, "when": when}, poster_url, overrides
    )


async def notify_screening_scheduled_broadcast(
    db: AsyncIOMotorDatabase,
    admin: dict,
    title: str | None,
    scheduled_at: datetime | None,
    poster_url: str | None = None,
) -> None:
    """Feature #221 — alternativet til notify_screening_request_scheduled
    ovenfor: admin har valgt at rundsende planlægnings-notifikationen til
    ALLE aktive brugere i stedet for kun anmodningsstiller(e). Genbruger
    `send()`s eksisterende `recipient_user_id=None`-rundsendings-gren (samme
    vej som admins manuelle "send besked"-API allerede bruger til at ramme
    alle aktive brugere, afsenderen selv undtaget) — ingen ny udsendelses-
    mekanisme. Gensidigt udelukkende med notify_screening_request_scheduled;
    screening_service.create_screening kalder ALDRIG begge for samme
    planlægning."""
    display_title = title or "titlen"
    when = f" d. {scheduled_at.strftime('%d/%m/%Y kl. %H:%M')}" if scheduled_at else ""
    overrides = await message_template_repository.find_all(db)
    content = _content_screening_scheduled_broadcast(display_title, when, poster_url, overrides)
    payload = MessageCreate(
        subject=content.subject,
        body=content.body,
        recipient_user_id=None,
    )
    try:
        await send(
            db,
            payload,
            admin,
            email_html=email_templates.render_notification_email(**content.html_kwargs),
        )
    except Exception:
        pass


def _content_library_addition_broadcast(
    display_title: str, is_tv: bool, poster_url: str | None, overrides: dict[str, dict]
) -> MessageContent:
    kind = "serie" if is_tv else "film"
    return _render(
        "library_addition_broadcast",
        {"title": display_title, "kind": kind, "site_url": settings.public_site_url},
        poster_url,
        overrides,
    )


async def notify_library_addition_broadcast(
    db: AsyncIOMotorDatabase,
    creator: dict,
    title: str | None,
    is_tv: bool,
    poster_url: str | None = None,
) -> None:
    """Feature #222 (Jan: "hvis nye film/tv bliver adderet til database så
    bliver der sendt en besked til alle at der er kommet en ny fede
    film/tv til samlingen og at man nu kan anmode om bio tid ... lave
    også et flueben ... om hvor vidt man vil sende besked til alle eller
    ikke") — valgfri broadcast til ALLE aktive brugere (samme
    `recipient_user_id=None`-mekanisme som #221s
    `notify_screening_scheduled_broadcast`) når en rigtig (ikke-ønske)
    film/serie tilføjes biblioteket, eller et ønske flyttes derind
    (`movie_service`/`tv_show_service`s `moved_to_library`-gren).

    Tilgængelig for enhver rolle der kan tilføje til biblioteket, ikke
    kun admin (Jans eksplicitte valg, til forskel fra #221s admin-only
    "send til alle") — `creator` er derfor den faktiske bruger der
    tilføjede/flyttede titlen, som `send()` også bruger som afsender
    (og dermed automatisk udelader fra selve rundsendingen).

    `cta_url` peger på selve Voldby BIO-forsiden (`settings.public_site_url`)
    — IKKE direkte på titlen selv, som Jan bekræftede ikke er muligt endnu
    ("det vil selvfølgelig være fedt hvis vi kunne linke direkte ind til
    filmmen i voldbybio portal men det kan vi ikke på nuværende
    tidspunkt")."""
    kind = "serie" if is_tv else "film"
    display_title = title or f"En ny {kind}"
    overrides = await message_template_repository.find_all(db)
    content = _content_library_addition_broadcast(display_title, is_tv, poster_url, overrides)
    payload = MessageCreate(
        subject=content.subject,
        body=content.body,
        recipient_user_id=None,
    )
    try:
        await send(
            db,
            payload,
            creator,
            email_html=email_templates.render_notification_email(**content.html_kwargs),
        )
    except Exception:
        pass


def _content_poll_closed_single(
    display_title: str, poster_url: str | None, overrides: dict[str, dict]
) -> MessageContent:
    return _render("poll_closed_single", {"title": display_title}, poster_url, overrides)


def _content_poll_closed_tie(titles: str, overrides: dict[str, dict]) -> MessageContent:
    return _render("poll_closed_tie", {"titles": titles}, None, overrides)


async def notify_poll_closed(
    db: AsyncIOMotorDatabase, poll_document: dict, poll_model: Poll, admin: dict
) -> None:
    """Feature #162 — svar til hver bruger der stemte, når admin lukker
    afstemningen. Samme "én send() pr. modtager"-mønster som de øvrige
    svar-funktioner ovenfor. Ét enkelt topscorer-resultat får en fest-tone
    med vinderens poster; et uafgjort resultat får samme rav-farve (det er
    stadig gode nyheder, bare ikke endeligt afgjort endnu) uden noget
    bestemt poster-billede."""
    voters = {vote["username"] for vote in poll_document.get("votes", [])} - {admin.get("username")}
    if not voters:
        return

    winners = [poll_model.candidates[i] for i in poll_model.winner_indices]
    overrides = await message_template_repository.find_all(db)
    if len(winners) == 1:
        winner = winners[0]
        content = _content_poll_closed_single(winner.title or "titlen", winner.poster_url, overrides)
    else:
        titles = ", ".join(w.title or "en titel" for w in winners)
        content = _content_poll_closed_tie(titles, overrides)

    for username in voters:
        voter = await user_repository.find_by_username_normalized(db, username.lower())
        if voter is None:
            continue
        payload = MessageCreate(
            subject=content.subject,
            body=content.body,
            recipient_user_id=str(voter["_id"]),
        )
        try:
            await send(
                db,
                payload,
                admin,
                email_html=email_templates.render_notification_email(**content.html_kwargs),
            )
        except Exception:
            pass


# Feature #216 (Jan: "når man sletter en afstemning så få users ikke notet
# om det, lan en besked som forklar at afstemings filmen er desvære aflyst
# af biograffens bestyrelse destående af de 7 små dværge, eller noget andet
# sjovt lave eventuelt en rotation med 5 forskeling besked typer med samme
# mening") — samme spøgefulde "Voldby Dagblad"-tone som resten af biograf-
# lore'en (feature #163/#210/#211's fiktive lokalavis-univers). Ren
# tilfældig udvælgelse pr. afsendelse, ikke en gemt round-robin-tilstand —
# simplest mulige tolkning af "en rotation", uden ny state at holde styr på.
#
# Feature #225 — bevidst UDELADT fra skabelon-systemet ovenfor (se modul-
# docstringen): en pulje af 5 faste vittigheds-varianter er strukturelt
# noget andet end én skabelon med pladsholdere, og forbliver hardkodet.
_POLL_CANCELLED_MESSAGES = [
    "Afstemningen er desværre aflyst af biografens bestyrelse, bestående af de 7 små dværge.",
    "Filmaftenen er trukket tilbage efter et lynindkaldt nødmøde i popcornmaskinens fagforening.",
    "Biografdirektøren — en talende kattekilling med gode kontakter — har underkendt afstemningen uden yderligere forklaring.",
    "Projektoren har nedlagt arbejdet i protest mod kandidatlisten, og afstemningen er derfor aflyst.",
    "Voldby BIOs hemmelige filmråd har trukket afstemningen tilbage. Ingen kommentarer til pressen.",
]


def _content_poll_cancelled(body: str) -> MessageContent:
    return MessageContent(
        subject="Afstemningen er aflyst",
        body=body,
        html_kwargs=dict(
            headline="Afstemningen er aflyst",
            tagline=body,
            body_text=body,
            poster_url=None,
            accent="muted",
        ),
    )


async def notify_poll_cancelled(db: AsyncIOMotorDatabase, poll_document: dict, admin: dict) -> None:
    """Feature #216 — svar til hver bruger der stemte, når admin sletter en
    ENDNU ÅBEN afstemning (poll_service.delete_poll kalder kun denne når
    status var 'open' — en allerede afgjort afstemning rammer stadig ingen,
    jf. delete_poll's egen docstring). Samme "én send() pr. modtager"-
    mønster som notify_poll_closed, blot med en tilfældigt valgt besked fra
    en fast pulje i stedet for ét fast budskab."""
    voters = {vote["username"] for vote in poll_document.get("votes", [])} - {admin.get("username")}
    if not voters:
        return

    content = _content_poll_cancelled(random.choice(_POLL_CANCELLED_MESSAGES))

    for username in voters:
        voter = await user_repository.find_by_username_normalized(db, username.lower())
        if voter is None:
            continue
        payload = MessageCreate(
            subject=content.subject,
            body=content.body,
            recipient_user_id=str(voter["_id"]),
        )
        try:
            await send(
                db,
                payload,
                admin,
                email_html=email_templates.render_notification_email(**content.html_kwargs),
            )
        except Exception:
            pass


def _content_poll_scheduled(
    display_title: str, when: str, poster_url: str | None, overrides: dict[str, dict]
) -> MessageContent:
    return _render("poll_scheduled", {"title": display_title, "when": when}, poster_url, overrides)


async def notify_poll_scheduled(
    db: AsyncIOMotorDatabase,
    poll_document: dict,
    winner: PollCandidateResult,
    admin: dict,
    scheduled_at: datetime | None,
) -> None:
    """Feature #162 — modparten til notify_poll_closed: den vindende titel
    er nu rent faktisk programsat (screening_service.create_screening med
    `poll_id` sat)."""
    voters = {vote["username"] for vote in poll_document.get("votes", [])} - {admin.get("username")}
    if not voters:
        return

    display_title = winner.title or "titlen"
    when = f" d. {scheduled_at.strftime('%d/%m/%Y kl. %H:%M')}" if scheduled_at else ""
    overrides = await message_template_repository.find_all(db)
    content = _content_poll_scheduled(display_title, when, winner.poster_url, overrides)

    for username in voters:
        voter = await user_repository.find_by_username_normalized(db, username.lower())
        if voter is None:
            continue
        payload = MessageCreate(
            subject=content.subject,
            body=content.body,
            recipient_user_id=str(voter["_id"]),
        )
        try:
            await send(
                db,
                payload,
                admin,
                email_html=email_templates.render_notification_email(**content.html_kwargs),
            )
        except Exception:
            pass


def _content_poll_approved(poll_title: str, overrides: dict[str, dict]) -> MessageContent:
    return _render("poll_approved", {"poll_title": poll_title}, None, overrides)


async def notify_poll_approved(db: AsyncIOMotorDatabase, poll_document: dict, admin: dict) -> None:
    """Feature #213 — svar til forslagsstilleren når admin godkender deres
    afstemnings-forslag og gør den global for alle. Ingen poster/vinder at
    vise endnu (afstemningen er lige blevet åbnet, ikke afgjort) — kun en
    kort bekræftelse."""
    creator_username = poll_document.get("created_by")
    if not creator_username or creator_username == admin.get("username"):
        return
    creator = await user_repository.find_by_username_normalized(db, creator_username.lower())
    if creator is None:
        return

    title = poll_document.get("title") or "din afstemning"
    overrides = await message_template_repository.find_all(db)
    content = _content_poll_approved(title, overrides)
    payload = MessageCreate(
        subject=content.subject,
        body=content.body,
        recipient_user_id=str(creator["_id"]),
    )
    try:
        await send(
            db,
            payload,
            admin,
            email_html=email_templates.render_notification_email(**content.html_kwargs),
        )
    except Exception:
        pass


def _content_poll_suggestion_rejected(poll_title: str, overrides: dict[str, dict]) -> MessageContent:
    return _render("poll_suggestion_rejected", {"poll_title": poll_title}, None, overrides)


async def notify_poll_suggestion_rejected(
    db: AsyncIOMotorDatabase, poll_document: dict, admin: dict
) -> None:
    """Feature #213 — modparten til notify_poll_approved: admin fjernede
    forslaget i stedet for at godkende det (poll_service.delete_poll's
    'was_pending'-gren). Samme dæmpede tone som
    notify_screening_request_declined — det er ikke en fejl, bare et nej."""
    creator_username = poll_document.get("created_by")
    if not creator_username or creator_username == admin.get("username"):
        return
    creator = await user_repository.find_by_username_normalized(db, creator_username.lower())
    if creator is None:
        return

    title = poll_document.get("title") or "dit afstemnings-forslag"
    overrides = await message_template_repository.find_all(db)
    content = _content_poll_suggestion_rejected(title, overrides)
    payload = MessageCreate(
        subject=content.subject,
        body=content.body,
        recipient_user_id=str(creator["_id"]),
    )
    try:
        await send(
            db,
            payload,
            admin,
            email_html=email_templates.render_notification_email(**content.html_kwargs),
        )
    except Exception:
        pass


async def list_sent(db: AsyncIOMotorDatabase) -> list[Message]:
    return [_to_model(document) for document in await message_repository.list_all(db)]


async def inbox(db: AsyncIOMotorDatabase, user_id: str) -> list[InboxMessage]:
    """De beskeder brugeren endnu ikke har lukket."""
    return [
        InboxMessage(
            id=str(document["_id"]),
            subject=document["subject"],
            body=document["body"],
            sent_by=document["sent_by"],
            created_at=document["created_at"],
        )
        for document in await message_repository.list_unread_for_user(db, user_id)
    ]


async def mark_read(db: AsyncIOMotorDatabase, message_id: str, user_id: str) -> None:
    """En bruger der ikke er modtager får samme svar som en besked der ikke
    findes: der er intet at markere, og hvilke beskeder der findes til andre
    er ikke hans oplysning."""
    if not await message_repository.mark_read(db, message_id, user_id):
        raise MessageNotFoundError(message_id)


async def mark_all_read(db: AsyncIOMotorDatabase, user_id: str) -> int:
    """Feature #226 — "Ryd alle" i Indstillinger → Beskeder. Intet at
    markere er ikke en fejl (samme stille no-op som #225s `reset_template`
    på en allerede-standard skabelon) — returnerer bare 0."""
    return await message_repository.mark_all_read(db, user_id)


async def delete(db: AsyncIOMotorDatabase, message_id: str) -> None:
    if not await message_repository.delete(db, message_id):
        raise MessageNotFoundError(message_id)
