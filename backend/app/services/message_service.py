"""Beskeder fra admin til brugerne (feature #100)."""

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import MessageNotFoundError, NoRecipientsError, UserNotFoundError
from app.models.message import InboxMessage, Message, MessageCreate, MessageRecipient
from app.models.user import UserStatus
from app.repositories import message_repository, user_repository


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
    springes over: man skal ikke have en banner om sin egen besked."""
    if payload.recipient_user_id is not None:
        target = await user_repository.find_by_id(db, payload.recipient_user_id)
        if target is None:
            raise UserNotFoundError(payload.recipient_user_id)
        return [{"user_id": str(target["_id"]), "username": target["username"], "read_at": None}]

    return [
        {"user_id": str(user["_id"]), "username": user["username"], "read_at": None}
        for user in await user_repository.list_all(db)
        if user.get("status") == UserStatus.ACTIVE.value and str(user["_id"]) != sender_id
    ]


async def send(
    db: AsyncIOMotorDatabase, payload: MessageCreate, sender: dict
) -> Message:
    sender_id = str(sender["_id"])
    recipients = await _resolve_recipients(db, payload, sender_id)
    if not recipients:
        # Ellers ville beskeden se ud som sendt, men ligge uden modtagere —
        # typisk når man er den eneste aktive bruger i portalen.
        raise NoRecipientsError()

    document = {
        # Allerede trimmet af MessageCreate.not_blank.
        "subject": payload.subject,
        "body": payload.body,
        "sent_by": sender["username"],
        "created_at": datetime.now(timezone.utc),
        "recipients": recipients,
        "is_broadcast": payload.recipient_user_id is None,
    }
    return _to_model(await message_repository.insert(db, document))


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
