# Changelog

Nyeste øverst. Hver entry tagges med `[version build NNNN]` (jf. CLAUDE.md regel 4).

## [0.5.0 build 0005] — 2026-07-31 — Moderne redesign + film-detaljer/redigering

- `frontend/src/index.css`: nyt design-system — CSS custom properties for farver/radius/skygge, lys + mørk tilstand (inkl. `data-theme`-override), fjernet Vite-template-resterne (centreret `#root`, 56px-overskrifter, lilla accent).
- `frontend/src/App.jsx` + `App.css`: nyt app-shell med sticky header, brand-mærke, segmenteret fane-navigation. Delte UI-primitiver (`.btn`, `.card`, `.chip`, `.banner`) tilføjet til genbrug på tværs af sider.
- Ny genanvendelig komponent `frontend/src/components/Chip.jsx` til til/fra-valg (bruges til tag-/format-/lyd-type-filtre og -valg begge steder).
- `pages/Library.jsx` (+ `Library.css`) genskrevet: poster-grid med serienummer- og format-badges, filter-panel med chips for tags/format/lyd-type (hentet fra `/api/tags` og `/api/movies/attribute-options`), loading-skeletons, tomme/fejl-tilstande.
- **Ny**: klik på et filmkort åbner en detalje-modal (poster, plot, cast, genre) med redigering af tags/format/audio_types samt slet-knap — implementerer FEATURES.md #7 og #8 mod de eksisterende `PATCH`/`DELETE`-endpoints.
- `pages/ScanMovie.jsx` (+ `ScanMovie.css`) genskrevet: kandidat-valg er nu adskilt fra gem-trinnet — efter valg af TMDb-kandidat vises et review-skema hvor tags/format/lyd-type vælges *før* filmen gemmes (tidligere gemte "Bekræft" med det samme, uden mulighed for attributter).
- `scanner/BarcodeScanner.jsx` (+ `BarcodeScanner.css`): visuel "viewfinder" med hjørne-markører og scan-linje-animation i stedet for et nøgent `<video>`-element.
- `api/client.js`: `listMovies` understøtter nu `format`/`audioTypes`; ny `attributeOptions()`.
- Ingen backend-ændringer i denne commit — kun frontend. Build verificeret (`npm run build`), dev-server smoke-testet.

## [0.4.0 build 0004] — 2026-07-31 — Strukturerede attributter + auto-serienummer

