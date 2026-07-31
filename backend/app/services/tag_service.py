from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories import tag_repository


def normalize(raw: str) -> str:
    return raw.strip().lower()


async def resolve_tags(db: AsyncIOMotorDatabase, raw_tags: list[str]) -> list[str]:
    """Dedup by normalized form, preserving each tag's first-typed casing."""
    canonical_names: list[str] = []
    seen_normalized: set[str] = set()

    for raw in raw_tags:
        trimmed = raw.strip()
        if not trimmed:
            continue
        normalized = normalize(trimmed)
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)

        existing = await tag_repository.find_by_normalized(db, normalized)
        if existing:
            canonical_names.append(existing["name"])
        else:
            created = await tag_repository.insert(db, trimmed, normalized)
            canonical_names.append(created["name"])

    return canonical_names


async def list_tag_names(db: AsyncIOMotorDatabase) -> list[str]:
    tags = await tag_repository.list_all(db)
    return [tag["name"] for tag in tags]
