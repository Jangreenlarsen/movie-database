from datetime import datetime

from pydantic import BaseModel, Field


class LibraryExport(BaseModel):
    """Feature #60 — a complete, portable snapshot of the film/TV library
    (not the whole system; see SystemBackup for that). Movie/TV entries are
    raw stored documents run through `mongo_json.to_json_safe`, not the
    API-facing Movie/TvShow models — this preserves every stored field
    exactly, including ones the read models don't expose."""

    exported_at: datetime
    app_version: str
    movies: list[dict] = Field(default_factory=list)
    tv_shows: list[dict] = Field(default_factory=list)


class LibraryImportResult(BaseModel):
    movies_imported: int
    tv_shows_imported: int


class SystemBackup(BaseModel):
    """Feature #61 — a full low-level dump of every collection needed to
    restore the whole system. `system_settings` (Jan's decision 2026-08-03)
    is deliberately NOT dumped wholesale: a genuinely complete dump would
    require returning the actual TMDb/UPC/Discogs/OMDb/Plex keys to the
    frontend, which CLAUDE.md regel 6 forbids outright — those six stay
    excluded and must be re-entered manually on the Indstillinger page after
    a restore.

    CLAUDE.md regel 20 — every collection a feature adds must be checked
    into this dump as part of that same feature. screenings/screening_
    requests/seat_reservations/messages/audit_log/visits were added
    retroactively (BUGS.md #65): the collections existed and were reachable
    through the API, but a system backup silently omitted them, so a
    restore quietly lost Voldby BIO's whole program and reservation state.

    2026-08-15 backup/restore sync audit (Jan: "de skal med") — the blanket
    `system_settings` exclusion above was itself catching two fields that
    aren't secrets at all: `plex_server_url`/`primary_barcode_source`
    (system_settings_repository.PLAIN_KEYS) are already returned with their
    real value by GET /api/settings/system, so excluding the whole
    collection lost them for no privacy reason — just two settings an admin
    had to retype after a restore. `system_settings_plain` fixes that
    narrowly, without touching the six-secret exclusion above.

    2026-08-17, feature #174 — the new password-policy fields (min length,
    require upper/lowercase/digit) live in the same `system_settings`
    document but are checked into the backup from day one via
    `password_policy`, rather than being retroactively discovered missing
    the way `system_settings_plain` was (regel 20 applied proactively this
    time). Feature #177 adds `screening_request_policy` the same way,
    same day, same reasoning."""

    backed_up_at: datetime
    app_version: str
    movies: list[dict] = Field(default_factory=list)
    tv_shows: list[dict] = Field(default_factory=list)
    deleted_movies: list[dict] = Field(default_factory=list)
    deleted_tv_shows: list[dict] = Field(default_factory=list)
    tags: list[dict] = Field(default_factory=list)
    users: list[dict] = Field(default_factory=list)
    counters: list[dict] = Field(default_factory=list)
    screenings: list[dict] = Field(default_factory=list)
    screening_requests: list[dict] = Field(default_factory=list)
    # Feature #162 — samme regel-20-begrundelse som screenings/
    # screening_requests: kandidater refererer movie_id/tv_show_id.
    polls: list[dict] = Field(default_factory=list)
    seat_reservations: list[dict] = Field(default_factory=list)
    # Feature #228 — køen til den samlede opdatering (regel 20 anvendt fra
    # dag ét). Tom liste for en backup taget før feature #228.
    pending_announcements: list[dict] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)
    audit_log: list[dict] = Field(default_factory=list)
    visits: list[dict] = Field(default_factory=list)
    # Feature #153 — cachede TMDb-poster-billeder (rå bytes, base64 via
    # mongo_json's "$binary"-nøgle). Rent teknisk genskabbar fra TMDb, men
    # regel 20 kræver den med alligevel — uden den ville en gendannelse på en
    # frisk installation kræve internet igen for hver eneste poster, indtil
    # nogen tilfældigvis besøger hver film/serie én gang til.
    poster_cache: list[dict] = Field(default_factory=list)
    # Kun system_settings_repository.PLAIN_KEYS (ikke-hemmelige nøgler) —
    # "" betyder eksplicit "ingen override" (samme konvention som
    # apply_updates), ikke "feltet blev ikke taget med".
    system_settings_plain: dict = Field(default_factory=dict)
    # Feature #174 — adgangskode-politikkens fire felter er slet ikke
    # hemmelige (bare tal/booleans), så de tages med råt, uden PLAIN_KEYS'
    # "" = ingen override-nuance ovenfor: en politik har altid en reel
    # værdi (koden har sine egne standarder), aldrig et "unset"-koncept.
    password_policy: dict = Field(default_factory=dict)
    # Feature #177 — samme rå, ingen-"unset"-håndtering som password_policy
    # ovenfor, blot det ene felt.
    screening_request_policy: dict = Field(default_factory=dict)
    # Feature #225 — admin-tilpassede besked-skabeloner (regel 20 anvendt
    # proaktivt, som #174/#177 ovenfor): kun de besked-typer der rent
    # faktisk er tilpasset har et dokument; uden denne ville en admins
    # tilpassede ordlyd stille forsvinde ved en gendannelse.
    message_templates: list[dict] = Field(default_factory=list)


