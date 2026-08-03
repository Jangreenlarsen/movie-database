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
    restore the whole system, deliberately EXCLUDING `system_settings`
    (Jan's decision 2026-08-03): a genuinely complete dump would require
    returning the actual TMDb/UPC/Discogs/OMDb/Plex keys to the frontend,
    which CLAUDE.md regel 6 forbids outright. A restore from this backup is
    therefore not 100% complete — those keys must be re-entered manually
    afterwards on the Indstillinger page."""

    backed_up_at: datetime
    app_version: str
    movies: list[dict] = Field(default_factory=list)
    tv_shows: list[dict] = Field(default_factory=list)
    deleted_movies: list[dict] = Field(default_factory=list)
    deleted_tv_shows: list[dict] = Field(default_factory=list)
    tags: list[dict] = Field(default_factory=list)
    users: list[dict] = Field(default_factory=list)
    counters: list[dict] = Field(default_factory=list)


class SystemRestoreResult(BaseModel):
    movies_imported: int
    tv_shows_imported: int
    deleted_movies_imported: int
    deleted_tv_shows_imported: int
    tags_imported: int
    users_imported: int
    counters_imported: int
