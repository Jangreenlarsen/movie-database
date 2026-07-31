# Features

Status: `planned` → `in-progress` → `done`. Tilføj entry *før* implementering påbegyndes (jf. CLAUDE.md regel 2).

| # | Feature                                                        | Status  | Version |
|---|------------------------------------------------------------------|---------|---------|
| 1 | Backend-skelet: FastAPI + MongoDB-forbindelse + health check        | done | 0.1.0       |
| 2 | Frontend-skelet: React/Vite PWA, grundlæggende layout               | done | 0.1.0       |
| 3 | Film CRUD (opret/hent/opdatér/slet) mod MongoDB — metadata leveres i request, TMDb-opslag er feature #4 | done | 0.2.0       |
| 4 | Scan stregkode (UPC/EAN) med kamera → UPC-opslag → TMDb-match       | done | 0.3.0       |
| 5 | Brugerdefinerede tags: tilføj/fjern pr. film, normaliseret dedup, autocomplete-liste | done | 0.2.0       |
| 6 | Bibliotek-visning: fritekst-søgning + tag/format/lyd-filtrering (via `/api/movies?q=&tags=&format=&audio_types=`) | done | 0.5.0       |
| 7 | Film-detaljevisning (poster, plot, cast, genre, tags, format, lyd)      | done | 0.5.0       |
| 8 | Redigér/slet film (modal i biblioteksvisning: tags/format/audio_types + slet) | done | 0.5.0       |
| 9 | PWA-installation på iPhone (manifest + service worker + ikoner)        | planned | -       |
| 10| Docker Compose-deployment (backend + frontend + MongoDB)                | planned | -       |
| 11| Strukturerede valgfrie attributter (lyd-type multi-select, film-format single-select fra fast liste) + auto-tildelt fortløbende serienummer pr. film. Filtrerbare i biblioteksvisningen (`/api/movies?format=&audio_types=`) | done | 0.4.0       |
| 12| Moderne visuelt redesign af frontend (design-tokens, poster-grid, filter-chips, detalje-modal, scan-viewfinder)  | done | 0.5.0       |
| 13| TMDb rating pr. film (vote_average, auto-hentet ved TMDb-oprettelse). Sortering i biblioteksvisning (titel/år/tilføjet/rating, stigende/faldende). Bruger-konfigurerbar visning af hvilke felter der vises på filmkort (år/tags/format/lyd/rating), gemt i browserens localStorage | done | 0.6.0       |
| 14| Brugerlogin (brugernavn/adgangskode, åben tilmelding, JWT i httpOnly cookie). Ét fælles filmbibliotek for alle brugere — view-/filterindstillinger (sortering, synlige felter) gemmes server-side pr. bruger i stedet for localStorage. Alle `/api/movies`, `/api/tags`, `/api/scan`-endpoints kræver login. | done | 0.7.0       |
| 15| Paginering af biblioteksvisning: side-navigation + valg af antal film pr. side | planned | -       |
