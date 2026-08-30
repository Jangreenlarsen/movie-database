import re
from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "users"

DEFAULT_SETTINGS = {
    "sort_field": None,
    "sort_direction": None,
    "visible_fields": {
        "year": True,
        "tags": True,
        "format": False,
        "audio_types": False,
        "media_type": False,
        "rating": False,
        "runtime": False,
        "genres": False,
    },
    "sort_levels": [],
    "sort_presets": [],
    "tv_visible_fields": {
        "year": True,
        "tags": True,
        "format": False,
        "audio_types": False,
        "media_type": False,
        "rating": False,
        "runtime": False,
        "genres": False,
    },
    "tv_sort_levels": [],
    "tv_sort_presets": [],
    "card_size": "medium",
    "page_size": 50,
}


async def _migrate_username_normalized(db: AsyncIOMotorDatabase) -> None:
    """Backfills `username_normalized` (lowercased, used for case-insensitive
    login/uniqueness — see BUGS.md #21: iOS Safari auto-capitalizes the
    first letter of a text input by default unless it opts out, which
    silently broke login for any username with mixed/lower case) for any
    user document created before this field existed."""
    cursor = db[COLLECTION].find({"username_normalized": {"$exists": False}})
    async for doc in cursor:
        await db[COLLECTION].update_one(
            {"_id": doc["_id"]}, {"$set": {"username_normalized": doc["username"].lower()}}
        )


async def _migrate_missing_status(db: AsyncIOMotorDatabase) -> None:
    """Backfills `status: "active"` (feature #66) for any user document
    created before the pending-approval gate existed — otherwise every
    pre-existing account would suddenly be locked out as implicitly
    "pending" the moment this feature ships."""
    await db[COLLECTION].update_many(
        {"status": {"$exists": False}}, {"$set": {"status": "active"}}
    )


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await _migrate_username_normalized(db)
    await _migrate_missing_status(db)

    # Uniqueness now lives on the normalized field (case-insensitive), not
    # the raw one — Mongo won't redefine an existing same-named index under
    # different options, so the old one is dropped first if present (same
    # migration pattern as movie_repository's serial_number sparse-index
    # switch).
    existing_indexes = await db[COLLECTION].index_information()
    if "username_1" in existing_indexes:
        await db[COLLECTION].drop_index("username_1")
    await db[COLLECTION].create_index("username_normalized", unique=True)


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_username_normalized(db: AsyncIOMotorDatabase, normalized_username: str) -> dict | None:
    return await db[COLLECTION].find_one({"username_normalized": normalized_username})


async def find_by_id(db: AsyncIOMotorDatabase, user_id: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})


async def update_settings(db: AsyncIOMotorDatabase, user_id: str, settings: dict) -> dict | None:
    """Updates only the given top-level `settings.*` keys via dotted-path
    `$set`s — atomic per-field, so concurrent requests touching different
    keys (e.g. `sort_levels` vs `sort_presets`) can never race and lose one
    another's write, unlike a read-whole-settings-then-overwrite approach."""
    if not ObjectId.is_valid(user_id):
        return None
    dotted_updates = {f"settings.{key}": value for key, value in settings.items()}
    if dotted_updates:
        await db[COLLECTION].update_one({"_id": ObjectId(user_id)}, {"$set": dotted_updates})
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})


async def count(db: AsyncIOMotorDatabase) -> int:
    return await db[COLLECTION].count_documents({})


async def count_active_admins(db: AsyncIOMotorDatabase) -> int:
    """Counts only admins who can actually log in right now (`status:
    "active"`) — the single source of truth for every last-admin lockout
    guard (role demotion, disable, delete).

    A status-blind `count_by_role("admin")` used to exist alongside this and
    was what the role-demotion guard called; it was removed in the BUGS.md
    #40 fix rather than left available, because "has the admin role" and
    "can actually administer the system" stopped being the same thing the
    moment feature #80 introduced the `disabled` status, and any future
    caller reaching for the status-blind count would silently reintroduce
    the same unrecoverable lockout."""
    return await db[COLLECTION].count_documents({"role": "admin", "status": "active"})


