# Changelog

Nyeste øverst. Hver entry tagges med `[version build NNNN]` (jf. CLAUDE.md regel 4).

## [0.15.0 build 0017] — 2026-08-01 — Soft-delete af film + slettet-liste

- Ny collection `deleted_movies` (`movie_repository.archive_deleted`/`list_deleted`, index på `deleted_at`).
- `movie_service.delete_movie` logger nu filmen (serienr, titel, år, format, tidspunkt, hvem) i `deleted_movies` *før* den fjernes fra `movies` — i stedet for bare at forsvinde. Serienummeret er automatisk frit til genbrug bagefter (det unikke index kender kun til film der stadig findes i `movies`).
- Ny `GET /api/movies/deleted` (registreret før `/{movie_id}`), nyt `DeletedMovie`-model.
- `DELETE /api/movies/{id}`-handleren henter nu `current_user` for at kunne logge hvem der slettede.
- Ny sektion "Slettede film" på Indstillinger-siden, viser serienr./titel/år/hvornår/hvem.
- Nye regressionstests i `test_deleted_movies.py`: sletning logges korrekt, et frigjort serienummer kan genbruges af en ny film, sletning af ukendt film giver stadig 404.
- `ARCHITECTURE.md` opdateret (REST-kontrakt, MongoDB-collections). `FEATURES.md` #29 markeret done.

## [0.14.0 build 0016] — 2026-08-01 — Print-venlig liste-side

- Ny frontend-side `frontend/src/pages/PrintList.jsx` + `PrintList.css`, ny fane "Print" i navigationen.
- Henter alle film via det eksisterende `GET /api/movies` (sorteret på `serial_number` stigende), viser dem i en kompakt tabel (Serienr./Titel/År/Format/Lokation), én film pr. linje. Simpel fritekst-søgning for at afgrænse listen før udskrift.
- `@media print`-regler skjuler navigation/knapper/footer og lader kun tabellen fylde siden ved faktisk udskrivning (`window.print()`).
- Ingen backend-ændringer — genbruger eksisterende `/api/movies`-kontrakt. `FEATURES.md` #31 markeret done.

## [0.13.0 build 0015] — 2026-08-01 — Lokation/ejer/registrant + adgangsstyring på serienummer

- `Movie`/`MovieCreate`/`MovieUpdate` (`models/movie.py`) udvidet med `location` (fritekst), `owner` (brugernavn) og `registered_by` (brugernavn, kun læsbar — sættes aldrig af klienten).
- `POST /api/movies` sætter nu `registered_by` til den indloggede bruger (fra JWT-cookien, ikke fra request-body) og lader `owner` defaulte til samme hvis ikke angivet. `movies.py`s `create_movie`/`update_movie`-handlers henter nu `current_user` via `Depends(get_current_user)` og videresender til service-laget.
- Ny `movie_service._assert_can_edit_serial_number`: `PATCH /api/movies/{id}` afviser (403 `NotAuthorizedError`) ændring af `serial_number` medmindre requesten kommer fra en admin eller fra den bruger der står i filmens `registered_by` — håndhævet i backend, ikke kun ved at deaktivere feltet i UI'et (jf. CLAUDE.md regel 16).
- `ScanMovie.jsx`: nye felter "Lokation" og "Ejer" (ejer forudfyldes med den indloggede brugers navn, men kan ændres) i gem-formularen.
- `Library.jsx`s `MovieDetailModal`: nye redigerbare felter Lokation/Ejer, en read-only "Registreret af"-linje, og serienummer-feltet deaktiveres (med forklarende tekst) hvis den nuværende bruger hverken er admin eller filmens registrant.
- Nye regressionstests i `test_movie_permissions.py`: registrant/ejer-defaults, standard-bruger kan ændre serienummer på egne registrerede film men ikke andres, admin kan altid.
- `ARCHITECTURE.md` opdateret (REST-kontrakt, MongoDB-skema, ny note om registrant/ejer/lokation). `FEATURES.md` #25, #26 markeret done.

## [0.12.0 build 0014] — 2026-08-01 — Versionsvisning, runtime-tag, klik-til-vis sortering/filtre

