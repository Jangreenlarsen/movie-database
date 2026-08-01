from app.integrations import plex_client
from app.models.plex import PlexAvailability


async def check_availability(tmdb_id: int | None, title: str | None, year: int | None) -> PlexAvailability:
    match = await plex_client.find_movie(tmdb_id, title, year)
    if match is None:
        return PlexAvailability(available=False)
    return PlexAvailability(
        available=True,
        play_url=plex_client.build_play_url(match["rating_key"], match["machine_identifier"]),
    )