class SystemRestoreResult(BaseModel):
    movies_imported: int
    tv_shows_imported: int
    deleted_movies_imported: int
    deleted_tv_shows_imported: int
    tags_imported: int
    users_imported: int
    counters_imported: int
    screenings_imported: int
    screening_requests_imported: int
    polls_imported: int
    seat_reservations_imported: int
    # Feature #228.
    pending_announcements_imported: int
    messages_imported: int
    # Merged insert-only, not wholesale-replaced (system_backup_service.
    # _merge_raw_collection) — this is how many entries were actually new,
    # not the backup's total audit_log count.
    audit_log_imported: int
    visits_imported: int
    poster_cache_imported: int
    # 0, 1 or 2 — how many of PLAIN_KEYS had a real (non-"") value restored.
    system_settings_plain_restored: int
    # Feature #174 — always true once a backup is successfully restored (the
    # policy always has all four fields; there's no partial/"unset" case to
    # count, unlike system_settings_plain_restored above).
    password_policy_restored: bool
    # Feature #177 — samme begrundelse som password_policy_restored ovenfor.
    screening_request_policy_restored: bool
    # Feature #225 — se den identiske note ved SystemBackup.message_templates.
    message_templates_imported: int


class DatabaseResetConfirm(BaseModel):
    """Feature #67 — a reset is more irreversible than a restore (a restore
    at least still has *some* data behind it), so confirmation is the
    admin's actual password, not just a typed phrase like #60/#61's
    restore flows."""

    current_password: str


class DatabaseResetResult(BaseModel):
    movies_removed: int
    tv_shows_removed: int
    deleted_movies_removed: int
    deleted_tv_shows_removed: int
    tags_removed: int
    counters_removed: int
    screenings_removed: int
    screening_requests_removed: int
    polls_removed: int
    seat_reservations_removed: int
    # Feature #228.
    pending_announcements_removed: int


class MediaTypeCounts(BaseModel):
    """Feature #94 — optaelling for een ressource."""

    total: int
    physical: int
    digital: int
    # Poster fra foer medietype blev paakraevet (feature #92) — vises kun hvis
    # der faktisk er nogen, saa tallet ikke forvirrer i et rent bibliotek.
    unclassified: int
    wishlist: int


class LibraryCounts(BaseModel):
    """Det samlede overblik i app-hovedet: hvor meget staar der egentlig i
    biblioteket. Film og TV-serier holdes adskilt, jf. CLAUDE.md's princip om
    to bevidst adskilte ressourcer."""

    movies: MediaTypeCounts
    tv_shows: MediaTypeCounts
