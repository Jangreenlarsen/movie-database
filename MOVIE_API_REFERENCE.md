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
| `vote_average`      | `rating`-fallback (0-10, rundet til 1 decimal) — kun hvis OMDb ikke har et bedre svar, se OMDb-afsnittet nedenfor |

> **OBS**: `vote_average` er TMDb's egen community-rating — det er **ikke** den faktiske IMDb-rating. Siden feature #46 (2026-08-02) hentes den *faktiske* IMDb-rating via OMDb i stedet, med `vote_average` som fallback hvis OMDb ikke er konfigureret/tilgængelig — se `## OMDb` nedenfor.

### Fejlhåndtering
- Tomt `results[]` ved søgning → vis "ingen match, prøv en anden titel" i frontend, tilbyd manuel indtastning.
- HTTP 401 → ugyldig/manglende token, log som konfigurationsfejl (ikke bruger-fejl).
- HTTP 429 → backoff og retry (se `TECH_REFERENCE.md` for retry-strategi i `integrations/tmdb_client.py`).

---

## OMDb (faktisk IMDb-rating, feature #46)

Implementeret i `backend/app/integrations/omdb_client.py`. **Ikke** en erstatning for TMDb — bruges udelukkende til at berige én enkelt værdi (`rating`) med det tal der reelt vises på imdb.com, da TMDb's `vote_average` er en helt separat community-rating. Nøglet på det `imdb_id` TMDb allerede leverer via `external_ids`, ingen fritekst-matching involveret.

- **Base URL**: `https://www.omdbapi.com/`
- **Auth**: `apikey=`-query-param. Gratis nøgle (1.000 opslag/dag) på http://www.omdbapi.com/apikey.aspx. Opbevares som `OMDB_API_KEY` i `.env`, eller admin-sat i UI'et under Indstillinger → System-indstillinger (samme mønster som de øvrige nøgler) — overstyrer `.env` med det samme, uden genstart.
- **Request**: `GET ?i=<imdb_id>&apikey=<nøgle>` (fx `?i=tt0133093`).
- **Response**: `imdbRating` (streng, fx `"8.7"`, eller `"N/A"` hvis ingen rating findes endnu). `Response: "False"` + `Error`-felt hvis `imdb_id` ikke findes hos OMDb.
- **Fejlhåndtering**: samme filosofi som UPC/Discogs/Plex — manglende nøgle, intet `imdb_id`, `N/A`-rating, `Response: "False"`, en ikke-200-status eller en netværksfejl giver alle sammen `None` (aldrig en kastet exception). `movie_service._resolve_rating` falder i så fald tilbage til TMDb's `vote_average`, så filmen aldrig ender uden nogen rating overhovedet.
- **Kaldes**: automatisk ved oprettelse af en film via `tmdb_id`, og ved `POST /api/movies/sync-tmdb`. Ikke et separat brugerflow/knap — helt usynligt for brugeren ud over at tallet nu matcher IMDb i stedet for TMDb.

---

## UPC-opslagstjeneste (stregkode → produkt/titel)

Implementeret i `backend/app/integrations/upc_client.py` mod **UPCitemdb**'s gratis trial-tier (live-verificeret) som standard-primær kilde, med **Discogs**, **UPCDatabase.org** og **EAN-Search.org** som fallbacks (se nedenfor) i den rækkefølge når det forrige led ikke finder et match. **Feature #77 (2026-08-04)**: hvilken kilde der prøves *først* er nu admin-konfigurerbar (`primary_barcode_source` i Indstillinger → System-indstillinger — "Primær stregkode-kilde") — de øvrige tre følger stadig som fallback i deres normale rækkefølge, blot med den valgte trukket forrest. `scan_service._lookup_title` prøver dem i den beregnede rækkefølge og returnerer hvilken kilde der matchede (`barcode_source`) — alle fire integrationer eksponerer samme `lookup_title(barcode) -> str | None`-kontrakt, så en femte kilde kan tilføjes samme sted uden at ændre service- eller API-laget.

