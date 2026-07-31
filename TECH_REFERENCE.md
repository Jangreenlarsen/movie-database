# Tech Reference

Konsulteres ved al teknisk implementering (jf. CLAUDE.md regel 10). Hold opdateret med nye konventioner/fund.

---

## Backend: FastAPI

- Python 3.11+ anbefalet (async/await, moderne typing).
- `backend/app/main.py`: opretter FastAPI-app, registrerer routers fra `app/api/`, sætter CORS (frontend-origin), starter/lukker MongoDB-forbindelse via lifespan-events.
- Config via `pydantic-settings` (`app/core/config.py`), læser fra `.env`: `MONGO_URI`, `TMDB_API_TOKEN`, `LOG_LEVEL`, `CORS_ORIGINS`.
- Routers i `app/api/` er tynde: validér input (Pydantic), kald service-funktion, returnér response-model. Ingen forretningslogik her (jf. ARCHITECTURE.md).
- Fejlhåndtering: brug FastAPI `HTTPException` i API-laget; service-laget kaster domæne-specifikke exceptions (fx `MovieNotFoundError`) som en exception-handler i `main.py` mapper til korrekte HTTP-statuskoder.

## Database: MongoDB

- Async driver: **Motor** (`motor.motor_asyncio.AsyncIOMotorClient`).
- Forbindelse oprettes én gang ved app-start (lifespan), genbruges via dependency injection i routers.
- Indexes oprettes ved app-start (idempotent `create_index`-kald):
  - `movies`: text-index på `title` + `overview` (til fritekstsøgning), index på `tags`, unique sparse index på `barcode`.
  - `tags`: unique index på `name`.
- Lokal udvikling uden Docker: da Docker ikke er installeret på udviklingsmaskinen pt., brug enten **MongoDB Atlas' gratis M0-cluster** (nemmest, ingen lokal installation) eller installer MongoDB Community Server direkte. `MONGO_URI` i `.env` peger på hvilken som helst af de to.

## Frontend: React + Vite (PWA)

- Scaffold via `npm create vite@latest frontend -- --template react`.
- PWA: `vite-plugin-pwa` genererer service worker + kobler `public/manifest.json` sammen. Kræver HTTPS (eller `localhost`) for at kamera-API'et (`getUserMedia`) virker — i produktion derfor reverse proxy med TLS foran frontend (fx Caddy/Traefik/nginx med Let's Encrypt, eller self-signed cert på lokalt netværk).
- `manifest.json`: `display: "standalone"`, ikon-sæt til iOS home-screen (`apple-touch-icon` i `index.html` — iOS Safari respekterer ikke altid manifest-ikoner alene).
- API-client i `src/api/`: centraliseret `fetch`-wrapper mod backend `/api`, ingen komponent kalder `fetch` direkte.

### Stregkode-scanning i browseren
- Anbefalet lib: **`@zxing/browser`** (ren JS/TS, ingen native afhængighed, understøtter UPC-A + EAN-13 via kamera-stream).
- Flow: `BrowserMultiFormatReader.decodeFromVideoDevice(...)` mod et `<video>`-element bundet til `getUserMedia`-stream; på match sendes koden til `POST /api/scan/lookup`.
- iOS Safari-quirks: kræver eksplicit brugerinteraktion (tryk "start scan") før kamera-adgang tillades; test på faktisk iPhone, ikke kun desktop Safari-simulator.

## Deployment: Docker Compose

- Tre services: `backend` (FastAPI + Uvicorn), `frontend` (bygget statisk build serveret via nginx, eller Vite preview), `mongo` (officielt `mongo` image med named volume for persistens).
- `.env` (git-ignoreret) leverer secrets til `backend`-servicen via `env_file`.
- Se `docker-compose.yml` i repo-rod for den konkrete opsætning.

## Test-strategi (efterhånden som features implementeres)
- Backend: `pytest` + `httpx.AsyncClient` mod FastAPI-app (ingen ægte MongoDB i unit-tests — brug `mongomock` eller en test-database).
- Frontend: komponent-tests efter behov (fx `vitest` + `@testing-library/react`) for søge-/tag-filtrering-logik.
