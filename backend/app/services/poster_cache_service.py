from motor.motor_asyncio import AsyncIOMotorDatabase

from app.integrations import tmdb_client
from app.repositories import poster_cache_repository

# Feature #153 — kun de størrelser frontend rent faktisk beder om
# (posterUrl.js's cardPosterSize) cachess; forhindrer at en vilkårlig
# sti-parameter kan bruges til at spamme TMDb-kald med ugyldige størrelser.
ALLOWED_SIZES = {"w185", "w342", "w500"}


async def get_or_fetch(db: AsyncIOMotorDatabase, size: str, path: str) -> tuple[bytes, str] | None:
    """Permanent poster-cache: første forespørgsel efter et givent
    (size, path)-par henter billedet fra TMDb's CDN og gemmer det i
    MongoDB; enhver efterfølgende forespørgsel serveres udelukkende fra
    databasen, uden nogen forbindelse til TMDb. Løser at hele appen ellers
    mistede postere så snart serveren ikke selv havde internetadgang,
    selvom resten af appen (kun den lokale MongoDB) virkede fint."""
    if size not in ALLOWED_SIZES:
        return None

    cached = await poster_cache_repository.find_one(db, size, path)
    if cached is not None:
        return bytes(cached["data"]), cached["content_type"]

    fetched = await tmdb_client.fetch_poster_image(size, path)
    if fetched is None:
        return None
    data, content_type = fetched
    document = await poster_cache_repository.insert(db, size, path, content_type, data)
    return bytes(document["data"]), document["content_type"]
