from app.integrations import discogs_client, tmdb_client, upc_client
from app.models.scan import MovieCandidate


async def lookup_by_barcode(barcode: str) -> dict:
    guessed_title = await upc_client.lookup_title(barcode)
    if not guessed_title:
        # UPCitemdb's trial tier is US-retail-centric and often misses
        # European EAN-13 movie barcodes — Discogs' community-catalogued
        # database has better international DVD/Blu-ray coverage.
        guessed_title = await discogs_client.lookup_title(barcode)
    if not guessed_title:
        return {"guessed_title": None, "candidates": []}

    raw_candidates = await tmdb_client.search_movies(guessed_title)
    candidates = [MovieCandidate(**candidate) for candidate in raw_candidates]
    return {"guessed_title": guessed_title, "candidates": candidates}