### UPCitemdb
- **Base URL**: `https://api.upcitemdb.com/prod/trial/lookup`
- **Auth**: ingen nøgle krævet på trial-tier, men rate-limited pr. IP (~100/dag). Produktions-tier kræver `user_key` + `key_type` headers.
- **Request**: `GET ?upc=<stregkode>`
- **Response**: `items[]` med bl.a. `title`, `brand`, `images[]`. Titel bruges som gæt til efterfølgende TMDb-søgning — brand/model-navne på DVD-covers er ofte ikke rene filmtitler, så forvent at skulle rense/forkorte strengen (fx fjern "(DVD)", "[Blu-ray]", årstal i parentes) før TMDb-søgning.

### Fejlhåndtering
- `code: "INVALID_UPC"` eller tomt `items[]` → intet gæt, falder videre til Discogs, derefter UPCDatabase.org (se nedenfor), og til sidst til manuel TMDb-søgning (se `/api/movies/tmdb-search` i ARCHITECTURE.md).
- Rate-limit ramt → log som warning, returnér "intet gæt" til frontend i stedet for at fejle hele scan-flowet (UPC-opslag er et *nice-to-have* forudfyld, ikke en kritisk sti).

### Discogs (fallback, feature #30)

Implementeret i `backend/app/integrations/discogs_client.py`. Bruges kun når UPCitemdb ikke finder noget — UPCitemdb's trial-tier er stærkt USA-detail-centreret og misser ofte europæiske EAN-13 stregkoder på film; Discogs' community-katalogiserede database (oprindeligt musik, men dækker også DVD/Blu-ray/VHS-udgivelser med stregkoder) har typisk bedre international dækning. **Live-verificeret 2026-08-01** mod den rigtige API (fx `?barcode=085391773726` → traf "Don Davis - The Matrix").

