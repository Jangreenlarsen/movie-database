# Arkitektur

Se [CLAUDE.md](CLAUDE.md) regel 5 og 8 — denne fil er den bindende reference for lag-ansvar og REST-kontrakten.

---

## Lag-ansvar

| Lag              | Placering                        | Ansvar                                                                 | Må IKKE                                      |
|-------------------|-----------------------------------|-------------------------------------------------------------------------|-----------------------------------------------|
| Frontend          | `frontend/src/`                   | UI, kamera-adgang, stregkode-detection, kalder backend REST API         | Kalde MongoDB, TMDb eller UPC-tjeneste direkte |
| API-lag           | `backend/app/api/`                 | HTTP-routing, request/response-validering (Pydantic), auth (hvis tilføjet senere) | Indeholde forretningslogik                    |
| Service-lag       | `backend/app/services/`            | Forretningslogik: matching, tag-normalisering, orkestrering af scan-flow | Tale direkte med MongoDB-driveren eller HTTP-libs |
| Repository-lag    | `backend/app/repositories/`        | MongoDB-adgang (Motor), queries, indexes                                | Kende til HTTP eller eksterne API'er           |
| Integrations-lag  | `backend/app/integrations/`        | HTTP-kald til TMDb og UPC-tjeneste, API-nøgle-håndtering, rate-limit/retry | Have forretningslogik ud over data-mapping     |

Kaldsretning er altid: **Frontend → API → Service → (Repository \| Integrations)**. Aldrig omvendt, og aldrig spring over et lag.

---

## REST API-kontrakt

Alle endpoints er ressource-orienterede og ligger under `/api`. Denne tabel opdateres *før* et nyt endpoint implementeres (jf. CLAUDE.md regel 8).

| Metode | Endpoint                     | Beskrivelse                                             | Status  |
|--------|-------------------------------|-----------------------------------------------------------|---------|
| GET    | `/api/movies`                  | Liste film, understøtter `?q=` (fritekst, MongoDB `$text`), `?tags=` (kommasepareret, case-insensitiv `$all`-match), `?format=` og `?audio_types=` (kommasepareret, `$in`-match) | done |
| GET    | `/api/movies/{id}`             | Hent én film med fuld metadata                             | done |
| POST   | `/api/movies`                  | Opret film (manuelt eller efter scan-bekræftelse). 409 ved dublet `barcode`. Tildeler automatisk fortløbende `serial_number`. | done |
| PATCH  | `/api/movies/{id}`             | Opdater film (tags, format, audio_types, noter — IKKE `serial_number`, den er immutable) | done |
| DELETE | `/api/movies/{id}`             | Slet film                                                     | done |
| GET    | `/api/movies/attribute-options`| Liste gyldige `format`- og `audio_types`-værdier (enum-kilde til frontend-dropdowns). Registreret før `/{movie_id}`. | done |
| GET    | `/api/tags`                    | Liste alle tags (til autocomplete)                            | done |
| POST   | `/api/scan/lookup`             | Input: scannet UPC/EAN. Output: UPC-gæt + TMDb-kandidater. 502 hvis TMDb er utilgængelig/token mangler. | done |
| GET    | `/api/movies/tmdb-search`      | Direkte TMDb-titel-søgning (fallback når scan ikke matcher). Registreret før `/{movie_id}`. | done |
| GET    | `/api/health`                  | Health check (backend + MongoDB-forbindelse)                    | done |

> `POST /api/movies` accepterer nu enten `tmdb_id` (backend henter fuld metadata fra TMDb server-side) eller en manuel `title` (fuldt manuel oprettelse uden TMDb). Se `MovieCreate` i `backend/app/models/movie.py`.

> **Strukturerede attributter**: `format` (étvalg, fast enum: VHS/DVD/Blu-ray/4K Ultra HD/Digital) og `audio_types` (flervalg, fast enum: Stereo/Mono/Dolby Digital/Dolby Digital 5.1/Dolby Digital 7.1/DTS/DTS-HD Master Audio/Dolby Atmos/Dolby TrueHD) — se `MovieFormat`/`AudioType` i `backend/app/models/movie.py`. I modsætning til tags er disse IKKE fritekst; ugyldige værdier afvises med 422. `serial_number` er et fortløbende heltal tildelt server-side ved oprettelse (atomisk `$inc` på en `counters`-collection, se `movie_repository.next_serial_number`) — kan ikke sættes eller ændres af klienten.

> Der er ikke et separat `/api/search`-endpoint — kombineret fritekst+tag-søgning dækkes af `/api/movies?q=&tags=` (se ovenfor), for at undgå to endpoints med overlappende ansvar.

---

## Data-flow: scan-til-gem

```
1. Frontend: bruger scanner cover → stregkode (UPC/EAN) læses client-side
2. Frontend → POST /api/scan/lookup { barcode }
3. Backend (scan_service):
   a. integrations/upc_client → slår barcode op → titel-gæt (eller ingen match)
   b. integrations/tmdb_client → søger TMDb på titel-gæt → kandidat-liste
   c. returnerer kandidater (poster, år, tmdb_id) til frontend
4. Frontend: bruger vælger korrekt kandidat (eller søger manuelt via /api/movies/tmdb-search)
5. Frontend → POST /api/movies { tmdb_id, barcode, tags[] }
6. Backend (movie_service): henter fuld TMDb-metadata, normaliserer tags,
   gemmer dokument via repositories/movie_repository → MongoDB
```

---

## MongoDB collections (overblik)

| Collection | Nøgle-felter                                                     | Indexes                                  |
|------------|-----------------------------------------------------------------------|--------------------------------------------|
| `movies`   | `serial_number` (fortløbende, immutable), `tmdb_id`, `barcode` (**udelades helt af dokumentet når ikke angivet — se BUGS.md #1**), `title`, `tags[]` (display-case), `tags_normalized[]` (lowercase, bruges til filtrering), `format` (enum-streng), `audio_types[]` (enum-strenge) | text-index på `title`+`overview`, index på `tags_normalized`, `format`, `audio_types`, unique sparse index på `barcode`, unique index på `serial_number` |
| `tags`     | `name` (første-typede casing), `normalized` (lowercase, unik nøgle)     | unique index på `normalized`                |
| `counters` | `_id` (fast nøgle `"movie_serial"`), `value` (seneste tildelte serienummer) | — (kun ét dokument, atomisk `$inc`)         |

Detaljeret skema og indexes: se [TECH_REFERENCE.md](TECH_REFERENCE.md).
