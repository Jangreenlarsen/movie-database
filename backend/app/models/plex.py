from pydantic import BaseModel


class PlexAvailability(BaseModel):
    available: bool
    play_url: str | None = None
