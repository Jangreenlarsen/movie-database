"""Beskeder fra admin til brugerne (feature #100)."""

import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.errors import EmailRateLimitedError, MessageNotFoundError, NoRecipientsError, UserNotFoundError
from app.integrations import email_client
from app.models.message import InboxMessage, Message, MessageCreate, MessageRecipient
from app.models.user import UserStatus
from app.repositories import message_repository, user_repository

logger = logging.getLogger("moviedb")


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


async def _send_emails(recipients: list[dict], subject: str, body: str) -> None:
    """Feature #197 — best-effort side-kanal, kaldes fra `send()` EFTER selve
    in-app-beskeden er skrevet. Rent, ulogget fravalg (ikke engang forsøgt)
    når Resend slet ikke er konfigureret — samme "unconfigured" vs. "error"-
    skel som frontendens usePlexAvailability allerede bruger. En 429 stopper
    resten af udsendelsen med det samme (CLAUDE.md regel 16 — bulk-kald mod
    en ekstern API skal ikke blive ved med at ramme en allerede rate-limitet
    tjeneste). Kaster aldrig selv ud af sig selv, men kaldes alligevel kun
    fra callere der allerede pakker `send()` i try/except (notify_wishlist_*
    nedenfor) — én ekstra sikkerhedslinje, ikke den eneste."""
    if not settings.resend_api_key or not settings.email_from_address:
        return
    for recipient in recipients:
        email = recipient.get("_email")
        if not email:
            continue
        try:
            ok = await email_client.send_email(to=email, subject=subject, text=body)
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
    db: AsyncIOMotorDatabase, payload: MessageCreate, sender: dict
) -> Message:
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
    await _send_emails(resolved, message.subject, message.body)
    return message


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
    kind = "serie" if is_tv else "film"
    display_title = title or wishlist_doc.get("title") or wishlist_doc.get("name") or kind
    payload = MessageCreate(
        subject=f"Din ønskede {kind} er nu i biblioteket",
        body=(
            f'Den {kind} du satte på indkøbslisten — "{display_title}" — er nu købt '
            "og lagt i biblioteket. 🎬"
        ),
        recipient_user_id=str(owner["_id"]),
    )
    try:
        await send(db, payload, mover)
    except Exception:
        pass


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
    kind = "serie" if is_tv else "film"
    display_title = title or wishlist_doc.get("title") or wishlist_doc.get("name") or kind
    payload = MessageCreate(
        subject=f'Dit ønske "{display_title}" er godkendt',
        body=(
            f'Den {kind} du ønskede — "{display_title}" — er nu godkendt og '
            "står på indkøbslisten. 🎬"
        ),
        recipient_user_id=str(owner["_id"]),
    )
    try:
        await send(db, payload, admin)
    except Exception:
        pass


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
    kind = "serie" if is_tv else "film"
    display_title = title or wishlist_doc.get("title") or wishlist_doc.get("name") or kind
    payload = MessageCreate(
        subject=f'Dit ønske "{display_title}" er bestilt',
        body=f'Den {kind} du ønskede — "{display_title}" — er nu bestilt. 🎬',
        recipient_user_id=str(owner["_id"]),
    )
    try:
        await send(db, payload, admin)
    except Exception:
        pass


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
    kind = "serie" if is_tv else "film"
    display_title = title or wishlist_doc.get("title") or wishlist_doc.get("name") or kind
    # "Den {kind}" (ikke en bøjet form af selve ordet) — samme knep som
    # notify_wishlist_moved bruger, så "film" ikke skal bøjes anderledes end
    # "serie" ("filmen" vs. "serien" ville kræve to forskellige suffikser).
    default_line = f'Den {kind} du ønskede — "{display_title}" — er desværre ikke blevet godkendt.'
    body = f"{default_line}\n\n{reason.strip()}" if reason and reason.strip() else default_line
    payload = MessageCreate(
        subject=f'Dit ønske "{display_title}" blev ikke godkendt',
        body=body,
        recipient_user_id=str(owner["_id"]),
    )
    try:
        await send(db, payload, admin)
    except Exception:
        pass


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
    kind = "serie" if is_tv else "film"
    display_title = title or kind
    for admin_doc in admins:
        if admin_doc.get("username") == wisher.get("username"):
            continue
        payload = MessageCreate(
            subject="Nyt ønske på indkøbslisten",
            body=f'{wisher.get("username")} har tilføjet "{display_title}" ({kind}) til ønskelisten.',
            recipient_user_id=str(admin_doc["_id"]),
        )
        try:
            await send(db, payload, wisher)
        except Exception:
            pass


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
    kind = "serie" if is_tv else "film"
    display_title = title or kind
    for admin_doc in admins:
        if admin_doc.get("username") == requester.get("username"):
            continue
        payload = MessageCreate(
            subject="Nyt ønske om visning i Voldby BIO",
            body=f'{requester.get("username")} ønsker at se "{display_title}" ({kind}) i Voldby BIO.',
            recipient_user_id=str(admin_doc["_id"]),
        )
        try:
            await send(db, payload, requester)
        except Exception:
            pass


async def notify_screening_request_declined(
    db: AsyncIOMotorDatabase,
    request_doc: dict,
    admin: dict,
    title: str | None,
) -> None:
    """Feature #202 — Jan: "svar skal sendes return hvis adm lave
    forandring for de ønsker/forvisninger". Flere brugere kan stå bag samme
    forvisnings-ønske (feature #62/#85s delte requested_by-liste) — hver af
    dem får deres egen besked, samme "én send() pr. modtager"-mønster som de
    fire notify_wishlist_*-funktioner ovenfor bruger for én bruger ad
    gangen."""
    requesters = request_doc.get("requested_by", [])
    if not requesters:
        return
    display_title = title or "titlen"
    for entry in requesters:
        username = entry.get("username")
        if not username or username == admin.get("username"):
            continue
        requester = await user_repository.find_by_username_normalized(db, username.lower())
        if requester is None:
            continue
        payload = MessageCreate(
            subject=f'Dit ønske om at se "{display_title}" blev afvist',
            body=f'Dit ønske om at se "{display_title}" i Voldby BIO er desværre ikke blevet til noget.',
            recipient_user_id=str(requester["_id"]),
        )
        try:
            await send(db, payload, admin)
        except Exception:
            pass


async def notify_screening_request_scheduled(
    db: AsyncIOMotorDatabase,
    request_doc: dict,
    admin: dict,
    title: str | None,
    scheduled_at: datetime | None,
) -> None:
    """Feature #202 — modparten til notify_screening_request_declined
    ovenfor: ønsket blev til en rigtig, planlagt visning i stedet for
    afvist."""
    requesters = request_doc.get("requested_by", [])
    if not requesters:
        return
    display_title = title or "titlen"
    when = f" d. {scheduled_at.strftime('%d/%m/%Y kl. %H:%M')}" if scheduled_at else ""
    for entry in requesters:
        username = entry.get("username")
        if not username or username == admin.get("username"):
            continue
        requester = await user_repository.find_by_username_normalized(db, username.lower())
        if requester is None:
            continue
        payload = MessageCreate(
            subject=f'Din ønskede visning "{display_title}" er planlagt!',
            body=f'"{display_title}" er nu planlagt til visning i Voldby BIO{when}. 🎬',
            recipient_user_id=str(requester["_id"]),
        )
        try:
            await send(db, payload, admin)
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


async def delete(db: AsyncIOMotorDatabase, message_id: str) -> None:
    if not await message_repository.delete(db, message_id):
        raise MessageNotFoundError(message_id)
