from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.repositories import tag_repository


def normalize(raw: str) -> str:
    return raw.strip().lower()


def added_by_tag(username: str) -> str:
    """Feature #18 — auto-tag added to every new movie/TV-show's tags at
    creation time, so "who added this" is filterable via the same tag
    mechanism as everything else — regardless of whether it came from a
    barcode scan, a manual TMDb search, or pure manual entry, since all
    three funnel through the same create_movie/create_tv_show call."""
    return f"Tilføjet af {username}"


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
            try:
                created = await tag_repository.insert(db, trimmed, normalized)
                canonical_names.append(created["name"])
            except DuplicateKeyError:
                # Another concurrent request created this same brand-new tag
                # between our find and our insert — use whatever casing won.
                existing = await tag_repository.find_by_normalized(db, normalized)
                canonical_names.append(existing["name"])

    return canonical_names


async def list_tag_names(db: AsyncIOMotorDatabase) -> list[str]:
    tags = await tag_repository.list_all(db)
    return [tag["name"] for tag in tags]