- Tilføjet `backend/app/core/version_info.py`: læser `version.json` (repo-roden) én gang ved opstart. `GET /api/health` returnerer nu også `version`/`build`. Ny test `test_health.py`.
- `frontend/src/App.jsx`: henter `/api/health` ved opstart og viser version+build i en ny footer nederst på siden (feature #22).
- TMDb-integrationen henter nu også `runtime` (minutter) fra `/movie/{id}` og gemmer det på filmen (`tmdb_client.py`, `movie_service.py`, `models/movie.py`). Manuel oprettelse/redigering kan også sætte `runtime` direkte.
- Filmkort i biblioteket kan nu vise en "Spilletid"-værdi (`X min`) via "Vis felter" (feature #23). De viste felter (år/format/lyd/spilletid) er samlet i et nyt 2-kolonne grid (`.movie-meta-grid`) i stedet for én lang kolonne, så kortene fylder mindre i højden.
- Sorterings-kontrollen og tag/format/lyd-filterpanelet i biblioteksvisningen er nu klik-til-vis (`Sortér ▾` / `Filtrér ▾`-knapper), samme mønster som det eksisterende "Vis felter ▾" (feature #24). Filtrér-knappen viser et antal når der er aktive filtre.
- `UserSettings.visible_fields` og `DEFAULT_SETTINGS` udvidet med `runtime`.
- `ARCHITECTURE.md`, `FEATURES.md` opdateret (#22, #23, #24 markeret done).

## [0.11.1 build 0013] — 2026-08-01 — Fase 2: fejlret alle 10 fund fra kode-gennemgangen

Retter BUGS.md #3-12 (registreret i fase 1 af kode-gennemgangen 2026-08-01, se CLAUDE.md regel 16). Kort per fund — fuld beskrivelse/løsning i BUGS.md:

- **#3+#4 (auth_service.py)**: `PATCH /api/users/{id}/role` tjekker nu om brugeren findes (404 i stedet for 500-crash) og afviser at fjerne den sidste admin (ny `LastAdminError` → 409, håndhævet i backend).
- **#5 (Settings.jsx)**: `UsersSection.toggleRole` viser nu en fejlbesked i stedet for at fejle lydløst.
- **#6 (ScanMovie.jsx)**: `saveMovie()` viser nu den faktiske backend-fejl (fx dublet-stregkode-409) i stedet for kun en generisk besked.
- **#7 (tag_service.py)**: `resolve_tags` fanger nu `DuplicateKeyError` fra et race-condition-scenarie ved et helt nyt tag og genindlæser i stedet for at crashe.
- **#8+#9 (tmdb_client.py)**: `_rating()` bruger nu `is not None` (bevarer en ægte `0.0`); ny fælles `_raise_for_status()` mapper alle uventede TMDb-fejlstatusser til `TmdbUnavailableError` (502) i stedet for rå 500'ere.
- **#10 (movie_service.py)**: `create_movie` trimmer og udelader nu blanke/whitespace-only stregkoder helt, samme behandling som `null`.
- **#11 (config.py/main.py)**: ny `Settings.using_insecure_jwt_secret`-property; lifespan logger en tydelig advarsel ved opstart hvis den usikre default-JWT-hemmelighed stadig er i brug.
- **#12 (models/user.py)**: ny validator afviser adgangskoder over bcrypts reelle 72-byte-grænse eksplicit, i stedet for at lade dem blive tavst afkortet.

Ny fælles metode-regel (CLAUDE.md #16) anvendt gennemgående: null-tjek før brug, specifikke fejlbeskeder til brugeren, lockout-beskyttelse i backend, `is not None` for eksterne API-tal, hele klassen af "tomhed"-repræsentationer rettet, sikkerhedskonfiguration advarer ved opstart.

Testdækket: 9 nye regressionstests (`test_roles.py` ×4, `test_movies.py` ×2, `test_tmdb_client.py` ×3 — ny fil). 66/66 grønne. Live-verificeret mod ægte MongoDB (blank-barcode, password-længde, JWT-advarsel fraværende med Jans rigtige `.env`).

## [0.11.0 build 0012] — 2026-08-01 — Telefon-adgang over LAN (HTTPS) + mobilvenligt design

- `frontend/vite.config.js`: dev-serveren binder nu til `0.0.0.0` (`server.host: true`) og kører HTTPS med et selvsigneret cert fra `frontend/.cert/` (git-ignoreret, genereres lokalt med `openssl` — se TECH_REFERENCE.md). HTTPS er et hårdt krav fra browseren for at `getUserMedia` (kamera-scanning) må bruges fra andet end `localhost`.
- Ny indgående firewall-regel (`Movie Database dev (Vite 5173)`, privat netværksprofil) så enheder på samme LAN kan nå dev-serveren. Backend (`:8000`) eksponeres ikke selv — Vite's proxy videresender `/api` server-side, usynligt for telefonen.
- Mobilvenligt responsivt design: `index.css` (input `font-size: 16px` for at undgå iOS Safaris auto-zoom-på-fokus, `overflow-x: hidden`), `App.css` (header/navigation stables og bliver scrollbar under 640px, brugernavn skjules på smalle skærme), `Library.css` (værktøjslinje/filter-paneler stabler, film-detalje-modalen bliver fuldskærmsagtig og bund-forankret på mobil, grid-kolonner tilpasses), `ScanMovie.css` (kandidat-grid og handlingsknapper tilpasses).
- Build verificeret (`npm run build`), HTTPS dev-server smoke-testet lokalt og via LAN-IP.

## [0.10.0 build 0011] — 2026-08-01 — Bruger-roller (admin/standard), adgangskode-ændring

- `models/user.py`: ny `UserRole` enum (`admin`/`standard`), `User.role`. Nye modeller `PasswordChange`, `UserRoleUpdate`.
- **Bootstrap**: det allerførste registrerede bruger bliver automatisk `admin` (`user_repository.count(db) == 0` på registreringstidspunktet); alle efterfølgende registreringer bliver `standard`. Ingen separat seed-konto med kendt/lækbar adgangskode.
- Ny `app/api/deps.py::require_admin`-dependency (403 `NotAuthorizedError` for ikke-admin). `PATCH /api/settings/serial-number` kræver nu admin — `GET` er fortsat åben for alle logget-ind brugere.
- Nye endpoints: `POST /api/users/me/password` (skift egen adgangskode), `GET /api/users` (liste alle, admin), `PATCH /api/users/{id}/role` (forfremme/degradere, admin).
- **Migreret eksisterende data**: den ægte "jan"-konto (oprettet før roller fandtes) fik sat `role: "admin"` direkte i databasen, da den reelt er den eneste/første bruger af appen.
- Frontend: `Settings.jsx` har fået en adgangskode-skift-formular (alle brugere) og en "Brugere"-sektion (kun admin: liste + forfrem/degradér). Serienummer-opsætningen vises stadig for alle (læsning), men felterne er disabled og gem-knappen skjult for ikke-admins.
- Pytest-suite: ny `tests/test_roles.py` (bootstrap, admin-gating på skriv/læs, adgangskode-skift, bruger-liste/rolle-ændring, 403 for standard-brugere). 57/57 grønne. Live-verificeret mod ægte MongoDB.

## [0.9.0 build 0010] — 2026-08-01 — Serienummer-generator-opsætning (afløser dele af v0.8.0)

- **Redesign efter feedback**: Settings-siden viste i v0.8.0 en liste over alle film med redigérbart serienummer. Det er nu flyttet til filmens redigeringsvindue i biblioteket (hvor det hører hjemme sammen med tags/format/audio_types) — Settings-siden har i stedet fået en "Serienummer-opsætning"-formular til selve generatoren.
- Counter-dokumentet (`counters._id: "movie_serial"`) har fået et nyt skema: `next_value` (hvilket nummer næste film får), `increment` (spring for fremtidige tildelinger), `padding_width` (kun visning). Migreres automatisk fra det gamle skema (`{"value": N}`) ved første tilgang — ingen manuel migrering nødvendig.
- Nye endpoints `GET`/`PATCH /api/settings/serial-number`. `start_number` er en "flyt næste-nummer-markøren hertil"-handling (ikke en formel-oprindelse) — sætter du den til 500, får den næste tilføjede film nummer 500 præcis. `increment` ændrer kun springet for fremtidige tildelinger fra det nuværende punkt.
- `movie_repository.next_serial_number` er nu kollisions-sikker efter reconfigurering: rammer det beregnede nummer en allerede-brugt værdi (fx efter at have flyttet `start_number` tilbage i et brugt interval), rykker den videre til første ledige nummer i stedet for at fejle med en duplicate-key-fejl.
- `padding_width` bruges i frontend til at zero-padde serienummer-badges (fx "00007") — rent visuelt, påvirker ikke det lagrede tal eller sorteringen.
- Pytest-suite: ny `tests/test_settings.py` (default-opsætning, ændring af start/increment, kollisions-omgåelse efter reconfigurering, validering, auth-krav). 48/48 grønne. Live-verificeret mod ægte MongoDB, inkl. den automatiske skema-migrering af det eksisterende counter-dokument.

## [0.8.0 build 0009] — 2026-08-01 — Settings-side: redigérbart serienummer

- `MovieUpdate` accepterer nu `serial_number` (positivt heltal). `movie_service._reassign_serial_number` bytter automatisk plads med en evt. film der allerede har det ønskede nummer — via et sentinel-mellemtrin (`-1`), da MongoDB's unique index på `serial_number` ellers ville afvise et direkte byt (intet indbygget atomisk "swap to unique values" uden transaktioner).
- Nye repository-funktioner `find_by_serial_number` og `set_serial_number` i `movie_repository.py`.
- Ny frontend-side `pages/Settings.jsx` (+ `Settings.css`), tilgået via en ny "Indstillinger"-fane i hovednavigationen. Viser konto-info (brugernavn) og en liste over alle film med redigérbart serienummer pr. række.
- Pytest-suite udvidet med swap-scenariet, "sæt til ubrugt nummer" og validering af ikke-positive værdier (422). 41/41 grønne. Live-verificeret mod ægte MongoDB (byt bekræftet i begge retninger).

## [0.7.0 build 0008] — 2026-08-01 — Brugerlogin + server-side view-indstillinger

- Nye backend-moduler: `core/security.py` (bcrypt password-hash, JWT via `pyjwt`), `models/user.py`, `repositories/user_repository.py`, `services/auth_service.py`, `api/auth.py` (`POST /api/auth/register|login|logout`), `api/users.py` (`GET /api/users/me`, `PATCH /api/users/me/settings`), `api/deps.py::get_current_user`.
- **Ét fælles filmbibliotek** for alle brugere — kun view-/filterindstillinger (`sort_field`, `sort_direction`, `visible_fields`) er personlige, gemt i `users.settings` i stedet for browserens `localStorage`.
- `movies`/`tags`/`scan`-routerne kræver nu login (router-level `dependencies=[Depends(get_current_user)]`) — 401 uden gyldig session. Session er en JWT i en httpOnly cookie (`access_token`, `samesite=lax`), ikke en Bearer-header.
- Åben tilmelding: alle kan oprette en konto via `POST /api/auth/register` (brugernavn 3-32 tegn, adgangskode min. 8 tegn, bcrypt-hashet). Der er ikke lagt et admin-lag ind til at begrænse hvem der kan registrere sig.
- Frontend: ny `pages/Login.jsx` (login/opret-konto), `App.jsx` gater nu hele appen bag `GET /api/users/me` og har fået en "Log ud"-knap. `Library.jsx`'s sortering/synlige-felter er flyttet fra `localStorage` til `api.updateMySettings()`.
- Nye JWT/cookie-relaterede indstillinger i `.env.example`: `JWT_SECRET_KEY` (skal genereres unikt pr. miljø), `COOKIE_SECURE` (sæt til `true` bag HTTPS i produktion).
- Pytest-suite udvidet med `tests/test_auth.py` (register/login/logout/settings/gating). `tests/conftest.py`'s `client`-fixture logger nu automatisk en test-bruger ind via en rigtig `/api/auth/register`-kald (httpx's cookie-jar håndterer resten), så alle eksisterende movie-/tag-/scan-tests fortsat virker uændret. 38/38 grønne. Live-verificeret mod ægte MongoDB (register → beskyttet endpoint → settings-update → logout → 401).

## [0.6.1 build 0007] — 2026-08-01 — Fix: serienummer/format-badge skjult bag poster

- `frontend/src/pages/Library.css`: `.movie-serial` og `.movie-format-badge` har fået `z-index: 2` — de blev malet under poster-billedet efter `.movie-poster` fik `position: relative` i v0.6.0 (nødvendig for rating-badgen). Se BUGS.md #2.

## [0.6.0 build 0006] — 2026-07-31 — Rating, sortering og konfigurerbar kort-visning

- `backend/app/integrations/tmdb_client.py`: `search_movies()` og `get_movie_details()` returnerer nu også `rating` (TMDb `vote_average`, rundet til 1 decimal — **ikke** den faktiske IMDb-rating, se MOVIE_API_REFERENCE.md).
- `Movie` og `MovieCandidate` har fået feltet `rating`. Kun sat automatisk via `tmdb_id`-oprettelse — ikke en del af `MovieCreate`/`MovieUpdate` (samme princip som `overview`/`genres`/`cast` for TMDb-stien).
- `GET /api/movies` har nye query-params `?sort=` (`title`\|`year`\|`serial_number`\|`rating`) og `?direction=` (`asc`\|`desc`). Sortérbare felter er whitelistet i `movie_repository.SORT_FIELDS` — ugyldige værdier afvises med 422 (`Literal`-typer på query-parametrene).
- Nye indexes på `year` og `rating` i `movies`-collectionen.
- Frontend: `Library.jsx` har fået en sortér-kontrol (felt + stigende/faldende) og en "Vis felter"-indstillingspanel (afkrydsning af År/Tags/Format/Lyd-type/Rating pr. filmkort), gemt i `localStorage` så valget huskes. Rating vises som badge på filmkort, i scan-kandidatlisten og i detalje-modalen.
- Pytest-suite udvidet med sortering (titel/år/serienr./rating, begge retninger) og ugyldig sort/direction-validering. 28/28 grønne. Live-verificeret mod ægte MongoDB + TMDb.

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
