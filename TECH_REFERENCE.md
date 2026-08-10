# Tech Reference

Konsulteres ved al teknisk implementering (jf. CLAUDE.md regel 10). Hold opdateret med nye konventioner/fund.

---

## Backend: FastAPI

- Python 3.11+ anbefalet (async/await, moderne typing).
- `backend/app/main.py`: opretter FastAPI-app, registrerer routers fra `app/api/`, sætter CORS (frontend-origin), starter/lukker MongoDB-forbindelse via lifespan-events.
- Config via `pydantic-settings` (`app/core/config.py`), læser fra `.env`: `MONGO_URI`, `TMDB_API_TOKEN`, `LOG_LEVEL`, `CORS_ORIGINS`, `JWT_SECRET_KEY`, `COOKIE_SECURE`.
- Routers i `app/api/` er tynde: validér input (Pydantic), kald service-funktion, returnér response-model. Ingen forretningslogik her (jf. ARCHITECTURE.md).
- Fejlhåndtering: brug FastAPI `HTTPException` i API-laget; service-laget kaster domæne-specifikke exceptions (fx `MovieNotFoundError`) som en exception-handler i `main.py` mapper til korrekte HTTP-statuskoder.

### Auth (JWT i httpOnly cookie)
- `app/core/security.py`: `bcrypt` til password-hashing, `pyjwt` til access-tokens. Token indeholder kun `sub` (bruger-id) + `exp`.
- `app/api/deps.py::get_current_user`: læser `access_token`-cookien, dekoder JWT, slår brugeren op i MongoDB. Bruges som router-level `dependencies=[Depends(get_current_user)]` på `movies`/`tags`/`scan`-routerne — ikke per-endpoint.
- **`JWT_SECRET_KEY` skal genereres unikt pr. miljø** (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) — default-værdien i koden er kun et fallback for lokal udvikling og må ALDRIG bruges i produktion.
- `COOKIE_SECURE=true` skal sættes når backend kører bag HTTPS i produktion (ellers sender browseren ikke cookien). `samesite="lax"` er brugt, hvilket virker fint til same-origin-opsætningen (frontend proxier `/api` til backend, se `vite.config.js`).
- Test-suiten logger automatisk en test-bruger ind i `client`-fixturen (`tests/conftest.py`) via en rigtig `/api/auth/register`-kald, så cookien håndteres af `httpx`'s indbyggede cookie-jar ligesom en browser ville.

## Database: MongoDB

- Async driver: **Motor** (`motor.motor_asyncio.AsyncIOMotorClient`).
- Forbindelse oprettes én gang ved app-start (lifespan), genbruges via dependency injection i routers.
- Indexes oprettes ved app-start (idempotent `create_index`-kald):
  - `movies`: text-index på `title` + `overview` (til fritekstsøgning), index på `tags_normalized`, unique sparse index på `barcode`.
  - `tags`: unique index på `normalized`.
- **Lokal udvikling (Jans maskine)**: Docker er ikke installeret, så MongoDB Community Server kører i stedet som lokal Windows-service, installeret via `winget install --id MongoDB.Server`. Kører på standard-porten `localhost:27017` — matcher default `MONGO_URI` i `.env.example` uden yderligere config. Service-status: `Get-Service MongoDB` (PowerShell).
- Alternativ uden lokal installation: **MongoDB Atlas' gratis M0-cluster** — peg `MONGO_URI` i `.env` på connection-stringen derfra i stedet.

## Frontend: React + Vite (PWA)

- Scaffold via `npm create vite@latest frontend -- --template react`.
- PWA: `vite-plugin-pwa` genererer service worker + kobler `public/manifest.json` sammen. Kræver HTTPS (eller `localhost`) for at kamera-API'et (`getUserMedia`) virker — i produktion derfor reverse proxy med TLS foran frontend (fx Caddy/Traefik/nginx med Let's Encrypt, eller self-signed cert på lokalt netværk).
- `manifest.json`: `display: "standalone"`, ikon-sæt til iOS home-screen (`apple-touch-icon` i `index.html` — iOS Safari respekterer ikke altid manifest-ikoner alene).
- API-client i `src/api/`: centraliseret `fetch`-wrapper mod backend `/api`, ingen komponent kalder `fetch` direkte.

