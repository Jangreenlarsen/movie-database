# Projekt: Movie Database App

Dette er Claudes system-prompt for dette projekt. Den læses altid først og følges uden undtagelser.

**Sprog**: Claude svarer Jan på **dansk** i chatten — ikke kun i commit-beskeder, kodekommentarer og FEATURES.md/BUGS.md/CHANGELOG.md-entries, som allerede er dansksprogede. Kode, filstier og tekniske termer forbliver naturligvis på engelsk hvor det er normalt (variabelnavne, kommandoer, fejlbeskeder fra tredjepartsværktøjer). (Jan, 2026-08-18: *"husk vi taler DK"*.)

---

## Projektbeskrivelse

En **film- & TV-database webapp** til at katalogisere en fysisk/digital film- og TV-serie-samling, bygget med **React (Vite, PWA)** frontend, **Python/FastAPI** backend og **MongoDB** database. Film og TV-serier er to bevidst adskilte ressourcer (egne MongoDB-collections, egen fane hver — Jans eksplicitte ønske 2026-08-02, se FEATURES.md #47), ikke ét fælles "medie"-begreb — de deler kun det de reelt har til fælles (tags, format/lyd/medietype, lokation/ejer/serienummer, personlig rating/note, admin-nøgle-mønsteret), ikke datamodel eller CRUD-lag.

Brugeren opbygger sit bibliotek ved enten at oprette film/serier manuelt, eller ved at **scanne stregkoden (UPC/EAN) på DVD/Blu-ray-covers** med iPhonens kamera direkte i browseren (ingen native app nødvendig — kræver HTTPS for kamera-adgang). Den scannede kode slås op i en UPC-opslagstjeneste for at forudfylde en titel, hvorefter rig metadata hentes fra **TMDb (The Movie Database)** — fra *begge* TMDb's film- og TV-databaser samtidig, da et scannet cover lige så vel kan være en TV-serie-boks (se BUGS.md #20) — til brugerens bekræftelse, før filmen/serien gemmes. TV-serier får derudover sæson-niveau ejerskabs-markering og episode-niveau set-status, hentet lazily fra TMDb pr. sæson (se ARCHITECTURE.md).

Hver film/serie kan tildeles frie, **brugerdefinerede tags** (fx "Julefilm", "Set med Anna", "4K", "Skal ses igen"). Tags er — sammen med fritekstsøgning på titel/skuespiller/genre — den primære søge- og filtreringsmekanisme i biblioteksvisningerne.

**Primær use case**: Hurtigt katalogisere en fysisk film-/TV-samling ved at scanne covers med telefonen, og bagefter genfinde dem via fritekst-søgning eller tags fra enhver enhed på netværket.

**Reference-stack**:
- **Frontend**: React + Vite, PWA (installérbar på iPhone hjemmeskærm via "Føj til hjemmeskærm", HTTPS krævet for kamera-adgang)
- **Backend**: Python 3.x + FastAPI (async), Pydantic-modeller
- **Database**: MongoDB (film-/TV-serie-dokumenter i hver sin collection, tags, cache af ekstern metadata)
- **Stregkode-scanning**: klient-side JS i browseren via `getUserMedia` + en barcode-detection-lib (fx `@zxing/browser`)
- **Eksterne API'er**: TMDb (film- og TV-metadata + posters), en UPC-opslagstjeneste (stregkode → produkt/titel-gæt)
- **Deployment**: selv-hostet, **native under systemd** på en dedikeret Debian-VM (MongoDB, FastAPI/uvicorn, Caddy) — *ikke* Docker Compose; `docker-compose.yml` er et uverificeret scaffold der aldrig er taget i brug (se regel 17). Publiceret på internettet som `movie.laces.dk` via en separat nginx-reverse-proxy-VM, som er klienternes eneste vej ind; appserveren selv sidder på et isoleret transport-subnet. Se [INFRASTRUCTURE.md](INFRASTRUCTURE.md) for topologien og [DEPLOYMENT.md](DEPLOYMENT.md) for driften.

---

## Faste regler

1. **Versionering (UFRAVIGELIG)**: Projektet versioneres via [version.json](version.json). Denne fil er den **eneste** kilde til versionsnumre — alle andre steder (backend, frontend, changelog) læser herfra.
   - Normalt format: `{ "version": "MAJOR.MINOR.PATCH", "build": "NNNN" }`
   - **build**: incrementeres med **1** ved HVERT commit med kodeændringer (0001 → 0002 → ...).
   - **PATCH**: incrementeres ved bug fixes (afsluttede). Build nulstilles IKKE.
   - **MINOR**: incrementeres ved nye features. PATCH sættes til 0.
   - **MAJOR**: incrementeres ved breaking changes (fx skema-ændringer i MongoDB der kræver migration) eller store milepæle. MINOR og PATCH sættes til 0.
   - **Debugging-format (4 decimaler)**: Under aktiv fejlsøgning bruges `MAJOR.MINOR.PATCH.D` hvor D starter på 1 og incrementeres for hvert debug-commit: `v0.1.0.1`, `v0.1.0.2`, osv. Commit-beskeder præfikses `vX.X.X.D-bNNNN: debug: beskrivelse`.
   - **Afslutning af debugging**: Når Jan bekræfter *"nu virker det som det skal"*, incrementeres PATCH og D nulstilles: `v0.1.0.3` → `v0.1.1.0`. Commit markeres som `fix:` og afslutter debug-serien.
   - **Kun-dokumentations-commits** (RELEASE_NOTES.md, CHANGELOG.md, BUGS.md, FEATURES.md uden kodeændringer): bump IKKE version — lav commit uden versionsbump.
   - **RELEASE_NOTES.md skal opdateres ved ETHVERT commit der ændrer kode** — features, bugfixes og debug-afslutninger. Dokumentations-commits er undtaget. Glem aldrig dette.
   - Changelog-entries tagges med versionsnummer: `## [0.1.0 build 0001] — 2026-07-31 — beskrivelse`.
   - Claude **skal** opdatere `version.json` og vise den nye version i commit-beskeden.

2. **Ny funktionalitet (features)** skal ALTID registreres i [FEATURES.md](FEATURES.md) *før* implementering påbegyndes. Opdatér status når den er færdig.

3. **Bugs** skal ALTID registreres i [BUGS.md](BUGS.md) så snart de opdages. Opdatér med løsning når de er fikset.

4. **Alle kodeændringer** skal logges i [CHANGELOG.md](CHANGELOG.md) med version, dato, berørte filer og kort beskrivelse. Nyeste øverst.

5. **Lag-arkitekturen** beskrevet i [ARCHITECTURE.md](ARCHITECTURE.md) skal respekteres til enhver tid:
   - Frontend taler **kun** med backendens REST API — aldrig direkte med MongoDB, TMDb eller UPC-tjenesten.
   - API-laget (FastAPI routers) kalder **kun** service-laget.
   - Service-laget kalder repository-laget (MongoDB) og integrations-laget (TMDb/UPC) — aldrig omvendt.
   - Kun integrations-laget må foretage HTTP-kald til eksterne API'er.

6. **Eksterne API-nøgler (UFRAVIGELIG)**: TMDb-, UPC-, Discogs- og Plex-nøgler har to legitime opbevaringssteder: backendens `.env` (git-ignoreret, bootstrap-fallback) og — siden feature #36 (udvidet med Plex i feature #45) — en admin-only overstyring i MongoDB (`system_settings`-collection), sat via Indstillinger-siden i UI'et. Uanset kilde gælder: de må ALDRIG committes, logges i klartekst eller sendes tilbage til frontend — hverken i en `GET`- eller `PATCH`-response. Enhver endpoint der eksponerer nøgle-status til frontend må **kun** returnere om en nøgle er sat og hvorfra (`env`/`custom`/`unset`), aldrig selve værdien; sætning af en ny værdi er en skriv-kun handling (payload ind, aldrig ud igen). Eneste bevidste undtagelse er `plex_server_url` — en LAN-adresse, ikke en hemmelighed, og returneres derfor med sin faktiske værdi. Frontend kalder udelukkende egne backend-endpoints — aldrig TMDb/UPC/Discogs/Plex direkte.

7. **Tags**: Tags er fritekst, normaliseres (trim + lowercase) ved gem og sammenligning for dedup, men vises i den formatering brugeren indtastede første gang. Der vedligeholdes en samlet tag-collection til autocomplete. Bibliotekets søgning skal understøtte kombination af fritekst (titel/skuespiller/genre) og tag-filtrering (en eller flere tags samtidig).

8. **REST API-kontrakt**: Se [ARCHITECTURE.md](ARCHITECTURE.md) for komplet endpoint-tabel. Nye ressourcer/endpoints tilføjes altid i den tabel *før* implementering, og navngives ressource-orienteret (`/api/movies`, `/api/tags`, ...) — ikke handling-orienteret.

9. **Film- og stregkode-reference**: [MOVIE_API_REFERENCE.md](MOVIE_API_REFERENCE.md) indeholder TMDb- og UPC-opslags-endpoints, rate-limits, felt-mapping og fejlhåndtering (fx "intet UPC-match" eller "flere TMDb-kandidater"). Konsultér og hold opdateret ved al integration med eksterne film-API'er.

10. **Tech-reference**: [TECH_REFERENCE.md](TECH_REFERENCE.md) indeholder FastAPI-konventioner, MongoDB-skemaer/indexes, React/PWA-opsætning (manifest, service worker), og kamera/stregkode-scanning-implementation. Konsultér ved al teknisk implementering.

11. **Runtime-logging**: Backend skal logge alle eksterne API-kald (TMDb/UPC) samt fejl via Python `logging`-modulet med struktureret kontekst (fx UPC/TMDb-id). Log-niveau konfigureres via miljøvariabel (`LOG_LEVEL`).

12. **Read/write rettigheder**: Claude har forhåndsgodkendelse (via [.claude/settings.local.json](.claude/settings.local.json)) til at læse, skrive og redigere filer i projektmappen. Samme forhåndsgodkendelse dækker **alle kommandoer der er relevante for at køre og teste projektet** — uden at spørge først: `pytest` (backend), `npm test`/`npm run lint`/`npm run build` (frontend), samt at starte/stoppe `uvicorn`/`npm run dev` lokalt til visuel verifikation (regel 18). Kun ægte destruktive handlinger (force-push, `git reset --hard`, sletning af andet end egne midlertidige testdata) kræver stadig eksplicit accept, jf. [.claude/settings.local.json](.claude/settings.local.json)'s `deny`-liste.

13. **Versionskontrol**: Projektet er et git-repo. Efter enhver logisk afsluttet ændring skal Claude lave en git commit med en beskrivende commit-besked. Aldrig bulk-commits af urelaterede ændringer.

14. **GitHub branch-strategi (UFRAVIGELIG)**:
    - `dev` — aktiv udviklingsbranch. **Al ny kode commites hertil.** Claude arbejder altid på `dev`.
    - `main` — stabil release-branch. Kun opdateret via PR/merge fra `dev` når en release er klar. Produktion følger `main`.
    - Claude skal pushe til `origin dev` efter hvert commit — aldrig direkte til `main`.
    - Merge `dev` → `main` gøres manuelt af Jan når en release er godkendt.

15. **Push og merge efter commit (UFRAVIGELIG)**: Efter ethvert commit skal Claude automatisk:
    - Pushe til `origin dev` — **uden at spørge først**
    - Spørge Jan: *"Vil du også merge til `main` og pushe?"*
    - Hvis ja: merge `dev` → `main` med `--no-ff` og pushe `origin main`
    - Hvis nej: forblive på `dev` og informere om at `main` ikke er opdateret
    - Svarer Jan blot *"main"*, betyder det ja til hele kæden (push `dev` → merge → push `main`), ikke kun det ene led.
    - **Historik**: reglen blev 2026-08-08 kortvarigt ændret til at kræve accept før *enhver* GitHub-skrivning, da Jan bad om det samtidig med at han gav Claude bypass-rettigheder lokalt. Han rullede det tilbage samme dag efter at have set hvor ofte det afbrød ham (*"vi skal ikke have ask på alt med"*). `main` kræver fortsat hans ord — det er dér produktionen følger med.

16. **Kodekvalitets-foranalyse (UFRAVIGELIG)**: Dette er en fast metode Claude *altid* anvender — både løbende mens der skrives ny kode, og som selvtjek før en feature/fix meldes færdig. Opstod af en systematisk to-fase-gennemgang (2026-08-01) der fandt gentagne instanser af de samme underliggende fejlmønstre; punkterne nedenfor er de generaliserede lektioner, ikke kun de konkrete bugs de blev fundet ud fra:
    - **Null/fejl-propagering**: ethvert kald til en repository- eller service-funktion der kan returnere `None`/`null` eller kaste en fejl, skal have sit resultat tjekket af den kaldende kode *før* det bruges (fx `document.get(...)` på et resultat der kan være `None`). Antag aldrig succes.
    - **Fejlbeskeder til brugeren**: frontend skal *altid* vise den specifikke fejlbesked fra backend (`err.message`), aldrig kun en generisk besked, når en specifik findes. Enhver `catch`-blok omkring et API-kald skal enten vise fejlen eller have en eksplicit, begrundet kommentar om hvorfor den bevidst undertrykkes.
    - **Adgangskontrol-lockout**: permission-/rolle-systemer skal altid beskyttes mod at ende i en tilstand uden nogen med adgang til at rette det igen (fx sidste admin fjernet). Håndhæv den slags regler i **backend**, ikke kun som en UI-bekvemmelighed der er triviel at omgå.
    - **Eksterne API'er og "tomhed"**: brug `is not None` — aldrig ren Python/JS-truthiness — for tal- eller valgfri-felter der lovligt kan være `0`/tomme (fx en rating på `0.0`). Håndtér altid et catch-all for uventede fejlstatusser fra eksterne API'er (ikke kun de statuskoder man tilfældigvis har tænkt på), så de mapper til en pæn fejl i stedet for en rå 500.
    - **"Tomhed"-repræsentationer generelt**: når en bug rettes for én repræsentation af "tom" (fx `null`), tjek samtidig alle andre ækvivalente repræsentationer (tom streng, whitespace-only) for samme klasse fejl — ret hele klassen, ikke kun den rapporterede instans.
    - **Sikkerhedskonfiguration**: usikre default-værdier (hemmeligheder, nøgler, adgangskoder) skal advare eller nægte at starte hvis de stadig er i brug ved opstart — aldrig glide stille igennem til en kørende instans.
    - **Samtidige delvise opdateringer ("last write wins")**: en service-funktion der opdaterer et dokument må aldrig læse hele dokumentet, ændre ét felt i hukommelsen og skrive det hele tilbage igen ("read-modify-write") hvis flere sådanne kald kan ske i hurtig rækkefølge uden kø (typisk fra en frontend der sender flere uafhængige PATCH-kald på kort tid). Brug i stedet punktum-sti `$set` (kun de faktisk ændrede felter) så to samtidige kald der rører *forskellige* felter aldrig kan overskrive hinandens skrivning, uanset rækkefølge (jf. BUGS.md #13).
    - **Bulk-operationer mod eksterne API'er**: når en handling itererer over mange elementer og kalder en ekstern API for hvert (fx en "synkroniser alt"-funktion), skal fejl der rammer *hele batchen* (manglende/ugyldig API-nøgle, rate-limit) håndteres adskilt fra fejl der kun rammer ét element. Tjek forudsætninger (API-nøgle sat) *før* løkken startes i stedet for at lade hvert element fejle for samme grundårsag, og stop batchen med det samme ved et rate-limit-svar i stedet for at blive ved med at forsøge resten mod en allerede-blokeret API (jf. BUGS.md #15/#16).
    - **Test i den faktiske runtime-kontekst, ikke kun logikken**: når en funktion skal køre under en bestemt runtime-sandkasse/isolation (fx en systemd-service med `ProtectSystem=strict`/`NoNewPrivileges=true`, en container, en begrænset bruger), er det ikke nok at teste logikken i et almindeligt/privilegeret shell — det kan give falsk tryghed, fordi sandkassen kan blokere ting (filskrivning, `sudo`, netværk) som slet ikke rammes af den manuelle test. Verificér i stedet direkte i den kontekst koden rent faktisk kører i produktion (fx via `nsenter` ind i den kørende proces' namespace, eller ved at udløse den rigtige, sandboxede vej end-to-end) *før* en feature der afhænger af servicens egne rettigheder meldes færdig (jf. BUGS.md #18 — OTA-deploy-featuren blev "verificeret" via et almindeligt SSH-shell, hvilket skjulte to reelle sandbox-relaterede fejl der først viste sig ved Jans egen brug).
    - **Rammeværkets fejl har en anden form end vores egne**: når et lag oversætter fejl til noget brugeren kan læse, dækker det typisk kun de fejl vi selv kaster. Rammeværket kaster sine egne, i sit eget format, ad samme vej — og de rammer først når nogen indtaster noget forkert. Tjek derfor eksplicit *begge* former, ikke kun den kode selv producerer (jf. BUGS.md #54: `HTTPException` giver `detail` som en streng, mens FastAPIs validering giver en **liste** af objekter; frontend gav listen direkte til `new Error(...)` og viste brugeren "[object Object]" ved enhver valideringsfejl i hele appen).
    - **Regler der kun gælder én gren**: når en regel indføres for ét tilfælde (kun ved oprettelse, kun for fysiske, kun for film), så gennemgå de øvrige grene *med det samme* — opdatering, den anden ressource, import-vejen. En regel der kun holder halvvejs opdages typisk først som en fejlmelding fra Jan (jf. BUGS.md #52: kravet om `format` blev håndhævet ens for film og serier, men kun film havde deres opløsning ved hånden, så hele TV-kategorien blev stiltiende sprunget over ved Plex-import).
    - Ved større funktioner (auth, permissions, betalinger, data-integritet) skal Claude proaktivt overveje disse punkter under implementering, ikke først vente på at Jan beder om en fejl-gennemgang.

17. **Produktions-deployment**: [DEPLOYMENT.md](DEPLOYMENT.md) indeholder den bindende reference for hvordan produktion faktisk kører (native services på en dedikeret Debian-server — MongoDB, backend via systemd/uvicorn, Caddy som reverse proxy/TLS — *ikke* `docker-compose.yml`, som er et uverificeret scaffold). Konsultér og hold opdateret ved enhver ændring der påvirker hvordan appen deployes, opdateres eller driftes (nye systemd-services, nye miljøvariabler, ændret portbrug osv.).

18. **Visuel verifikation af layout-ændringer (UFRAVIGELIG)**: en ændring af *placering* — absolut positionering, flex/grid-containere, hjørne-grupper, z-index, ombrydning — skal ses i browseren før den meldes færdig. `npm run build` og `npm run lint` kan ikke fange den slags: JSX og CSS er hver for sig gyldige, og det er kun kombinationen der er forkert. Regel 16's "test i den faktiske runtime-kontekst" gælder også her, og browseren *er* runtime-konteksten for layout. Jf. BUGS.md #53, hvor en absolut placeret gruppe kom til at indeholde et absolut placeret panel: panelets bredde blev derefter regnet mod gruppens få pixels, login-boksen blev mast sammen, og både build og lint var grønne hele vejen. Brug `/run`-skillen eller start dev-serveren og kig — og sig eksplicit i afrapporteringen om ændringen er set eller kun bygget.

19. **Frontend-tests**: `frontend/src/**/*.test.{js,jsx}` køres med `npm test` (Vitest + Testing Library, feature #103). Ny frontend-logik der kan gå galt uden at nogen opdager det — fejlbesked-oversættelse, formatering, oversætter-fallback, tilstands-skift i et vindue — skal have en test. Rene visuelle ændringer skal ikke; til dem gælder regel 18 i stedet. Katalog-testene i `i18n.test.js` fanger manglende oversættelser og pladsholdere på tværs af sprog og skal blive ved med at dække begge kataloger.

20. **Backup/restore skal følge med systemet (UFRAVIGELIG)**: hver gang en feature ændres eller oprettes, og den tilføjer eller udvider et data-sæt (en ny collection, et nyt felt på en eksisterende collection, en ny relation mellem collections), skal backup/restore-funktionen (`library_backup_service.py`/`system_backup_service.py` + tilhørende modeller/endpoints) gennemgås som en del af det samme stykke arbejde — *ikke* som en separat, senere opgave. Tjek konkret: (a) bliver det nye/udvidede data-sæt inkluderet i en backup, eller går det stiltiende tabt? (b) bliver det korrekt genskabt ved restore, inklusive eventuelle nye felter på eksisterende dokumenter? (c) er der nye relationer (fx en reference til et andet dokument) som restore skal genoprette i rigtig rækkefølge eller mappe om (id'er der ændrer sig)? Opdag denne slags huller *før* Jan gør (jf. regel 16's generelle princip: en regel/funktion der kun holder for de dele af systemet den blev skrevet til, opdages typisk først som en fejlmelding). Er der et hul, ret det som en del af samme feature — det er ikke acceptabelt at aflevere en feature hvor data findes i systemet, men ikke i en backup.

---

## Workflow for enhver opgave

1. Tilføj entry i `FEATURES.md` (feature) eller `BUGS.md` (bug).
2. Implementer ændringen i det korrekte lag jf. `ARCHITECTURE.md`.
3. Opdater `version.json`: bump build (altid), bump version (hvis feature/bugfix/breaking).
4. Tilføj entry i `CHANGELOG.md` med `[version build NNNN]` prefix.
5. Opdater `RELEASE_NOTES.md` hvis kode er ændret.
6. Kør **begge** testsuiter før noget meldes færdigt: `cd backend && ./.venv/Scripts/python.exe -m pytest -q` og `cd frontend && npm test`. Frontend havde ingen suite indtil feature #103; "hvis relevant" gælder derfor ikke længere som undskyldning for at springe den over. Rør ændringen ved layout eller placering, gælder desuden regel 18.
7. `git add` + `git commit` med besked der inkluderer version: `v0.1.0-b0001: beskrivelse`.
8. `git push origin dev` til GitHub.
9. Spørg Jan: *"Vil du også merge til `main`?"* — merge og push `origin main` hvis ja.

---

## Stregkode & Film-metadata Quick Reference

### Flow ved scanning
```
Scan cover (UPC/EAN) → UPC-opslag (titel-gæt) → TMDb-søgning på gættet titel
 → bruger bekræfter match (poster + år vises) → gem film + metadata-cache i MongoDB
```
- Understøttede stregkode-formater: **UPC-A** og **EAN-13** (de mest almindelige på DVD/Blu-ray-covers).
- **Intet UPC-match**: brugeren falder tilbage til direkte TMDb-titel-søgning.
- **Flere TMDb-kandidater**: vis top-resultater (poster + år) og lad brugeren vælge.
- TMDb-metadata caches i MongoDB ved gem, så samme film ikke slår op igen ved visning.

### Registerdata pr. film (MongoDB-dokument, overblik)
| Felt          | Kilde                          | Noter                              |
|---------------|--------------------------------|-------------------------------------|
| `barcode`     | Scannet af bruger               | UPC/EAN, valgfri (manuel oprettelse har ingen) |
| `tmdb_id`     | TMDb-søgning                    | Bruges til at genhente/opdatere metadata |
| `title`, `year`, `poster_url`, `overview`, `genres`, `cast` | TMDb | Cachet lokalt |
| `tags`        | Bruger                          | Fritekst, normaliseret til søgning |
| `created_at`, `updated_at` | Backend            | Timestamps |

---

## Projektstruktur

```
.
├── CLAUDE.md                  # denne fil — regler Claude altid følger
├── version.json               # SINGLE SOURCE OF TRUTH for version + build
├── ARCHITECTURE.md            # lag-struktur, REST endpoint-tabel og arkitekturregler
├── MOVIE_API_REFERENCE.md     # TMDb + UPC-opslag API-reference
├── TECH_REFERENCE.md          # FastAPI/MongoDB/React-PWA/scanning-reference
├── FEATURES.md                # features (planned / in-progress / done)
├── BUGS.md                    # bugs (open / fixed)
├── CHANGELOG.md               # alle kodeændringer, nyeste øverst
├── RELEASE_NOTES.md           # brugervenlige release-noter
├── DEPLOYMENT.md              # produktions-drift (native Debian-server, ikke Docker — se regel 17)
├── docker-compose.yml         # uverificeret scaffold, IKKE brugt i produktion (se DEPLOYMENT.md)
├── .claude/
│   └── settings.local.json    # Claude-rettigheder
├── backend/                   # FastAPI-app
│   ├── app/
│   │   ├── main.py            # app-init, router-registrering
│   │   ├── core/              # config (Pydantic Settings), logging
│   │   ├── api/                # REST-routers pr. ressource (movies, tv_shows, tags, scan, search)
│   │   ├── services/           # forretningslogik
│   │   ├── integrations/       # tmdb_client.py, upc_client.py
│   │   ├── repositories/       # MongoDB data-access (Motor)
│   │   └── models/             # Pydantic schemas
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
└── frontend/                   # React (Vite) PWA — taler kun med backend API
    ├── src/
    │   ├── api/                 # backend API-client (fetch-wrapper)
    │   ├── components/          # genanvendelige UI-komponenter
    │   ├── i18n/                 # oversætter + da.json/en.json (feature #89)
    │   ├── pages/                # Library, TvShows, ScanMovie, Statistics
    │   ├── scanner/              # kamera + stregkode-detection
    │   ├── utils/                # rene hjælpefunktioner (serienr., datoformat)
    │   ├── test/                 # setup.js til Vitest (feature #103)
    │   └── **/*.test.{js,jsx}    # tests ligger ved siden af det de tester
    ├── public/
    │   └── manifest.json         # PWA manifest
    ├── index.html
    ├── package.json
    ├── vite.config.js            # også Vitest-konfiguration (test-blokken)
    └── Dockerfile
```

---

## Arkitektur-lag (overblik)

```
┌───────────────────────────────────────────┐
│      Web Frontend (iOS Safari / PWA)       │  React + Vite
│   pages/  components/  scanner/  api/      │
└──────────────────┬──────────────────────────┘
                    │ HTTPS REST (JSON)
┌──────────────────┼──────────────────────────┐
│            API-lag (FastAPI routers)         │
│ /api/movies /api/tv-shows /api/tags /api/scan │
└──────────────────┬──────────────────────────┘
                    │
┌──────────────────┼──────────────────────────┐
│         Service-lag (forretningslogik)       │
│ movie_service  tv_show_service  scan_service │
└──────┬────────────────────────────┬──────────┘
       │                            │
┌──────┼──────────┐        ┌────────┼─────────────┐
│ Repository-lag  │        │  Integrations-lag     │
│ MongoDB (Motor)  │        │  TMDb-client, UPC-client │
└──────┬───────────┘        └────────┬─────────────┘
       │                             │
┌──────┼─────────┐          ┌────────┼─────────────┐
│    MongoDB      │          │  TMDb API / UPC API   │
└──────────────────┘          └───────────────────────┘
```
