from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "screening_requests"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[COLLECTION].create_index([("media_kind", 1), ("movie_id", 1), ("tv_show_id", 1)])
    await db[COLLECTION].create_index("status")
    # BUGS.md #44 — `request_screening` does find-then-insert, so two users
    # requesting the same title at the same moment could both conclude "no
    # request exists yet" and each create one. Scoped to `status: "pending"`
    # via a partial filter on purpose: only ONE pending request per title may
    # exist, while any number of previously declined/scheduled ones may
    # coexist as history — a plain unique index would make declining a
    # second request for a title collide with the first declined one.
    await db[COLLECTION].create_index(
        [("media_kind", 1), ("movie_id", 1), ("tv_show_id", 1)],
        unique=True,
        partialFilterExpression={"status": "pending"},
        name="uniq_pending_request_per_title",
    )


async def find_pending_for_title(
    db: AsyncIOMotorDatabase, media_kind: str, movie_id: str | None, tv_show_id: str | None
) -> dict | None:
    return await db[COLLECTION].find_one(
        {
            "media_kind": media_kind,
            "movie_id": movie_id,
            "tv_show_id": tv_show_id,
            "status": "pending",
        }
    )


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def add_requester(db: AsyncIOMotorDatabase, request_id: str, entry: dict) -> dict | None:
    """Adds one user to `requested_by` — atomic, and a no-op (dedup) if
    that user is already on the list, via the `$ne` guard in the filter.

    Feature #85: `entry` now also carries that user's optional message and
    preferred time. The dedup is deliberately still keyed on username alone,
    so re-sending a request for a title you already wished for keeps your
    original message rather than appending a second entry for you — the UI
    has no path to it either (the button reads "✓ Ønsket" once requested)."""
    if not ObjectId.is_valid(request_id):
        return None
    await db[COLLECTION].update_one(
        {"_id": ObjectId(request_id), "requested_by.username": {"$ne": entry["username"]}},
        {
            "$push": {"requested_by": entry},
            "$set": {"updated_at": entry["requested_at"]},
        },
    )
    return await db[COLLECTION].find_one({"_id": ObjectId(request_id)})


async def find_by_id(db: AsyncIOMotorDatabase, request_id: str) -> dict | None:
    if not ObjectId.is_valid(request_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(request_id)})


async def find_all(db: AsyncIOMotorDatabase, status: str | None = None) -> list[dict]:
    filter_ = {"status": status} if status else {}
    cursor = db[COLLECTION].find(filter_).sort("created_at", -1)
    return await cursor.to_list(length=500)


async def find_pending_for_user(db: AsyncIOMotorDatabase, username: str) -> list[dict]:
    cursor = db[COLLECTION].find({"status": "pending", "requested_by.username": username})
    return await cursor.to_list(length=500)


async def delete_for_title(db: AsyncIOMotorDatabase, media_kind: str, title_id: str) -> int:
    """BUGS.md #43 — companion to `screening_repository.delete_for_title`:
    removes every request pointing at a movie/TV show being deleted, so the
    admin's pending list doesn't accumulate untitled ghost rows."""
    field = "movie_id" if media_kind == "movie" else "tv_show_id"
    result = await db[COLLECTION].delete_many({"media_kind": media_kind, field: title_id})
    return result.deleted_count


async def set_status(db: AsyncIOMotorDatabase, request_id: str, status: str, updated_at) -> dict | None:
    if not ObjectId.is_valid(request_id):
        return None
    await db[COLLECTION].update_one(
        {"_id": ObjectId(request_id)}, {"$set": {"status": status, "updated_at": updated_at}}
    )
    return await db[COLLECTION].find_one({"_id": ObjectId(request_id)})
