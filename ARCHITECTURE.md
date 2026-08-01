# Arkitektur

Se [CLAUDE.md](CLAUDE.md) regel 5 og 8 — denne fil er den bindende reference for lag-ansvar og REST-kontrakten.

---

## Lag-ansvar

| Lag              | Placering                        | Ansvar                                                                 | Må IKKE                                      |
|-------------------|-----------------------------------|-------------------------------------------------------------------------|-----------------------------------------------|
| Frontend          | `frontend/src/`                   | UI, kamera-adgang, stregkode-detection, kalder backend REST API         | Kalde MongoDB, TMDb eller UPC-tjeneste direkte |
| API-lag           | `backend/app/api/`                 | HTTP-routing, request/response-validering (Pydantic), auth (`app/api/deps.py::get_current_user`, JWT-cookie) | Indeholde forretningslogik                    |
| Service-lag       | `backend/app/services/`            | Forretningslogik: matching, tag-normalisering, orkestrering af scan-flow | Tale direkte med MongoDB-driveren eller HTTP-libs |
| Repository-lag    | `backend/app/repositories/`        | MongoDB-adgang (Motor), queries, indexes                                | Kende til HTTP eller eksterne API'er           |
| Integrations-lag  | `backend/app/integrations/`        | HTTP-kald til TMDb og UPC-tjeneste, API-nøgle-håndtering, rate-limit/retry | Have forretningslogik ud over data-mapping     |

Kaldsretning er altid: **Frontend → API → Service → (Repository \| Integrations)**. Aldrig omvendt, og aldrig spring over et lag.

---

## REST API-kontrakt

Alle endpoints er ressource-orienterede og ligger under `/api`. Denne tabel opdateres *før* et nyt endpoint implementeres (jf. CLAUDE.md regel 8).