- **Base URL**: `https://api.discogs.com/database/search`
- **Auth**: Valgfrit personal access token (`DISCOGS_TOKEN` i `.env`, eller admin-sat i UI'et under Indstillinger → System-indstillinger, feature #36 — oprettes på https://www.discogs.com/settings/developers) som `token=`-query-param — hæver rate-limit fra 25 til 60 req/min. Virker også helt uden token.
- **Påkrævet header**: `User-Agent` med en beskrivende værdi (Discogs afviser/rate-limiter hårdere uden) — sat til `MovieDatabaseApp/1.0`.
- **Request**: `GET ?barcode=<stregkode, kun cifre>`
- **Response**: `results[]`, hvert element har bl.a. `title` (format: `"Artist - Titel"`, hvor "Artist" for film ofte er "Various", et studienavn, eller komponisten — fjernes med `_strip_artist_prefix` før TMDb-søgning) og selve `barcode[]`-listen (til evt. fremtidig krydstjek).
- **Fejlhåndtering**: samme filosofi som UPCitemdb — enhver fejl (netværk, ikke-200, tomt `results[]`) logges og returnerer `None`, aldrig en kastet exception (nice-to-have forudfyld, ikke kritisk sti).

### UPCDatabase.org (fallback, feature #69)

Implementeret i `backend/app/integrations/upcdatabase_client.py`. Tredje og sidste stregkode-opslags-fallback, forsøgt kun når hverken UPCitemdb eller Discogs finder et match — tilføjet 2026-08-03 efter at have bekræftet (BUGS.md #32) at 4 konkrete danske DVD-stregkoder manglede i alle andre kilder. UPCDatabase.org's egen database har heller ikke haft data for netop de 4 test-stregkoder, men er tilføjet alligevel som et gratis, lavt-risiko ekstra forsøg — kan hjælpe for andre plader/nordiske udgivelser end de specifikt testede.

- **Base URL**: `https://api.upcdatabase.org/product/{barcode}`
- **Auth**: **Påkrævet** personal API key (`UPCDATABASE_TOKEN` i `.env`, eller admin-sat i UI'et under Indstillinger → System-indstillinger — oprettes med egen konto på https://upcdatabase.org/api) som `Authorization: Bearer <token>`-header. Gratis niveau: 100 opslag/dag. I modsætning til Discogs (hvor token blot hæver rate-limit) springes selve opslaget helt over hvis intet token er sat, i stedet for at forsøge et uautoriseret kald der alligevel vil få 403.
- **Request**: `GET /{stregkode}` (ren sti-parameter, ingen query-string)
- **Response**: `{"success": true, "title": "...", ...}` ved match. `success: false` eller manglende `title` → intet gæt.
- **Fejlhåndtering**: samme filosofi som UPCitemdb/Discogs — manglende token, 404 (intet match), 400 (ugyldig stregkode), netværksfejl eller enhver anden ikke-200-status logges og returnerer `None`, aldrig en kastet exception (nice-to-have forudfyld, ikke kritisk sti). **BUGS.md #37**: et ugyldigt token giver *også* HTTP 200 med `success: false` — identisk med et ægte "intet match", bortset fra et ekstra `error.apikey`-felt i svaret. `lookup_title` tjekker eksplicit for dette feltet og logger en `WARNING` ("token afvist") i stedet for den almindelige `INFO` ("intet match") i så fald.

### EAN-Search.org (fallback, feature #76)

Implementeret i `backend/app/integrations/ean_search_client.py`. Fjerde og sidste stregkode-opslags-fallback, forsøgt kun når UPCitemdb, Discogs og UPCDatabase.org alle tre missede — Jans egen betalte konto (2026-08-03), købt i håb om bedre dansk/nordisk EAN-dækning end de tre gratis kilder.

- **Base URL**: `https://api.ean-search.org/api`
- **Auth**: **Påkrævet** personal API-token (`EAN_SEARCH_API_KEY` i `.env`, eller admin-sat i UI'et under Indstillinger → System-indstillinger — Jans egen betalte konto, ingen gratis niveau) som `token`-query-parameter. Springes helt over hvis intet token er sat, samme princip som UPCDatabase.org.
- **Request**: `GET /api?token=<token>&op=barcode-lookup&format=json&ean=<stregkode>`
- **Response**: en JSON-liste. Match: `[{"ean": "...", "name": "Artist, Titel", ...}]` — `name` bruges som titel-gæt. Intet match: tom liste `[]`. Ugyldigt token: `[{"error": "Invalid token"}]`.
- **Fejlhåndtering**: samme "skelnen mellem afvist token og ægte tomhed"-princip som UPCDatabase.org (BUGS.md #37) — et `error`-felt i svaret logges som `WARNING`, en tom liste som almindelig `INFO`-"intet match". Netværksfejl/ikke-200-status logges og returnerer `None`, aldrig en kastet exception.

### Plex (tilgængeligheds-integration, feature #45 → omlagt i feature #88)

Implementeret i `backend/app/integrations/plex_client.py` + `app/services/plex_service.py`. **Ikke** en metadata-kilde som TMDb/UPC/Discogs — bruges udelukkende til at afgøre om noget brugeren allerede har katalogiseret *også* ligger i deres egen, selv-hostede Plex-server, og i så fald linke direkte til at afspille det der. Kataloget er stadig ikke en medieserver (bevidst fravalgt) — dette er en tynd bro til en Plex-installation brugeren allerede kører.

#### Konfiguration i denne app

| Indstilling | Hvor | Påkrævet | Beskrivelse |
|---|---|---|---|
| `PLEX_SERVER_URL` | `.env` eller Indstillinger → System-indstillinger | **ja** | LAN-adressen på Plex-serveren, fx `http://192.168.1.50:32400`. Ikke en hemmelighed — vises med sin faktiske værdi (se ARCHITECTURE.md). |
| `PLEX_TOKEN` | `.env` eller Indstillinger → System-indstillinger | **ja** | `X-Plex-Token`. Skriv-kun, aldrig eksponeret til frontend. |
| `PLEX_CACHE_TTL_SECONDS` | `.env` (default `300`) | nej | Hvor længe det hentede Plex-index genbruges. `0` slår cachen fra (ét fuldt hent pr. sideindlæsning — frarådes). |
| `PLEX_VERIFY_SSL` | `.env` (default `true`) | nej | Sæt `false` hvis URL'en er `https://` mod en rå LAN-IP: Plex' certifikater udstedes til `*.plex.direct` og validerer derfor ikke. Trafikken er stadig krypteret, værtsnavnet bare ikke verificeret. Er ikke nødvendig ved `http://`. |

Badget slås til pr. bruger under **Vis felter → Plex** i Bibliotek og TV-serier (fra som standard). Fejlsøgning: Indstillinger → Nøgler → **Plex-forbindelse (fejlsøgning)**.

#### Hvad der skal være på plads i selve Plex

1. **Et token med adgang til bibliotekerne.** Findes via Plex' egen vejledning "Finding an authentication token / X-Plex-Token" — det er *ikke* Plex-konto-adgangskoden. Et token fra en delt/begrænset bruger ser kun de biblioteker den bruger har adgang til; `/library/sections` returnerer så en tom liste, hvilket fejlsøgnings-panelet melder eksplicit.
2. **Serveren skal kunne nås fra backend-værten** på den angivne adresse/port (typisk 32400). "Remote access" behøver ikke være slået til — al trafik går over LAN.
3. **Film- og TV-bibliotekerne skal bruge en agent der giver TMDb-id'er** — "Plex Movie" og "Plex TV Series" (de nyere agenter) gør det. Bruger et bibliotek en ældre agent (`com.plexapp.agents.imdb` m.fl.), findes der ingen TMDb-id'er at matche entydigt på, og matchningen falder tilbage på titel+år. Det virker, men er mindre sikkert. Fejlsøgnings-panelets kolonne "Med TMDb-id" viser præcis hvor mange elementer i hver sektion der har ét.
4. **Ingen indstilling i Plex skal ændres** ud over det. Der skrives aldrig til Plex — integrationen er udelukkende læsende.

#### Sådan finder du dit Plex-token

1. Åbn Plex i browseren (`http://<din-plex-server>:32400/web`), klik på en vilkårlig film eller serie.
2. **⋮** → **Get Info** → **View XML** nede i venstre hjørne.
3. Der åbner en fane med XML — værdien efter `X-Plex-Token=` i adresselinjen er tokenet.

Alternativt direkte på serveren: `PlexOnlineToken`-attributten i `Preferences.xml` (Linux: `/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml`; Windows: `%LOCALAPPDATA%\Plex Media Server\Preferences.xml`).

Det er et **konto**-token, ikke et server-token: det giver adgang til præcis de biblioteker den konto kan se. Bruger du en begrænset/delt konto, kommer `/library/sections` tilbage tom, hvilket fejlsøgnings-panelet melder eksplicit.

#### Endpoints der bruges

- `GET /` — `friendlyName`, `version` og `machineIdentifier` (sidstnævnte indgår i afspilnings-linket).
- `GET /library/sections` — sektionslisten; kun `type: "movie"` og `type: "show"` bruges.
- `GET /library/sections/{key}/all?includeGuids=1` — alle elementer i en sektion, hentet sidevist med `X-Plex-Container-Start`/`-Size` (500 ad gangen, maks. 40 sider). `includeGuids=1` er det der overhovedet får `Guid`-listen med; uden den er der ingen TMDb-id'er at matche på.
- **Afspilnings-link**: `{server}/web/index.html#!/server/{machineIdentifier}/details?key=%2Flibrary%2Fmetadata%2F{ratingKey}` — Plex-serverens egen indbyggede web-UI, ikke `app.plex.tv` (undgår internet-/plex.tv-konto-afhængighed, matcher "selv-hostet på hjemmenetværk"-modellen resten af appen bruger).

#### Matchning

I faldende sikkerhed, og hvilken regel der ramte følger med i svarets `matched_by`:
1. **TMDb-id** fra elementets `Guid`-liste (`tmdb://603`) eller en legacy-agents `guid`-streng (`com.plexapp.agents.themoviedb://603`).
2. **Normaliseret titel + år**, med ±1 års tolerance (Plex følger ofte den lokale udgivelse, TMDb premieren). Normalisering = små bogstaver, accenter og tegnsætning væk, indledende artikel (`the`/`den`/`et`/…) væk.
3. **Normaliseret titel alene** — kun når den er entydig i Plex. To film der begge hedder "Batman" giver bevidst *intet* match frem for et tilfældigt af dem.

Film og TV-serier matches aldrig på tværs af hinanden.

#### Import (feature #90)

`POST /api/plex/import` opretter alt Plex har som portalen ikke har. Samme matchning som ovenfor, blot i modsat retning — se ARCHITECTURE.md. Plex-elementer uden TMDb-id slås op via `/search/movie` eller `/search/tv` og importeres kun ved præcis ét resultat med samme normaliserede titel og samme år. TV-serier henter derudover `/library/metadata/{ratingKey}/children` for at markere de sæsoner der ligger på serveren som ejede. Der skrives aldrig til Plex — også importen er ren læsning.

Importerede poster får `media_type: Digital` (feature #91) og `format` udledt af Plex' `videoResolution`:

| Plex-værdi | Format i portalen |
|---|---|
| `4k`, `2160`, `2160p` | `D-UHD` |
| `1080`, `720` (og alt ≥ 720) | `D-HD` |
| `576`, `480`, `sd` | `D-SD` |
| ukendt/manglende | tomt (gættes ikke) |

For film står opløsningen i `Media[].videoResolution` allerede i `/all`-svaret. For serier findes den kun på episoderne, så `/library/metadata/{ratingKey}/allLeaves` bruges — det ene kald leverer både sæsonnumre (`parentIndex`) og episodernes opløsning. En serie med blandede opløsninger får den **hyppigste**, ikke den højeste: ét 4K-afsnit ud af tres gør ikke serien til en UHD-udgave. Ties brydes til fordel for højere kvalitet.

- **Fejlhåndtering**: samme filosofi som UPC/Discogs — manglende konfiguration, en utilgængelig server eller intet match giver et tomt resultat med en læsbar `error`, aldrig en kastet exception. Et 401-svar rapporteres eksplicit som "token afvist" i stedet for at blive til "ingen match".

---

## Stregkode-formater i praksis

- DVD/Blu-ray-covers i EU/DK bruger typisk **EAN-13**. Amerikanske udgivelser bruger ofte **UPC-A** (12 cifre) — EAN-13 er et superset (UPC-A = EAN-13 med et foranstillet 0). To ting sikrer i praksis at begge håndteres korrekt (BUGS.md #19):
  1. **Kamera-scanneren** (`BarcodeScanner.jsx`) begrænser `@zxing/browser`s `BrowserMultiFormatReader` eksplicit til kun `EAN_13`/`UPC_A` via `DecodeHintType.POSSIBLE_FORMATS`. Uden denne begrænsning prøver zxing *alle* symbologier den understøtter (QR, Code128, ITF, Codabar, ...) på hver frame — på et cover med flere stregkoder/grafik kunne den låse fast på støj og stille og roligt returnere et forkert tal for en helt anden symbologi, hvilket så fejlagtigt fremstod som "intet match" i UPC/Discogs.
  2. **`scan_service._alternate_upc_ean_form`** prøver automatisk den anden længde (12↔13 cifre, foranstillet/fjernet nul) hvis det først-scannede tal ikke giver noget match — dækker tilfælde hvor en lookup-tjeneste kun har koden indekseret under den ene af de to former.
