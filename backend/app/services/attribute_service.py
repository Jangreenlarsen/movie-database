from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories import movie_repository, tv_show_repository


def _merge_sorted(*value_lists: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for values in value_lists:
        for value in values:
            if value not in seen:
                seen.add(value)
                merged.append(value)
    return sorted(merged, key=str.casefold)


async def list_owners(db: AsyncIOMotorDatabase) -> list[str]:
    """Owner values already in use, merged across movies *and* TV shows —
    owner/location are shared concepts between the two resources (jf.
    CLAUDE.md's projektbeskrivelse), so the same person/shelf should be
    suggested regardless of which tab the field is being filled in from."""
    movie_owners = await movie_repository.distinct_owners(db)
    tv_owners = await tv_show_repository.distinct_owners(db)
    return _merge_sorted(movie_owners, tv_owners)


async def list_locations(db: AsyncIOMotorDatabase) -> list[str]:
    movie_locations = await movie_repository.distinct_locations(db)
    tv_locations = await tv_show_repository.distinct_locations(db)
    return _merge_sorted(movie_locations, tv_locations)
