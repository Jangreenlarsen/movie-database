from datetime import datetime

from pydantic import BaseModel, Field


class MovieCreate(BaseModel):
    title: str
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    tmdb_id: int | None = None
    barcode: str | None = None
    tags: list[str] = Field(default_factory=list)


class MovieUpdate(BaseModel):
    title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] | None = None
    cast: list[str] | None = None
    tags: list[str] | None = None


class Movie(BaseModel):
    id: str
    tmdb_id: int | None = None
    barcode: str | None = None
    title: str
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