- `backend/app/models/movie.py`: nye enums `MovieFormat` (VHS/DVD/Blu-ray/4K Ultra HD/Digital, étvalg) og `AudioType` (Stereo/Mono/Dolby Digital/Dolby Digital 5.1/Dolby Digital 7.1/DTS/DTS-HD Master Audio/Dolby Atmos/Dolby TrueHD, flervalg). Ugyldige værdier afvises med 422. `Movie` har nu `serial_number` (immutable, server-tildelt).
- `backend/app/repositories/movie_repository.py`: `next_serial_number()` — atomisk `$inc` mod en ny `counters`-collection (race-sikkert ved samtidige oprettelser). Nye indexes på `format`, `audio_types`, unique index på `serial_number`.
- `backend/app/services/movie_service.py`: `create_movie` tildeler serienummer og gemmer `format`/`audio_types`; `list_movies` og `update_movie` understøtter dem.
- `GET /api/movies` har nye query-params `?format=` og `?audio_types=` (kommasepareret, `$in`-match — "mindst én af"). Nyt endpoint `GET /api/movies/attribute-options` leverer de gyldige værdier til frontend-dropdowns.
- **Bugfix (se BUGS.md #1)**: film oprettet uden stregkode fik eksplicit `barcode: null` gemt i dokumentet, hvilket kolliderede med den sparse unique-index efter den *anden* stregkodeløse film (sparse index ekskluderer kun manglende felter, ikke `null`-værdier). Opdaget live mod ægte MongoDB — mongomock-testsuiten fangede det ikke. Rettet ved at udelade `barcode`-nøglen helt når den ikke er angivet; eksisterende data migreret.
- Pytest-suite udvidet med serienummer-, attribut-validering-, attribut-filtrering- og barcode-regressionstests. 22/22 grønne.
- `ARCHITECTURE.md` opdateret: endpoint-kontrakt, MongoDB-skema (`counters`-collection, nye indexes).

## [0.3.0 build 0003] — 2026-07-31 — Stregkode-scan → UPC-opslag → TMDb-match

- Tilføjet `backend/app/integrations/tmdb_client.py`: `search_movies()` (letvægts-kandidater til søgning) og `get_movie_details()` (fuld metadata + credits ved gem). Kaster `TmdbNotFoundError` (→ 404) og `TmdbUnavailableError` (→ 502, bl.a. ved manglende `TMDB_API_TOKEN`).
- Tilføjet `backend/app/integrations/upc_client.py`: UPCitemdb-opslag (trial-tier, ingen nøgle krævet). Fejler aldrig hardt — returnerer `None` ved intet match/timeout, jf. "nice-to-have, ikke kritisk sti" i MOVIE_API_REFERENCE.md. Renser producent-suffixe som "(DVD)"/"[Blu-ray]" fra titelgættet.
- Tilføjet `backend/app/services/scan_service.py`: orkestrerer UPC-opslag → TMDb-søgning.
- `backend/app/models/movie.py`: `MovieCreate` accepterer nu enten `tmdb_id` (backend henter fuld metadata server-side) eller en manuel `title` — valideret med en model-validator.
- `backend/app/services/movie_service.py`: `create_movie` henter fuld TMDb-metadata (titel, år, poster, plot, genrer, cast) når `tmdb_id` er angivet.
- Tilføjet `POST /api/scan/lookup` (`backend/app/api/scan.py`) og `GET /api/movies/tmdb-search` (registreret før `/{movie_id}` for ikke at blive skygget).
- Frontend: `ScanMovie.jsx` har nu en manuel TMDb-titel-søgning som fallback når stregkode-scan ikke giver match; `client.js` har fået `tmdbSearch()`.
- Pytest-suite udvidet med `tests/test_scan.py` (mocket TMDb/UPC via `monkeypatch`, ingen rigtige netværkskald i CI). 13/13 grønne.
- Live-verificeret mod ægte MongoDB og ægte UPCitemdb (rigtigt UPC-opslag lykkedes); TMDb-kaldene fejler pt. korrekt med 502 da `TMDB_API_TOKEN` endnu ikke er sat i `.env` — kræver at Jan opretter en gratis TMDb-konto/token.

## [0.2.0 build 0002] — 2026-07-31 — Film- og tag-CRUD

- Tilføjet `backend/app/models/movie.py`: Pydantic-modeller `Movie`, `MovieCreate`, `MovieUpdate`.
- Tilføjet `backend/app/repositories/movie_repository.py` og `tag_repository.py`: MongoDB-adgang via Motor, indexes (text-index på `title`+`overview`, index på `tags_normalized`, unique sparse index på `barcode`, unique index på `tags.normalized`).
- Tilføjet `backend/app/services/movie_service.py` og `tag_service.py`: forretningslogik, herunder tag-normalisering (trim+lowercase dedup, men bevarer først-indtastede casing på tværs af film — jf. CLAUDE.md regel 7).
- Tilføjet `backend/app/api/movies.py` (`GET/POST /api/movies`, `GET/PATCH/DELETE /api/movies/{id}`) og `tags.py` (`GET /api/tags`).
- Tilføjet `backend/app/core/errors.py`: `MovieNotFoundError` (→ 404) og `DuplicateBarcodeError` (→ 409), håndteret via exception-handlers i `main.py`.
- `main.py`: routere registreret, indexes oprettes ved app-start (lifespan).
- Tilføjet pytest-suite (`backend/tests/`) mod `mongomock_motor` — dækker CRUD, tag-dedup/casing, tag-filtrering, dublet-barcode. 7/7 grønne.
- `ARCHITECTURE.md` opdateret: endpoint-status, MongoDB-skema (`tags_normalized`), fjernet redundant `/api/search` (dækkes af `/api/movies?q=&tags=`).

## [0.1.0 build 0001] — 2026-07-31 — Projekt-scaffold

- Oprettet `CLAUDE.md` (system-prompt), `version.json`, `ARCHITECTURE.md`, `MOVIE_API_REFERENCE.md`, `TECH_REFERENCE.md`, `FEATURES.md`, `BUGS.md`, `RELEASE_NOTES.md`.
- Valgt stack: React (Vite, PWA) frontend, Python/FastAPI backend, MongoDB database.
- Valgt scan-flow: UPC/EAN-stregkode-scanning i browseren → UPC-opslag → TMDb-metadata-bekræftelse.
- Oprettet minimal backend-skelet (FastAPI + Motor + health-endpoint) og frontend-skelet (React/Vite PWA).
- Docker Compose-fil til backend + frontend + MongoDB.
- `.claude/settings.local.json` med læse/skrive-rettigheder til projektmappen.