async def list_all(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db[COLLECTION].find().sort("created_at", 1)
    return await cursor.to_list(length=1000)


async def list_active_admins(db: AsyncIOMotorDatabase) -> list[dict]:
    """Feature #202 — bruges til at rundsende en notifikation specifikt til
    admin-rollen (nyt ønske/ny forvisnings-anmodning oprettet), i modsætning
    til message_service.send()s eksisterende `recipient_user_id=None`-gren,
    som rammer ALLE aktive brugere uanset rolle."""
    cursor = db[COLLECTION].find({"role": "admin", "status": "active"})
    return await cursor.to_list(length=1000)


async def find_all_raw(db: AsyncIOMotorDatabase) -> list[dict]:
    """Unbounded, includes `password_hash` — backs the full system backup
    (feature #61). A hash isn't the plaintext password (that's the whole
    point of hashing), so including it is standard practice for a genuine
    database backup — unlike the external API keys in `system_settings`,
    it isn't excluded (see FEATURES.md #61 for why those specifically are)."""
    return await db[COLLECTION].find({}).to_list(length=None)


async def replace_all(db: AsyncIOMotorDatabase, documents: list[dict]) -> None:
    """Wholesale replace — used only by the system restore (feature #61).
    Not transactional; see movie_repository.replace_all's docstring."""
    await db[COLLECTION].delete_many({})
    if documents:
        await db[COLLECTION].insert_many(documents)


async def set_role(db: AsyncIOMotorDatabase, user_id: str, role: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(user_id)}, {"$set": {"role": role}})
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})


async def set_status(db: AsyncIOMotorDatabase, user_id: str, status: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(user_id)}, {"$set": {"status": status}})
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})


async def set_plex_play_enabled(db: AsyncIOMotorDatabase, user_id: str, enabled: bool) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    await db[COLLECTION].update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"plex_play_enabled": enabled}}
    )
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})


async def set_email(db: AsyncIOMotorDatabase, user_id: str, email: str | None) -> dict | None:
    """Feature #197. `None` clears the field (stored as `null`, not an
    unset/missing key — consistent with how other optional profile fields
    on this collection are cleared)."""
    if not ObjectId.is_valid(user_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(user_id)}, {"$set": {"email": email}})
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})


async def find_by_email(db: AsyncIOMotorDatabase, email: str) -> dict | None:
    """Feature #205 — case-insensitive (langt de fleste brugere forventer
    at 'Navn@Foo.dk' og 'navn@foo.dk' er samme konto, og `email` har ingen
    normaliseret søster-kolonne som `username_normalized`). `email` er
    allerede `EmailStr`-valideret/afgrænset af kalderen før den når hertil,
    så et regex-opslag her er hverken injicerbart eller et reelt ReDoS-mål
    (fast, kort, forankret mønster)."""
    pattern = f"^{re.escape(email)}$"
    return await db[COLLECTION].find_one({"email": {"$regex": pattern, "$options": "i"}})


async def set_reset_token(
    db: AsyncIOMotorDatabase, user_id: str, token_hash: str, expires_at: datetime
) -> None:
    """Feature #205 — selvbetjent password-reset. Kun ÉT aktivt token pr.
    bruger ad gangen: en ny anmodning overskriver automatisk et evt.
    tidligere (ubrugt) token, som dermed holder op med at virke."""
    if not ObjectId.is_valid(user_id):
        return
    await db[COLLECTION].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"reset_token_hash": token_hash, "reset_token_expires_at": expires_at}},
    )


async def find_by_reset_token_hash(db: AsyncIOMotorDatabase, token_hash: str) -> dict | None:
    return await db[COLLECTION].find_one({"reset_token_hash": token_hash})


async def consume_reset_token(db: AsyncIOMotorDatabase, user_id: str, password_hash: str) -> None:
    """Sætter den nye adgangskode og fjerner token-felterne i samme atomiske
    skrivning — et token kan derfor aldrig genbruges til at sætte en anden
    adgangskode bagefter, uanset om noget skulle gå galt undervejs et andet
    sted i kaldskæden."""
    if not ObjectId.is_valid(user_id):
        return
    await db[COLLECTION].update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {"password_hash": password_hash, "must_change_password": False},
            "$unset": {"reset_token_hash": "", "reset_token_expires_at": ""},
        },
    )


async def set_password_hash(
    db: AsyncIOMotorDatabase, user_id: str, password_hash: str, must_change_password: bool
) -> None:
    # Feature #172 — caller states the flag explicitly (no default) so
    # neither call site can silently forget it: an admin reset sets it
    # True, a self-service change (voluntary or the forced one this
    # triggers) clears it back to False.
    await db[COLLECTION].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password_hash": password_hash, "must_change_password": must_change_password}},
    )


async def delete(db: AsyncIOMotorDatabase, user_id: str) -> bool:
    """Feature #80 — a genuine hard delete, not a soft-delete/archive like
    movies/TV-shows: `registered_by`/`owner`/audit-log entries all store the
    username as a plain string (not a reference to this document), so
    removing the account leaves that history intact rather than orphaning
    anything. Returns whether a document was actually removed."""
    if not ObjectId.is_valid(user_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count > 0
