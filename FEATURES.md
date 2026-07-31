# Features

Status: `planned` → `in-progress` → `done`. Tilføj entry *før* implementering påbegyndes (jf. CLAUDE.md regel 2).

| # | Feature                                                        | Status  | Version |
|---|------------------------------------------------------------------|---------|---------|
| 1 | Backend-skelet: FastAPI + MongoDB-forbindelse + health check        | done | 0.1.0       |
| 2 | Frontend-skelet: React/Vite PWA, grundlæggende layout               | done | 0.1.0       |
| 3 | Film CRUD (opret/hent/opdatér/slet) mod MongoDB — metadata leveres i request, TMDb-opslag er feature #4 | done | 0.2.0       |
| 4 | Scan stregkode (UPC/EAN) med kamera → UPC-opslag → TMDb-match       | done | 0.3.0       |
| 5 | Brugerdefinerede tags: tilføj/fjern pr. film, normaliseret dedup, autocomplete-liste | done | 0.2.0       |
| 6 | Bibliotek-visning: fritekst-søgning + tag-filtrering (via `/api/movies?q=&tags=`) | done | 0.2.0       |
| 7 | Film-detaljevisning (poster, plot, cast, genre, tags, noter)           | planned | -       |
| 8 | Redigér/slet film                                                     | planned | -       |
| 9 | PWA-installation på iPhone (manifest + service worker + ikoner)        | planned | -       |
| 10| Docker Compose-deployment (backend + frontend + MongoDB)                | planned | -       |
| 11| Strukturerede valgfrie attributter (lyd-type multi-select, film-format single-select fra fast liste) + auto-tildelt fortløbende serienummer pr. film. Filtrerbare i biblioteksvisningen (`/api/movies?format=&audio_types=`) | done | 0.4.0       |
