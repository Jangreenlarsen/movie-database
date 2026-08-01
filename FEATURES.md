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
| 16| Settings-side: opsætning af serienummer-generatoren (næste nummer, increment, antal cifre). Redigering af en *bestemt* films serienummer sker i filmens redigeringsvindue (auto-byt ved kollision med en anden films nummer) | done | 0.9.0       |
| 17| Fler-niveau sortering i biblioteksvisning (op til 3 niveauer, fx: 1. format, 2. lyd-type, 3. titel), hvert niveau med egen retning | planned | -       |
| 18| Automatisk "Tilføjet af {brugernavn}"-tag på film ved oprettelse (uanset om det sker via scan, manuel TMDb-søgning eller ren manuel indtastning) | planned | -       |
| 19| Bruger-roller (admin/standard). Første registrerede bruger bliver automatisk admin. Admin kan liste alle brugere og forfremme/degradere roller. Serienummer-generator-opsætning kræver admin (skrivning — læsning er åben for alle). Adgangskode-ændring på Settings-siden. | done | 0.10.0       |
| 20| OTA-opdateringsfunktion fra GitHub-repo, inkl. tjek/installation af manglende afhængigheder (pip/npm) ved opdatering (kræver afklaring af deployment-model — se ARCHITECTURE.md/TECH_REFERENCE.md, feature #10 Docker Compose er stadig ikke verificeret) | planned | -       |
| 21| Adgang fra telefon over LAN (HTTPS dev-server + firewall-regel) + mobilvenligt responsivt design | done | 0.11.0       |
| 22| Versionsvisning i frontend (læst fra `version.json` via `/api/health`)  | done | 0.12.0       |
| 23| Filmkort: `runtime`-tag (minutter, fra TMDb) + 2-kolonne kompakt visning af felter (år/format/lyd/runtime) i stedet for én kolonne | done | 0.12.0       |
| 24| Klik-til-vis (som "Vis felter") for både sortering og tag/format/lyd-filterpanelet i biblioteksvisningen — begge er i dag altid synlige | done | 0.12.0       |
| 25| Lokation, automatisk "registreret af"-felt og "ejer" pr. film, indtastet ved scan/registrering | done | 0.13.0       |
| 26| Films `serial_number` kan kun ændres af en admin eller den bruger der oprindeligt registrerede filmen (afhænger af #25) | done | 0.13.0       |
| 27| Fler-niveau sortering (se #17) udvides: en valgt kombination af sorteringsniveauer kan gemmes som navngivet preset og hurtigt genvælges via dropdown i biblioteksvisningen | planned | -       |
| 28| Ønskeliste-side ("Ønsker"): samme søge-/filtrerings-/sorteringsfunktioner som biblioteksvisningen, men uden serienummer | planned | -       |
| 29| Soft-delete af film: ved sletning logges film (serienr, titel, hvornår, hvem) i en separat slettet-film-liste i stedet for kun at forsvinde. Serienummeret frigøres derved automatisk til genbrug | planned | -       |
| 30| Discogs som fallback-kilde ved stregkode-opslag (`/api/scan/lookup`) når UPCitemdb ikke finder et match — bedre dækning for europæiske EAN-koder | planned | -       |
| 31| Print-venlig liste-visning af biblioteket: kompakt tabel (serienr/titel/år/format/lokation), én film pr. linje, optimeret til udskrift | done | 0.14.0       |