| Metode | Endpoint                     | Beskrivelse                                             | Status  |
|--------|-------------------------------|-----------------------------------------------------------|---------|
| GET    | `/api/movies`                  | Liste film, understøtter `?q=` (fritekst, MongoDB `$text`), `?tags=` (kommasepareret, case-insensitiv `$all`-match), `?format=`, `?audio_types=` og `?media_types=` (kommasepareret, `$in`-match), samt `?sort=` — kommasepareret liste af op til 3 `felt:retning`-tokens (fx `format:asc,audio_types:asc,title:desc`), se note om fler-niveau-sortering nedenfor. `?wishlist=true` viser ønskelisten i stedet for hovedbiblioteket (se note om ønskeliste nedenfor). `?watched=true`/`false` filtrerer på set-status (feature #40, udeladt = ingen filtrering). `?cast=` og `?director=` (præcist navne-match, feature #41) filtrerer til andre film i samlingen med samme skuespiller/instruktør. | done |
| GET    | `/api/movies/{id}`             | Hent én film med fuld metadata                             | done |
| POST   | `/api/movies`                  | Opret film (manuelt eller efter scan-bekræftelse), eller en ønskeliste-post hvis `is_wishlist: true`. 409 ved dublet `barcode`. Tildeler automatisk fortløbende `serial_number` — udelades helt for ønskeliste-poster. Sætter `registered_by` til den indloggede bruger; `owner` defaulter til samme hvis ikke angivet. Accepterer valgfri `location`, `owner`. | done |
| PATCH  | `/api/movies/{id}`             | Opdater film (tags, format, audio_types, location, owner, samt `serial_number`/`is_wishlist` — se noter nedenfor). `serial_number` kan **kun** ændres af en admin eller den bruger der står i filmens `registered_by` (403 ellers). `is_wishlist: false` flytter en ønske-post til biblioteket (tildeler et nyt `serial_number`, ubegrænset som ved oprettelse); `is_wishlist: true` gør det omvendte (fjerner `serial_number`, samme adgangsbegrænsning som redigering af et eksisterende nummer). | done |
| DELETE | `/api/movies/{id}`             | Slet film. Filmen logges først i `deleted_movies` (serienr, titel, hvornår, hvem — se `GET /api/movies/deleted`), derefter fjernes den fra `movies`; dens serienummer er derefter frit til genbrug. | done |
| GET    | `/api/movies/deleted`          | Liste over slettede film (serienr, titel, år, format, tidspunkt, hvem). Registreret før `/{movie_id}`. | done |
| POST   | `/api/movies/sync-tmdb`        | Genindlæser TMDb-metadata for alle film med `tmdb_id` (se note nedenfor). **Kræver admin.** Registreret før `/{movie_id}`. | done |
| GET    | `/api/movies/attribute-options`| Liste gyldige `format`-, `audio_types`- og `media_types`-værdier (enum-kilde til frontend-dropdowns). Registreret før `/{movie_id}`. | done |
| GET    | `/api/movies/check-duplicate`  | Input: `tmdb_id`. Output: liste af eksisterende film (bibliotek og/eller ønskeliste) med samme `tmdb_id` — blød advarsel før gem, ikke en blokering (feature #38). Registreret før `/{movie_id}`. | done |
| GET    | `/api/movies/stats`            | Aggregerede statistikker over biblioteket (ønskeliste ekskluderet): antal film, samlet spilletid, set/ikke-set, genre-/årti-/format-fordeling, top instruktører/skuespillere (feature #43). Registreret før `/{movie_id}`. | done |
| GET    | `/api/movies/collections/{collection_id}` | TMDb's fulde liste af film i en samling (franchise/box-set), krydsrefereret mod brugerens egne film — hver del markeret `owned`/`owned_movie_id`/`owned_is_wishlist` (feature #42). To path-segmenter kolliderer ikke med `/{movie_id}` (kun ét segment). | done |
| GET    | `/api/tags`                    | Liste alle tags (til autocomplete)                            | done |
| POST   | `/api/scan/lookup`             | Input: scannet UPC/EAN. Output: titel-gæt + TMDb-kandidater. Prøver UPCitemdb først, herefter Discogs som fallback hvis intet match (se MOVIE_API_REFERENCE.md). 502 hvis TMDb er utilgængelig/token mangler. | done |
| GET    | `/api/movies/tmdb-search`      | Direkte TMDb-titel-søgning (fallback når scan ikke matcher). Registreret før `/{movie_id}`. | done |
| GET    | `/api/health`                  | Health check (backend + MongoDB-forbindelse), samt `version`/`build` fra `version.json` (se `app/core/version_info.py`) | done |
| POST   | `/api/auth/register`           | Opret bruger ({username, password}). 409 hvis brugernavn er taget. Sætter auth-cookie. | done |
| POST   | `/api/auth/login`              | Login ({username, password}). 401 ved forkert login. Sætter auth-cookie.  | done |
| POST   | `/api/auth/logout`              | Rydder auth-cookien.                                           | done |
| GET    | `/api/users/me`                 | Nuværende bruger + indstillinger. 401 hvis ikke logget ind.       | done |
| PATCH  | `/api/users/me/settings`        | Opdatér bruger-specifikke view-/filter-indstillinger (sort_field/sort_direction — lagt til side til fordel for `sort_levels`, se note nedenfor — visible_fields, sort_levels, sort_presets). | done |
| GET    | `/api/settings/serial-number`   | Hent serienummer-generatorens opsætning (`start_number`, `increment`, `padding_width`). Åben for alle logget-ind brugere. | done |
| PATCH  | `/api/settings/serial-number`   | Opdatér opsætningen. **Kræver admin.** `start_number` flytter *direkte* næste-nummer-markøren (ikke en historisk oprindelse) — se note nedenfor. | done |
| POST   | `/api/users/me/password`        | Skift egen adgangskode ({current_password, new_password}). 401 ved forkert nuværende adgangskode. | done |
| GET    | `/api/users`                    | Liste alle brugere (id, username, role, created_at). **Kræver admin.** | done |
| PATCH  | `/api/users/{id}/role`          | Sæt en brugers rolle (`admin`\|`standard`). **Kræver admin.**    | done |
| POST   | `/api/system/deploy`            | Udløser en OTA-opdatering (`git pull` + geninstaller afhængigheder + genstart services) — se note nedenfor. **Kræver admin.** Kun meningsfuldt i produktion (se DEPLOYMENT.md); kører ikke lokalt under dev. | done |
| GET    | `/api/settings/system`          | Status for eksterne API-nøgler (`configured: bool` + `source: "env"\|"custom"\|"unset"` pr. nøgle) — **aldrig** den faktiske værdi. **Kræver admin.** Se note nedenfor. | planned |
| PATCH  | `/api/settings/system`          | Sæt/ryd TMDb-/UPC-/Discogs-nøgle. Skriv-kun (request-body, aldrig i response). Tomt felt rydder overstyringen (falder tilbage til `.env`). **Kræver admin.** | planned |

> **Auth**: `/api/movies`, `/api/tags`, `/api/scan` og `/api/settings` (GET) kræver login (router-level `dependencies=[Depends(get_current_user)]` i `app/api/deps.py`) — 401 uden gyldig session. Session er en JWT i en httpOnly cookie (`access_token`), ikke en Bearer-header. Biblioteket er ét fælles bibliotek for alle brugere; kun view-/filterindstillinger er personlige (gemt i `users.settings`, ikke i browserens localStorage).

> **Roller (admin/standard)**: `users.role` — det allerførste registrerede brugere bliver automatisk `admin` (`user_repository.count(db) == 0` ved registrering), alle efterfølgende bliver `standard`. `Depends(require_admin)` (i `app/api/deps.py`, bygger oven på `get_current_user`) giver 403 (`NotAuthorizedError`) for ikke-admin-brugere. Admin kan forfremme/degradere andre via `PATCH /api/users/{id}/role`. Der findes ingen finere-kornet "read/write pr. bruger"-model end dette — alle logget-ind brugere (uanset rolle) kan læse/skrive i det fælles filmbibliotek; rollen styrer kun adgang til system-opsætning (pt. kun serienummer-generatoren) og bruger-administration.

> **Serienummer-generator vs. redigering af én films nummer**: dette er to adskilte ting, bevidst delt over to sider i frontend (Settings-siden vs. filmens redigeringsvindue i biblioteket):
> - `PATCH /api/settings/serial-number` styrer *generatoren* — hvilket nummer NÆSTE tilføjede film får (`start_number`, som er en "flyt markøren hertil"-handling, ikke en formel-oprindelse), samt spring (`increment`, påvirker kun fremtidige tildelinger) og visnings-padding (`padding_width`, rent kosmetisk, påvirker ikke det lagrede tal).
> - `PATCH /api/movies/{id}` med `serial_number` ændrer én **eksisterende** films nummer direkte og bytter automatisk med en evt. kolliderende film (se `movie_service._reassign_serial_number`).
> - `movie_repository.next_serial_number` er kollisions-sikker: hvis det beregnede næste-nummer allerede er i brug (typisk lige efter `start_number` er flyttet tilbage til et brugt interval), rykker den videre til første ledige nummer i stedet for at fejle.
> - Counter-dokumentet migrerede fra det gamle skema (`{"value": N}`) til det nye (`{"next_value": N, "increment": 1, "padding_width": 0}`) automatisk ved første tilgang efter v0.9.0 — ingen manuel migrering nødvendig.

> `POST /api/movies` accepterer nu enten `tmdb_id` (backend henter fuld metadata fra TMDb server-side) eller en manuel `title` (fuldt manuel oprettelse uden TMDb). Se `MovieCreate` i `backend/app/models/movie.py`.

> **Strukturerede attributter**: `format` (étvalg, fast enum: VHS/DVD/BD/UHD/Digital-UHD/Digital-HD/Digital-STD), `audio_types` (flervalg, fast enum: Stereo/Mono/DD/DD5.1/DD7.1/DTS/DTS-HD-M/Atmos/D-true-HD) og `media_type` (étvalg, fast enum: Fysisk/Digital, feature #35 — et hurtigt fysisk-vs-digital-filter, uafhængigt af det mere detaljerede `format`) — se `MovieFormat`/`AudioType`/`MediaType` i `backend/app/models/movie.py`. I modsætning til tags er disse IKKE fritekst; ugyldige værdier afvises med 422. `serial_number` er et fortløbende heltal tildelt server-side ved oprettelse (atomisk `$inc` på en `counters`-collection, se `movie_repository.next_serial_number`).
> **Label-migrationer** (v0.22.0): `format`/`audio_types` fik kortere labels (fx "Blu-ray"→"BD", "Dolby Digital 5.1"→"DD5.1") — `movie_repository._migrate_format_labels`/`_migrate_audio_type_labels` kører automatisk ved opstart (`ensure_indexes`) og omskriver eksisterende dokumenters gamle, længere labels, så de fortsat validerer mod de nye enums. Det gamle `format: "Digital"` havde intet kvalitets-niveau og kan derfor ikke migreres eksakt — den defaulter til `"Digital-HD"`; tjek/ret manuelt hvis en film reelt var en anden digital-kvalitet. Live-verificeret mod Jans rigtige database.

> **Redigering af `serial_number`** (Settings-siden, feature #16): `PATCH /api/movies/{id}` accepterer nu `serial_number` (positivt heltal). Kolliderer den ønskede værdi med en anden films eksisterende serienummer, **bytter** de to film automatisk plads (`movie_service._reassign_serial_number`) — via et mellemtrin gennem en sentinel-værdi (`-1`), da MongoDB's unique index ellers ville afvise et direkte byt (ingen indbygget atomisk swap uden transaktioner).

> **Registrant/ejer/lokation** (feature #25/#26): hver film har `registered_by` (sat automatisk til den opretttende bruger ved `POST /api/movies`, aldrig klient-sættelig, aldrig ændret efterfølgende), `owner` (defaulter til `registered_by` men kan sættes/ændres frit — fx hvis en anden i husstanden reelt ejer disken) og `location` (fritekst, fx hylde/rum). `movie_service._assert_can_edit_serial_number` håndhæver at kun en admin eller brugeren i `registered_by` må ændre `serial_number` — håndhævet i backend (403 `NotAuthorizedError` ellers), ikke kun skjult/deaktiveret i UI'et (jf. CLAUDE.md regel 16).

> **Ønskeliste** (feature #28): samme `movies`-collection og datamodel som hovedbiblioteket, adskilt af boolean-feltet `is_wishlist` — undgår at duplikere hele CRUD/søgnings-/sorterings-laget for en separat ressource. Ønskeliste-poster har **intet** `serial_number` (feltet udelades helt af dokumentet, samme "udelad frem for null"-mønster som `barcode`, se BUGS.md #1/#10), og `next_serial_number` kaldes slet ikke ved oprettelse af en sådan post. `movie_repository.find_many`s `is_wishlist`-filter bruger `{"$ne": True}` for hovedbiblioteket (ikke en `False`-lighedstest) så film oprettet før denne feature — som slet ikke har feltet — fortsat vises korrekt der; kun `{"is_wishlist": True}` filtrerer til ønskelisten. Samme frontend-komponent (`Library.jsx`) genbruges for begge visninger via en `wishlist`-prop, som App.jsx's "Ønsker"-fane sætter.
> Selve *tilføjelsen* af en ønske-post bruger samme metode/data-opslag som "Scan film" (barcode-scan → UPC/Discogs → TMDb-søgning → bekræft): scan/søge/gem-flowet er udtrukket til `frontend/src/components/MovieLookupForm.jsx` (props: `user`, `wishlist`, `onSaved`), som både `pages/ScanMovie.jsx` (tynd wrapper, `wishlist=false`) og `pages/Library.jsx`s ønskeliste-tilstand (et "+ Tilføj ønske ▾"-panel i toolbaren, `wishlist=true`) genbruger — ingen dupliceret scan-/søgelogik.

> **OTA-opdatering** (feature #20): `POST /api/system/deploy` (`app/api/system.py`, admin-only) kalder `deploy_service.trigger_deploy()`, som starter et **detached** subprocess (`subprocess.Popen(..., start_new_session=True)`) der kører `settings.deploy_script_path` (default `/opt/moviedb-deploy.sh` — se DEPLOYMENT.md) og returnerer med det samme (202) uden at vente på det er færdigt. Scriptet ligger **uden for** git-working-tree'en (`/opt/moviedb`), for at undgå at `git pull` overskriver den fil bash er ved at eksekvere midt i kørslen. Scriptet selv kører som den almindelige service-bruger (`git pull`/`pip install`/`npm run build` — alle inden for `ReadWritePaths`). Da subprocessen arver `moviedb-backend.service`s `NoNewPrivileges=true`, kan den **aldrig** bruge `sudo` (systemd blokerer al ny-privilegie-optjening for hele process-træet permanent — ikke løsbart via sudoers) — den faktiske genstart af `moviedb-backend`/`caddy` sker derfor ved at scriptet rører en trigger-fil (`/opt/moviedb/.deploy-restart-trigger`), som en separat, ikke-sandboxed root-ejet systemd path-unit (`moviedb-deploy-restart.path` → `.service`, se `scripts/`) reagerer på uden om sudo/setuid helt. Se BUGS.md #18 for den fulde fejlanalyse. Frontend'en poller `/api/health`s `build`-felt efter at have udløst opdateringen, for at vise hvornår den nye version faktisk er oppe.
> **Admin-konfigurerbare API-nøgler** (feature #36): `TMDB_API_TOKEN`/`UPC_API_KEY`/`DISCOGS_TOKEN` kan nu sættes/opdateres direkte i UI'et (Indstillinger, admin-only) i stedet for kun via `.env`. `system_settings_repository` gemmer en overstyring pr. nøgle i en ny `system_settings`-collection (singleton-dokument, samme mønster som `counters`-collectionens serienummer-config). `.env` forbliver **bootstrap-fallback**: ved opstart (og ved enhver `PATCH`) skrives DB-overstyringen direkte ind i den globale `settings`-singleton i hukommelsen (`app/core/config.py`), så resten af koden (`tmdb_client`, `discogs_client` osv., som allerede blot læser `settings.tmdb_api_token` mv.) automatisk bruger den nye værdi med det samme — ingen genstart nødvendig, ingen ændring i integrations-laget. Overholder CLAUDE.md regel 6 ("aldrig eksponeres til frontend") ved at være **skriv-kun**: `PATCH`-payloaden indeholder den nye værdi, men `GET`/`PATCH`-response returnerer kun `configured`/`source` pr. nøgle, aldrig selve strengen. Et tomt felt i `PATCH`-payloaden rydder overstyringen (`$unset`, ikke `null` — samme "udelad frem for tom" konvention som resten af appen) og falder tilbage til `.env`.

> **Flyt ønske → bibliotek** (feature #32): filmens detaljevindue får en "Flyt til bibliotek"-knap når `is_wishlist` er sand, som sender `PATCH {is_wishlist: false}`. `movie_service.update_movie` opdager overgangen og tildeler et `serial_number` via samme `next_serial_number`-mekanisme som `create_movie` — enhver logget-ind bruger må gøre dette (det er reelt en første-tildeling, ikke en ændring af et eksisterende nummer, så `_assert_can_edit_serial_number` gælder ikke her). Den modsatte retning (`is_wishlist: true` på en biblioteks-film) fjerner nummeret igen (`movie_repository.clear_serial_number`, `$unset` — ikke `null`) og *er* underlagt samme adgangsbegrænsning som at redigere et eksisterende nummer.

> **Migration af `serial_number`-indexet** (v0.18.0): før ønskelisten fandtes var `serial_number`-indexet unikt men **ikke** sparse — et sådant index ville kollidere hvis to dokumenter begge mangler feltet. `movie_repository.ensure_indexes` opdager og migrerer selv et gammelt ikke-sparse `serial_number_1`-index (dropper og genopretter det som sparse) ved opstart, uden manuel indgriben — samme selv-migrerende mønster som counter-dokumentets skema (se note ovenfor). Live-verificeret mod Jans rigtige database 2026-08-01.

> **Rating**: `rating` (0-10, TMDb's `vote_average` — IKKE den faktiske IMDb-rating, se MOVIE_API_REFERENCE.md) hentes automatisk ved oprettelse via `tmdb_id` og caches lokalt som alle andre TMDb-felter. Ikke sættelig af klienten (hverken `MovieCreate` eller `MovieUpdate`); manuelt oprettede film (uden `tmdb_id`) har altid `rating: null`.

> **Set/franchise-gruppering** (feature #42): `collection_id`/`collection_name` hentes fra TMDb's `belongs_to_collection` ved oprettelse/synkronisering — TMDb-sourced, ikke sættelig af klienten (samme mønster som `rating`). `GET /api/movies/collections/{collection_id}` kalder `tmdb_client.get_collection` (TMDb's `/collection/{id}`, fuld liste af samlingens film) og krydsrefererer mod egne film via ét batch-opslag (`movie_repository.find_by_tmdb_ids`, `{"$in": [...]}`) i stedet for ét opslag pr. del. Frontend viser "Del af samlingen: X" i detaljevinduet, udvidbart til en liste med ejer-status pr. del og en "+ Tilføj"-knap for manglende (kalder `POST /api/movies` direkte med kun `tmdb_id` — ingen mellemliggende formular, samme minimalistiske mønster som "Flyt til bibliotek").

> **Statistik-side** (feature #43): `GET /api/movies/stats` beregnes i Python over ét `find()`-kald (`movie_repository.find_all_library_movies`, ønskeliste ekskluderet, uncapped i modsætning til den normale 500-grænse i `find_many`) frem for en MongoDB aggregation-pipeline — matcher kodebasens eksisterende stil og undgår uverificerede pipeline-stadier i mongomock-testsuiten (samme forsigtighed som BUGS.md's noter om mongomock's sparse-index/arrayFilters-uoverensstemmelser). `Counter`-baseret optælling af genre/årti/format/instruktør/skuespiller i hukommelsen — fuldt fint til en personlig samlings størrelsesorden.

> **Skuespiller/instruktør-browsing** (feature #41): nyt `director`-felt (TMDb's `credits.crew`, første person med `job == "Director"`, `tmdb_client._director`) ved siden af det eksisterende `cast`. Klik på et navn i detaljevinduet filtrerer biblioteket til andre film *i egen samling* med samme person (`?cast=`/`?director=` — præcist array-/felt-match, ikke fritekstsøgning: `$text`-indexet dækker fortsat kun `title`/`overview`). Kun ét personfilter ad gangen (ikke kombinerbart med tag-filtrering i UI'et), vist som en fjernbar aktiv-filter-indikator i stedet for en chip-liste.

> **"Set"-status** (feature #40): `watched` (bool) + `watched_at` (dato, valgfri) — `?watched=true|false` på `GET /api/movies` filtrerer, `watched_at` er sorterbar. `create_movie` sætter aldrig `watched: false` eksplicit i dokumentet (feltet er simpelthen fraværende ved oprettelse), så `watched=false`-filteret bruger samme `{"$ne": True}`-mønster som `is_wishlist` ovenfor — en direkte `{"watched": False}`-lighedstest ville ellers ekskludere alle film der aldrig er markeret, inklusive alle film oprettet før denne feature fandtes.

> **Personlig rating + note** (feature #39): `personal_rating` (1-10) og `personal_note` (fritekst) er helt adskilt fra TMDb's `rating` — kun sættelig via `PATCH /api/movies/{id}` (ikke ved oprettelse), redigeres i detaljevinduet. `null` rydder feltet direkte (`$set`, ikke `$unset`) — der er ingen sparse unique-index-problematik her som ved `barcode`/`serial_number`, så det simple read-modify-write-frie mønster fra `movie_repository.update` er tilstrækkeligt uden særbehandling.

> **IMDb-/trailer-link** (feature #34): `imdb_url` og `trailer_url` hentes fra TMDb's `external_ids`/`videos` — bundtet ind i samme `GET /movie/{id}`-kald som resten af detaljerne via `append_to_response=credits,videos,external_ids` (én HTTP-request i stedet for tidligere to: detail + credits separat). `trailer_url` er det første officielle YouTube-"Trailer" i `videos.results` (ikke teasers/klip), ellers `null`. Kan også sættes manuelt for film oprettet uden `tmdb_id`.

> **TMDb-synkronisering** (feature #33): `POST /api/movies/sync-tmdb` (admin) genkører `tmdb_client.get_movie_details` for hver film med et `tmdb_id` og opdaterer kun de TMDb-sourcede felter (titel, år, poster, plot, genrer, cast, rating, spilletid, imdb/trailer-link) — aldrig brugerens egne felter (tags, format, audio_types, location, owner, serial_number, registered_by, barcode). Én films fejlende TMDb-opslag (fjernet fra TMDb, TMDb midlertidigt nede) stopper ikke resten af kørslen — den tælles som fejlet (`TmdbSyncResult.failed_titles`) og synkroniseringen fortsætter.

> **Fler-niveau sortering** (feature #17/#27): `?sort=` accepterer op til `movie_repository.MAX_SORT_LEVELS` (3) kommasepararede `felt:retning`-tokens, fx `format:asc,audio_types:asc,title:desc`. `movie_service.parse_sort_param` validerer hvert felt mod whitelistet `movie_repository.SORT_FIELDS` (kan aldrig sortere på et vilkårligt/uindekseret felt) og bygger et compound Mongo-sort (`cursor.sort([(felt1, retning1), ...])`). Et ukendt felt-token *afvises ikke* med 422 — det droppes stille og roligt, så et gemt preset der refererer et felt der senere er fjernet degraderer i stedet for at fejle hele biblioteksvisningen. Manglende `:retning` defaulter til `asc`; et ukendt `:retning`-ord behandles også som `asc`. Brugerens valgte niveauer gemmes som `sort_levels` (`UserSettings`) og kan navngives og gemmes som et gengenkaldeligt `sort_presets`-indgang (samme model), begge server-side pr. bruger — se `frontend/src/pages/Library.jsx`s sorterings-panel.
> `SORT_FIELDS` dækker (v0.22.0, BUGS.md #14): `title`, `year`, `serial_number`, `created_at` (adskilt fra `serial_number` — de kan afvige efter en manuel serienummer-ombytning), `rating`, `runtime`, `format`, `audio_types`, `media_type`, `location`, `owner`, `registered_by`.

> Der er ikke et separat `/api/search`-endpoint — kombineret fritekst+tag-søgning dækkes af `/api/movies?q=&tags=` (se ovenfor), for at undgå to endpoints med overlappende ansvar.

---

## Data-flow: scan-til-gem

```
1. Frontend: bruger scanner cover → stregkode (UPC/EAN) læses client-side
2. Frontend → POST /api/scan/lookup { barcode }
3. Backend (scan_service):
   a. integrations/upc_client → slår barcode op → titel-gæt (eller ingen match)
   a2. Intet match fra UPCitemdb? integrations/discogs_client prøves som fallback (bedre dækning for europæiske EAN-koder)
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
| `movies`   | `serial_number` (fortløbende, immutable, **udelades helt for ønskeliste-poster** — se BUGS.md #29 soft-delete/genbrug), `tmdb_id`, `barcode` (**udelades helt af dokumentet når ikke angivet — se BUGS.md #1**), `title`, `year`, `tags[]` (display-case), `tags_normalized[]` (lowercase, bruges til filtrering), `format` (enum-streng), `audio_types[]` (enum-strenge), `media_type` (enum-streng, Fysisk/Digital), `rating` (0-10, TMDb `vote_average`, kun sat når `tmdb_id` er angivet), `runtime` (minutter, fra TMDb eller manuel), `imdb_url`, `trailer_url`, `location` (fritekst), `owner` (brugernavn, defaulter til `registered_by`), `registered_by` (brugernavn, sat automatisk ved oprettelse, immutable), `is_wishlist` (bool, default false, se feature #28) | text-index på `title`+`overview`, index på `tags_normalized`, `format`, `audio_types`, `media_type`, `year`, `rating`, `runtime`, `location`, `owner`, `registered_by`, `created_at`, `is_wishlist`, unique sparse index på `barcode`, unique **sparse** index på `serial_number` |
| `tags`     | `name` (første-typede casing), `normalized` (lowercase, unik nøgle)     | unique index på `normalized`                |
| `counters` | `_id` (fast nøgle `"movie_serial"`), `next_value` (hvad næste film får), `increment`, `padding_width` (kun visning) | — (kun ét dokument, atomisk `$inc`)         |
| `deleted_movies` | `movie_id` (den oprindelige films `_id`), `serial_number`, `title`, `year`, `format`, `deleted_at`, `deleted_by` (brugernavn) — se `movie_repository.archive_deleted` | index på `deleted_at`                       |
| `users`    | `username` (unik), `password_hash` (bcrypt), `role` (`admin`\|`standard`), `settings` (sort_field, sort_direction, visible_fields — personlige view-/filterindstillinger) | unique index på `username`                  |

Detaljeret skema og indexes: se [TECH_REFERENCE.md](TECH_REFERENCE.md).
