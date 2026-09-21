from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.message import InboxMessage, Message, MessageCreate, MessagePreview, MessageTemplateUpdate
from app.services import audit_log_service, message_preview_service, message_service, message_template_service

router = APIRouter(
    prefix="/api/messages", tags=["messages"], dependencies=[Depends(get_current_user)]
)


@router.get("/previews", response_model=list[MessagePreview], dependencies=[Depends(require_admin)])
async def list_message_previews(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Feature #223/#225 — katalog over alle besked-typer appen kan sende,
    med eksempel-data OG (for de redigerbare typer) den nuværende, evt.
    admin-tilpassede skabelon (Indstillinger → Beskeder). Kalder aldrig
    `send()` — opretter eller sender intet rigtigt. Registreret før
    `/{message_id}`-ruterne (ingen konflikt her, da ingen eksisterende
    GET-rute har et path-parameter, men samme forsigtighed som `/inbox`
    nedenfor)."""
    return await message_preview_service.list_message_previews(db)


@router.patch(
    "/templates/{key}", response_model=MessagePreview, dependencies=[Depends(require_admin)]
)
async def update_message_template(
    key: str,
    payload: MessageTemplateUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Feature #225 — gemmer en admin-tilpasning af én besked-types
    skabelon (kun de felter der rent faktisk er sendt med, se
    `MessageTemplateUpdate`). 404 for en ukendt eller ikke-redigerbar nøgle
    (fx `poll_cancelled_1`), 422 hvis et felt bruger en pladsholder der
    ikke findes for netop denne besked-type."""
    return await message_template_service.update_template(db, key, payload)


@router.delete(
    "/templates/{key}", response_model=MessagePreview, dependencies=[Depends(require_admin)]
)
async def reset_message_template(key: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    """Feature #225 — nulstiller én besked-type til kode-standarden ved at
    fjerne den gemte tilpasning. Stille no-op (ingen fejl) hvis typen
    allerede var på standarden."""
    return await message_template_service.reset_template(db, key)


@router.get("/inbox", response_model=list[InboxMessage])
async def get_inbox(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """De beskeder brugeren endnu ikke har lukket (feature #100). Åben for
    alle logget-ind brugere inkl. guests — at modtage en besked er ren
    læsning. Registreret før `/{message_id}`-ruterne."""
    return await message_service.inbox(db, str(current_user["_id"]))


@router.post("/{message_id}/read", status_code=204)
async def mark_read(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Markerer beskeden som læst for den aktuelle bruger — det er dét der
    sker når man lukker banneret. Kun ens eget eksemplar røres."""
    await message_service.mark_read(db, message_id, str(current_user["_id"]))


@router.get("", response_model=list[Message], dependencies=[Depends(require_admin)])
async def list_sent(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Sendte beskeder med læse-status pr. modtager. **Kræver admin** —
    hvem der har læst hvad, er afsenderens oplysning."""
    return await message_service.list_sent(db)


@router.post("", response_model=Message, status_code=201, dependencies=[Depends(require_admin)])
async def send_message(
    payload: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    message = await message_service.send(db, payload, current_user)
    await audit_log_service.record(
        db,
        current_user["username"],
        "message.sent",
        f"{'Rundsendt' if message.is_broadcast else 'Personlig'}: {message.subject} "
        f"({message.recipient_count} modtagere)",
    )
    return message


@router.delete("/{message_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_message(message_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    """Fjerner beskeden for alle modtagere — også dem der ikke har set den."""
    await message_service.delete(db, message_id)
