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
