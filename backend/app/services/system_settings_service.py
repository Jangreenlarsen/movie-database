from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import ENV_DEFAULT_API_KEYS, settings
from app.integrations import discogs_client, ean_search_client, omdb_client, tmdb_client, upcdatabase_client
from app.models.settings import (
    ApiKeyStatus,
    ApiKeyTestResult,
    PasswordPolicy,
    PasswordPolicyUpdate,
    SystemSettingsStatus,
    SystemSettingsUpdate,
    TestableApiKey,
)
from app.repositories import system_settings_repository
from app.services import plex_service

KEYS = system_settings_repository.OVERRIDABLE_KEYS

# Feature #75 — hver testbar nøgle mappet til sin integrations-klient (ikke
# funktionen selv — et modul-reference gør at .test_connection() slås op
# friskt ved hvert kald, så fx test-monkeypatching af klientens funktion
# efter modulets indlæsning stadig respekteres).
_TEST_CONNECTION_CLIENTS = {
    "tmdb_api_token": tmdb_client,
    "discogs_token": discogs_client,
    "upcdatabase_token": upcdatabase_client,
    "ean_search_api_key": ean_search_client,
    "omdb_api_key": omdb_client,
}

# Rendered as a masked ApiKeyStatus (configured/source only) in GET responses
# — every overridable key except the two plain, non-secret values below.
_PLAIN_KEYS = system_settings_repository.PLAIN_KEYS
SECRET_KEYS = tuple(key for key in KEYS if key not in _PLAIN_KEYS)


async def apply_overrides_on_startup(db: AsyncIOMotorDatabase) -> None:
    """Called once from the app lifespan, after the .env-derived `settings`
    singleton exists but before anything else reads from it — so admin-set
    overrides from a previous run take effect immediately without requiring
    the .env file itself to be edited."""
    overrides = await system_settings_repository.get_overrides(db)
    for key, value in overrides.items():
        setattr(settings, key, value)

    # Feature #174 — samme "sync fra DB ved opstart" som ovenfor, for
    # adgangskode-politikkens egne, typede felter.
    policy_overrides = await system_settings_repository.get_password_policy_overrides(db)
    for key, value in policy_overrides.items():
        setattr(settings, key, value)


async def get_status(db: AsyncIOMotorDatabase) -> SystemSettingsStatus:
    overrides = await system_settings_repository.get_overrides(db)
    statuses = {}
    for key in SECRET_KEYS:
        value = getattr(settings, key)
        if key in overrides:
            source = "custom"
        elif value:
            source = "env"
        else:
            source = "unset"
        statuses[key] = ApiKeyStatus(configured=bool(value), source=source)
    return SystemSettingsStatus(
        **statuses,
        plex_server_url=settings.plex_server_url,
        primary_barcode_source=settings.primary_barcode_source,
    )


async def update_settings(
    db: AsyncIOMotorDatabase, payload: SystemSettingsUpdate
) -> SystemSettingsStatus:
    updates = {
        key: value.strip()
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    await system_settings_repository.apply_updates(db, updates)

    for key, value in updates.items():
        # `.get(key, "")` rather than `[key]` — if a new overridable key is
        # ever added to `SystemSettingsUpdate`/`OVERRIDABLE_KEYS` without
        # also adding it to `ENV_DEFAULT_API_KEYS` in config.py, clearing its
        # override degrades to "no .env fallback" instead of a raw 500
        # (BUGS.md #30).
        setattr(settings, key, value if value != "" else ENV_DEFAULT_API_KEYS.get(key, ""))

    # Feature #88 — det cachede Plex-biblioteks-index blev hentet med de
    # *gamle* credentials. Uden denne rydning ville en admin der retter en
    # forkert URL/token stadig se det gamle (typisk tomme) resultat indtil
    # TTL'en løb ud, og med rimelighed konkludere at rettelsen ikke virkede.
    if any(key.startswith("plex_") for key in updates):
        plex_service.invalidate_cache()

    return await get_status(db)


async def test_connection(key: TestableApiKey) -> ApiKeyTestResult:
    """Feature #75 — laver et rigtigt, minimalt testkald mod den aktuelt
    aktive nøgle og rapporterer om den faktisk virker, ikke kun om den er
    gemt. Opstod af at en gemt-men-forkert nøgle (fx tastet i forkert felt,
    eller udløbet) ellers er usynlig indtil et helt scan/synk fejler i
    praksis — se BUGS.md #34/#36-tråden."""
    ok, message = await _TEST_CONNECTION_CLIENTS[key].test_connection()
    return ApiKeyTestResult(ok=ok, message=message)


def _password_policy_from_settings() -> PasswordPolicy:
    return PasswordPolicy(
        password_min_length=settings.password_min_length,
        password_require_uppercase=settings.password_require_uppercase,
        password_require_lowercase=settings.password_require_lowercase,
        password_require_digit=settings.password_require_digit,
    )


async def get_password_policy(db: AsyncIOMotorDatabase) -> PasswordPolicy:
    return _password_policy_from_settings()


async def update_password_policy(
    db: AsyncIOMotorDatabase, payload: PasswordPolicyUpdate
) -> PasswordPolicy:
    """Feature #174 (Jan: "vi skal have en password politik config del i
    setting"). Samme "skriv til DB, så synkronisér straks ind i den
    kørende `settings`-singleton"-mønster som `update_settings` ovenfor —
    ellers ville ændringen først slå igennem efter en genstart, og
    `models.user.validate_password_policy` (som læser `settings` direkte,
    ikke databasen) ville fortsætte med at håndhæve den gamle politik."""
    updates = payload.model_dump(exclude_unset=True)
    await system_settings_repository.apply_password_policy_update(db, updates)
    for key, value in updates.items():
        setattr(settings, key, value)
    return _password_policy_from_settings()
