# Film- & Stregkode-API Reference

Konsulteres ved al integration med eksterne film-/stregkode-API'er (jf. CLAUDE.md regel 9). Hold denne fil opdateret med nye fund (rate-limits, quirks, fejlkoder).

---

## TMDb (The Movie Database)

- **Base URL**: `https://api.themoviedb.org/3`
- **Auth**: Bearer-token (API Read Access Token, v4-auth) i `Authorization: Bearer <token>` header. Alternativt API-nøgle som query-param (`?api_key=`) på v3-endpoints — brug Bearer-metoden, den er nyere og anbefalet.
- **Nøgle opbevares**: `backend/.env` som `TMDB_API_TOKEN`, eller (feature #36) admin-sat direkte i UI'et under Indstillinger → System-indstillinger — den overstyrer `.env` med det samme, uden genstart. Hentes gratis på https://www.themoviedb.org/settings/api (kræver konto).
- **Rate limit**: Ingen hård grænse dokumenteret pr. sekund længere (tidligere ~40 req/10s), men vær nænsom og cache resultater i MongoDB.

### Relevante endpoints
| Endpoint                          | Brug                                             |
|------------------------------------|----------------------------------------------------|
| `GET /search/movie?query=<titel>`    | Fritekst-søgning på titel → liste af kandidater      |
| `GET /movie/{id}`                    | Fuld detalje for én film (overview, genres, release_date) |
| `GET /movie/{id}/credits`            | Cast/crew                                             |
| Billeder                             | Poster-path fra søge/detalje-svar kombineres med image base URL: `https://image.tmdb.org/t/p/w500{poster_path}` |

### Felt-mapping til vores `movies`-collection
| TMDb-felt         | Vores felt      |
|--------------------|------------------|
| `id`                | `tmdb_id`        |
| `title`             | `title`          |
| `release_date`      | `year` (parses år ud) |
| `overview`          | `overview`       |
| `genre_ids` → navne | `genres`         |
| `poster_path`       | `poster_url` (præfikset med image base URL) |
| `credits.cast[0..N]`| `cast`           |
| `vote_average`      | `rating` (0-10, rundet til 1 decimal) |

> **OBS**: `vote_average` er TMDb's egen community-rating — det er **ikke** den faktiske IMDb-rating. Ægte IMDb-rating (og Rotten Tomatoes/Metacritic) kræver en separat integration mod OMDb API (omdbapi.com), som ikke er implementeret. Valgt fra (se BUGS.md/FEATURES.md #13): TMDb's rating var tilgængelig med det samme uden ny konto/nøgle.

### Fejlhåndtering
- Tomt `results[]` ved søgning → vis "ingen match, prøv en anden titel" i frontend, tilbyd manuel indtastning.
- HTTP 401 → ugyldig/manglende token, log som konfigurationsfejl (ikke bruger-fejl).
- HTTP 429 → backoff og retry (se `TECH_REFERENCE.md` for retry-strategi i `integrations/tmdb_client.py`).

---

## UPC-opslagstjeneste (stregkode → produkt/titel)

Implementeret i `backend/app/integrations/upc_client.py` mod **UPCitemdb**'s gratis trial-tier (live-verificeret) som primær kilde, med **Discogs** som fallback (se nedenfor) når UPCitemdb ikke finder et match. `scan_service.lookup_by_barcode` prøver dem i rækkefølge — begge integrationer eksponerer samme `lookup_title(barcode) -> str | None`-kontrakt, så en tredje kilde kan tilføjes samme sted uden at ændre service- eller API-laget.

### UPCitemdb
- **Base URL**: `https://api.upcitemdb.com/prod/trial/lookup`
- **Auth**: ingen nøgle krævet på trial-tier, men rate-limited pr. IP (~100/dag). Produktions-tier kræver `user_key` + `key_type` headers.
- **Request**: `GET ?upc=<stregkode>`
- **Response**: `items[]` med bl.a. `title`, `brand`, `images[]`. Titel bruges som gæt til efterfølgende TMDb-søgning — brand/model-navne på DVD-covers er ofte ikke rene filmtitler, så forvent at skulle rense/forkorte strengen (fx fjern "(DVD)", "[Blu-ray]", årstal i parentes) før TMDb-søgning.

### Fejlhåndtering
- `code: "INVALID_UPC"` eller tomt `items[]` → intet gæt, falder videre til Discogs (se nedenfor), og derefter til manuel TMDb-søgning (se `/api/movies/tmdb-search` i ARCHITECTURE.md).
- Rate-limit ramt → log som warning, returnér "intet gæt" til frontend i stedet for at fejle hele scan-flowet (UPC-opslag er et *nice-to-have* forudfyld, ikke en kritisk sti).

### Discogs (fallback, feature #30)

Implementeret i `backend/app/integrations/discogs_client.py`. Bruges kun når UPCitemdb ikke finder noget — UPCitemdb's trial-tier er stærkt USA-detail-centreret og misser ofte europæiske EAN-13 stregkoder på film; Discogs' community-katalogiserede database (oprindeligt musik, men dækker også DVD/Blu-ray/VHS-udgivelser med stregkoder) har typisk bedre international dækning. **Live-verificeret 2026-08-01** mod den rigtige API (fx `?barcode=085391773726` → traf "Don Davis - The Matrix").

- **Base URL**: `https://api.discogs.com/database/search`
- **Auth**: Valgfrit personal access token (`DISCOGS_TOKEN` i `.env`, eller admin-sat i UI'et under Indstillinger → System-indstillinger, feature #36 — oprettes på https://www.discogs.com/settings/developers) som `token=`-query-param — hæver rate-limit fra 25 til 60 req/min. Virker også helt uden token.
- **Påkrævet header**: `User-Agent` med en beskrivende værdi (Discogs afviser/rate-limiter hårdere uden) — sat til `MovieDatabaseApp/1.0`.
- **Request**: `GET ?barcode=<stregkode, kun cifre>`
- **Response**: `results[]`, hvert element har bl.a. `title` (format: `"Artist - Titel"`, hvor "Artist" for film ofte er "Various", et studienavn, eller komponisten — fjernes med `_strip_artist_prefix` før TMDb-søgning) og selve `barcode[]`-listen (til evt. fremtidig krydstjek).
- **Fejlhåndtering**: samme filosofi som UPCitemdb — enhver fejl (netværk, ikke-200, tomt `results[]`) logges og returnerer `None`, aldrig en kastet exception (nice-to-have forudfyld, ikke kritisk sti).

---

## Stregkode-formater i praksis

- DVD/Blu-ray-covers i EU/DK bruger typisk **EAN-13**. Amerikanske udgivelser bruger ofte **UPC-A** (12 cifre) — EAN-13 er et superset (UPC-A = EAN-13 med et foranstillet 0), så samme lookup-flow håndterer begge hvis stregkode-detection-biblioteket understøtter begge formater (se TECH_REFERENCE.md).
