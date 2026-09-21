"""Feature #225 (Jan: "... så vi kan editere hvordan beskeder skal se ud i
fremtiden") — gem/nulstil af admin-tilpassede besked-skabeloner. Selve
KATALOGET/visningen bor i message_preview_service.py; dette lag er kun de
to skrivende handlinger, som begge genbruger kataloget bagefter til at
returnere den friskt genberegnede visning af den ene ændrede type."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import InvalidMessageTemplateError, MessageTemplateNotFoundError
from app.models.message import MessagePreview, MessageTemplateUpdate
from app.repositories import message_template_repository
from app.services import message_preview_service, message_service


def _validate(key: str, fields: dict) -> None:
    """Renderer hvert ændret tekst-felt mod nøglens egne eksempel-
    pladsholdere (`TEMPLATE_DEFS[key].sample`) FØR noget gemmes. Fanger en
    tastefejl i et `{pladsholder}`-navn (fx `{titel}` i stedet for
    `{title}`) med det samme, i stedet for at den første fejler stille ved
    den næste rigtige afsendelse — notify_*-funktionernes `try/except:
    pass` ville ellers sluge den som enhver anden uventet fejl (CLAUDE.md
    regel 16: rammeværkets/en enkelt fejlkildes fejl har en anden form end
    vores egne, og skal tjekkes eksplicit, ikke antages væk)."""
    definition = message_service.TEMPLATE_DEFS[key]
    for field, value in fields.items():
        if field == "accent" or value is None:
            continue
        try:
            value.format(**definition.sample)
        except (KeyError, IndexError) as exc:
            raise InvalidMessageTemplateError(field, f"ukendt pladsholder {exc}") from exc


async def update_template(
    db: AsyncIOMotorDatabase, key: str, payload: MessageTemplateUpdate
) -> MessagePreview:
    if key not in message_service.TEMPLATE_DEFS:
        raise MessageTemplateNotFoundError(key)
    fields = payload.model_dump(exclude_unset=True)
    _validate(key, fields)
    if fields:
        await message_template_repository.upsert(db, key, fields)
    previews = await message_preview_service.list_message_previews(db)
    return next(preview for preview in previews if preview.key == key)


async def reset_template(db: AsyncIOMotorDatabase, key: str) -> MessagePreview:
    """Nulstiller til kode-standarden ved at fjerne overrideet helt —
    ingen fejl hvis typen ikke var tilpasset i forvejen (et stille no-op
    er den rigtige adfærd for "nulstil" på noget der allerede er standard,
    ikke en fejlmelding for en handling der reelt lykkedes)."""
    if key not in message_service.TEMPLATE_DEFS:
        raise MessageTemplateNotFoundError(key)
    await message_template_repository.delete(db, key)
    previews = await message_preview_service.list_message_previews(db)
    return next(preview for preview in previews if preview.key == key)
