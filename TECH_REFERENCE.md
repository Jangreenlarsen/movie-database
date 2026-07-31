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

## Test-strategi (efterhånden som features implementeres)
- Backend: `pytest` + `httpx.AsyncClient` mod FastAPI-app (ingen ægte MongoDB i unit-tests — brug `mongomock` eller en test-database).
- Frontend: komponent-tests efter behov (fx `vitest` + `@testing-library/react`) for søge-/tag-filtrering-logik.