### Sprog / i18n (feature #89)

Egen ~60-linjers motor i `frontend/src/i18n/`, ikke react-i18next — to sprog, ingen lazy-loading af sprogfiler og kun "én/flere"-flertal retfærdiggør ikke ~40 kB ekstra i en bundle der allerede advarer om sin størrelse.

| Fil | Rolle |
|---|---|
| `i18n/index.js` | `useT()`, `useLanguage()`, `useLocale()`, `LANGUAGES`, `SOURCE_LANGUAGE`, `createTranslator()`. Ingen komponenter — se næste række. |
| `i18n/I18nProvider.jsx` | Kun provider-komponenten. Adskilt fordi Vites fast refresh ikke kan opdatere en fil der blander komponenter og ikke-komponenter uden fuld genindlæsning. Sætter også `<html lang>`. |
| `i18n/da.json`, `i18n/en.json` | Flade, punktum-adskilte nøgler (`"lib.searchPlaceholder"`), ikke indlejrede objekter — en nøgle man har foran sig i JSX kan søges direkte i sprogfilen som præcis den streng. |

**Regler ved ny UI-tekst:**
- Dansk skrives først og er kildesproget. En nøgle der mangler i `en.json` falder tilbage til dansk; mangler den i *begge*, vises den rå nøgle — grimt med vilje, så en manglende oversættelse er til at få øje på frem for at gemme sig som tom tekst.
- Begge kataloger skal have samme nøglesæt og samme `{pladsholdere}` pr. nøgle. En manglende pladsholder i én oversættelse giver en halvfærdig sætning uden at fejle nogen steder.
- Interpolation: `t("key", { navn: "Anna" })` → `{navn}`. Flertal: `t("key", { count: n })` vælger `key_one`/`key_other` hvis de findes.
- **Modul-konstanter må ikke indeholde færdig tekst.** Lister som `SORT_OPTIONS`/`VISIBLE_FIELD_OPTIONS`/`settingsTabs()` evalueres ved import, før nogen oversætter findes — de bærer derfor `labelKey` og slår nøglen op ved render.
- **Rene funktioner tager `t`/`locale` som argument** frem for at kalde hooks (fx `formatRuntime`, `cinemaFormat.js`). Kun komponenter må kalde `useT()`/`useLocale()`.
- Datoer/tal: brug `useLocale()` (`da-DK`/`en-GB`), aldrig et hardkodet locale. Engelsk er bevidst `en-GB`, ikke `en-US` — dag-før-måned og 24-timers ur, som resten af appen regner med.
- `ErrorBoundary` er bevidst *ikke* oversat: den ligger uden om provideren for netop at kunne fange en fejl i den, så der er hverken context eller garanti for at brugerens indstillinger nåede at blive hentet.

### Stregkode-scanning i browseren
- Anbefalet lib: **`@zxing/browser`** (ren JS/TS, ingen native afhængighed, understøtter UPC-A + EAN-13 via kamera-stream).
- Flow: `BrowserMultiFormatReader.decodeFromVideoDevice(...)` mod et `<video>`-element bundet til `getUserMedia`-stream; på match sendes koden til `POST /api/scan/lookup`.
- iOS Safari-quirks: kræver eksplicit brugerinteraktion (tryk "start scan") før kamera-adgang tillades; test på faktisk iPhone, ikke kun desktop Safari-simulator.

