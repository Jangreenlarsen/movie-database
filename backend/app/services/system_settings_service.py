from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import ENV_DEFAULT_API_KEYS, settings
from app.core.errors import EmailRateLimitedError
from app.integrations import (
    discogs_client,
    ean_search_client,
    email_client,
    omdb_client,
    tmdb_client,
    upcdatabase_client,
)
from app.models.settings import (
    ApiKeyStatus,
    ApiKeyTestResult,
    PasswordPolicy,
    PasswordPolicyUpdate,
    PlexAutoImportPolicy,
    PlexAutoImportPolicyUpdate,
    ScreeningRequestPolicy,
    ScreeningRequestPolicyUpdate,
    SystemSettingsStatus,
    SystemSettingsUpdate,
    TestableApiKey,
    TestModePolicy,
    TestModePolicyUpdate,
)
from app.repositories import system_settings_repository
from app.services import anthem_service, plex_service

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
    "resend_api_key": email_client,
    # Feature #212 — anthem_service, ikke anthem_client selv: skal tjekke
    # den aktive diagnostik-session først (se anthem_service.test_connection).
    "anthem_host": anthem_service,
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

    # Feature #186 — omdøb en eksisterende override FØR den læses, ellers
    # forsvinder den stille (se migrationens egen docstring).
    await system_settings_repository.migrate_screening_request_policy_field_rename(db)

    # Feature #177 — samme sync, for visningsønske-politikkens ene felt.
    screening_policy_overrides = await system_settings_repository.get_screening_request_policy_overrides(db)
    for key, value in screening_policy_overrides.items():
        setattr(settings, key, value)

    # Feature #181 — samme sync, for auto-import-politikkens to felter.
    auto_import_overrides = await system_settings_repository.get_plex_auto_import_overrides(db)
    for key, value in auto_import_overrides.items():
        setattr(settings, key, value)

    # Feature #217 — samme sync, for test-tilstandens ene felt.
    test_mode_overrides = await system_settings_repository.get_test_mode_overrides(db)
    for key, value in test_mode_overrides.items():
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
        plex_shield_client_identifier=settings.plex_shield_client_identifier,
        anthem_host=settings.anthem_host,
        anthem_port=settings.anthem_port,
        email_from_address=settings.email_from_address,
    )


async def update_settings(
    db: AsyncIOMotorDatabase, payload: SystemSettingsUpdate
) -> SystemSettingsStatus:
    # Feature #183 — `anthem_port` er den første ikke-streng-nøgle i denne
    # generiske opdatering (alle andre er hidtil altid strenge). `.strip()`
    # ville kaste på et int, så det springes eksplicit over for alt der ikke
    # er en streng, i stedet for at antage typen som før.
    updates = {
        key: value.strip() if isinstance(value, str) else value
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


async def send_test_email(to: str) -> ApiKeyTestResult:
    """Feature #199 (Jan: "lave også en email test funktion") — en ægte
    ende-til-ende-afsendelse, adskilt fra test_connection() ovenfor: den
    bekræfter kun at NØGLEN er gyldig (og for en "sending access"-nøgle kan
    den slet ikke bekræfte mere end det, se email_client.test_connection's
    egen kommentar) — ikke at en mail rent faktisk kan afleveres."""
    if not settings.resend_api_key or not settings.email_from_address:
        return ApiKeyTestResult(
            ok=False, message="Resend-nøgle og/eller e-mail-afsenderadresse mangler"
        )
    try:
        ok = await email_client.send_email(
            to=to,
            subject="Testmail fra Film & TV-databasen",
            text=(
                "Denne mail bekræfter at jeres Resend-opsætning virker. "
                "Ingen handling nødvendig."
            ),
        )
    except EmailRateLimitedError:
        return ApiKeyTestResult(ok=False, message="Resend rate-limit ramt (429) — prøv igen om lidt")

    return ApiKeyTestResult(
        ok=ok,
        message=(
            "Testmail sendt — tjek indbakken (og evt. spam-mappen)"
            if ok
            else "Resend afviste afsendelsen — se serverens log for detaljer"
        ),
    )


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


def _screening_request_policy_from_settings() -> ScreeningRequestPolicy:
    return ScreeningRequestPolicy(require_preferred_at=settings.require_preferred_at)


async def get_screening_request_policy(db: AsyncIOMotorDatabase) -> ScreeningRequestPolicy:
    return _screening_request_policy_from_settings()


async def update_screening_request_policy(
    db: AsyncIOMotorDatabase, payload: ScreeningRequestPolicyUpdate
) -> ScreeningRequestPolicy:
    """Feature #177/#186. Samme skriv-og-synkronisér-mønster som
    `update_password_policy` ovenfor."""
    updates = payload.model_dump(exclude_unset=True)
    await system_settings_repository.apply_screening_request_policy_update(db, updates)
    for key, value in updates.items():
        setattr(settings, key, value)
    return _screening_request_policy_from_settings()


def _test_mode_policy_from_settings() -> TestModePolicy:
    return TestModePolicy(test_mode=settings.test_mode)


async def get_test_mode_policy(db: AsyncIOMotorDatabase) -> TestModePolicy:
    return _test_mode_policy_from_settings()


async def update_test_mode_policy(
    db: AsyncIOMotorDatabase, payload: TestModePolicyUpdate
) -> TestModePolicy:
    """Feature #217 (Jan: "vi skal have en funktion for adm i settings hvor
    vi kan sætte at 'test' tilstand..."). Samme skriv-og-synkronisér-mønster
    som update_screening_request_policy ovenfor — message_service.send()
    læser settings.test_mode direkte ved hvert kald, så en ændring her slår
    igennem med det samme, uden genstart."""
    updates = payload.model_dump(exclude_unset=True)
    await system_settings_repository.apply_test_mode_update(db, updates)
    for key, value in updates.items():
        setattr(settings, key, value)
    return _test_mode_policy_from_settings()


def _plex_auto_import_policy_from_settings() -> PlexAutoImportPolicy:
    return PlexAutoImportPolicy(
        plex_auto_import_enabled=settings.plex_auto_import_enabled,
        plex_auto_import_interval_minutes=settings.plex_auto_import_interval_minutes,
        plex_import_tag=settings.plex_import_tag,
    )


async def get_plex_auto_import_policy(db: AsyncIOMotorDatabase) -> PlexAutoImportPolicy:
    return _plex_auto_import_policy_from_settings()


async def update_plex_auto_import_policy(
    db: AsyncIOMotorDatabase, payload: PlexAutoImportPolicyUpdate
) -> PlexAutoImportPolicy:
    """Feature #181 (Jan: "jeg tro tilgengæld at vi skal have en automatisk
    scan af plex media server for ny film og tv serie"). Samme
    skriv-og-synkronisér-mønster som `update_screening_request_policy`
    ovenfor — `plex_service.run_auto_import_loop` læser `settings` direkte
    ved hver iteration, så en ændring her slår igennem uden genstart."""
    updates = payload.model_dump(exclude_unset=True)
    await system_settings_repository.apply_plex_auto_import_update(db, updates)
    for key, value in updates.items():
        setattr(settings, key, value)
    return _plex_auto_import_policy_from_settings()