### Test fra telefon over LAN (HTTPS krævet for kamera)
- `vite.config.js` sætter `server.host: true` (binder til `0.0.0.0`, ikke kun `localhost`) og `server.https` med et selvsigneret cert fra `frontend/.cert/` (git-ignoreret — genereres lokalt, committes aldrig).
- Generér cert (kør fra `frontend/`):
  ```
  mkdir .cert && cd .cert
  openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 \
    -subj "/CN=movie-database-dev" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:<din-lan-ip>"
  ```
  Find LAN-IP'en med `ipconfig` (Windows) — se efter den aktive adapters IPv4-adresse (typisk `192.168.x.x` eller `10.x.x.x`).
- `npm run dev` viser derefter både en `Local` (`https://localhost:5173`) og en `Network`-URL (`https://<lan-ip>:5173`) — sidstnævnte er den telefonen skal bruge, forudsat telefon og PC er på samme netværk.
- Selvsigneret cert ⇒ telefonens browser viser en sikkerhedsadvarsel ("Ikke privat"/"Avanceret") — accepter den for at fortsætte. Uden HTTPS blokerer browseren `getUserMedia()` fuldstændigt på alt andet end `localhost`.
- **Windows-firewall**: der skal være en indgående regel der tillader TCP på Vite-porten (5173) på det private netværksprofil, ellers kan telefonen slet ikke oprette forbindelse (`New-NetFirewallRule -DisplayName "..." -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow -Profile Private`).
- Backend (`:8000`) behøver ikke selv eksponeres til netværket — Vite's dev-proxy videresender `/api`-kald server-side til `localhost:8000` på samme maskine, usynligt for telefonen.

## Deployment: Docker Compose

- Tre services: `backend` (FastAPI + Uvicorn), `frontend` (bygget statisk build serveret via nginx, eller Vite preview), `mongo` (officielt `mongo` image med named volume for persistens).
- `.env` (git-ignoreret) leverer secrets til `backend`-servicen via `env_file`.
- Se `docker-compose.yml` i repo-rod for den konkrete opsætning.

## Test-strategi

**Backend**: `pytest` + `httpx.AsyncClient` mod FastAPI-appen, med `mongomock_motor` i stedet for en rigtig MongoDB.

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest -q
```

`conftest.py` fastlåser de eksterne API-nøgler til åbenlyst falske værdier, så suiten aldrig afhænger af udviklerens `.env` (BUGS.md #31). Bemærk at mongomock ikke implementerer alt: `$text` mangler helt (BUGS.md #48), og sparse/partielle index-regler håndhæves ikke som i produktion (BUGS.md #1) — en test kan derfor ikke bevise at et unikt index virker.

**Frontend** (feature #103): Vitest + Testing Library, konfigureret i `vite.config.js`' `test`-blok så appens egne aliasser og plugins gælder i testene uden at skulle holdes ens to steder.

```bash
cd frontend && npm test          # én kørsel
cd frontend && npm run test:watch
cd frontend && npm run test:coverage
```

Testfiler ligger ved siden af det de tester (`client.test.js` ved siden af `client.js`). `src/test/setup.js` kører før hver fil og rydder DOM'en op mellem tests.

Hvad der skal testes på frontend:
- **Logik der kan fejle stille**: fejlbesked-oversættelse (`readableDetail`), formatering (`formatSerial`), oversætter-fallback. Det er her BUGS.md #54 lå i månedsvis uden at nogen så det.
- **Katalog-konsistens**: `i18n.test.js` tjekker at `da.json` og `en.json` har samme nøgler og samme pladsholdere. En nøgle der kun findes på det ene sprog er usynlig i koden, men synlig for brugeren.
- **Tilstands-skift i komponenter**: fx at et banner bliver stående når markeringen fejler (`MessageBanner.test.jsx`) — netop de tilfælde hvor en optimistisk UI-opdatering ville lyve over for brugeren.

Hvad der **ikke** skal testes her: rent visuelle ændringer. Til dem gælder CLAUDE.md regel 18 — se på siden i en browser.
