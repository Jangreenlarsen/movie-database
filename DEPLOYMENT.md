# Deployment (produktion)

Produktion kører **native** på en dedikeret Debian-server — ikke Docker Compose. `docker-compose.yml` i repo-roden er fra det oprindelige scaffold og er aldrig blevet færdiggjort/verificeret (se FEATURES.md #10); den bruges ikke.

---

## Server

| | |
|---|---|
| OS | Debian 13 (trixie) |
| Host | `10.1.130.10` (hjemmenetværket) og offentligt/primært via `movie.laces.dk` (se "Offentlig adgang" nedenfor). **`movie.ll.lan` er retired** (Jan, 2026-08-29: *"movie.ll.lan skal ikke være en del af dns mere da vi er gået i prod med movie.laces.dk"*) — den interne DNS-post er fjernet, hostnavnet indgår ikke længere i `CORS_ORIGINS`, og Caddyfilens `movie.ll.lan`-site-block er fjernet (udført 2026-08-29 via backup→swap→`caddy validate`→`systemctl reload caddy`; backup ligger som `/etc/caddy/Caddyfile.bak-tlsinternal`). Verificeret efter reload: `10.1.130.10` og `movie.laces.dk` svarer begge korrekt på `/api/health`, mens en request med `Host: movie.ll.lan` nu får Caddys tomme-200-fallback og intet certifikat — hostnavnet matcher altså intet site-block længere. Se "TLS-certifikat"-afsnittet nedenfor for den historiske baggrund. |
| Hypervisor | Kører som **gæste-VM under Synology Virtual Machine Manager** på `ds5.ll.lan`/`10.1.1.17` — ikke bare metal. "Native" i denne fils overskrift betyder fortsat *ingen Docker inde i gæsten*, ikke at gæsten selv kører uden virtualisering. Se feature #152/FEATURES.md for en genanvendelig VM-skabelon af denne stack til import i VMM. |
| Bruger | `jgl` (har **kun** snæver passwordless sudo til to specifikke kommandoer, via `/etc/sudoers.d/jgl-deploy-ota` — se "Opdatere produktion" nedenfor) |
| Repo | klonet til `/opt/moviedb` fra `main`-branchen, via en **read-only deploy key** (ikke en personlig adgangstoken) — se GitHub repo → Settings → Deploy keys, "moviedb-prod-server" |

### Offentlig adgang (`movie.laces.dk`)

Siden 2026-08-09 er appen desuden nået fra det åbne internet via `movie.laces.dk`, gennem en **separat nginx-reverse-proxy-VM** (ikke Caddy, ikke beskrevet ovenfor) der terminerer TLS (Let's Encrypt) og videresender til `10.1.130.10:443` over et privat netværkssegment — proxyen fungerer samtidig som NAT-gateway for appserverens segment, da dettes egen router-SVI bevidst er fjernet. Fuld arkitektur, netværkstopologi og genetablerings-trin står i `movie-laces-dk-runbook.md` i repo-roden (**bevidst git-ignoreret** — indeholder adgangsoplysninger til den infrastruktur og må aldrig committes, se BUGS.md #66). Konsultér den fil direkte, ikke denne, ved arbejde på proxy-laget.

**Vigtigt for enhver langvarig/streaming-respons (SSE, chunked)**: denne nginx-VM's `location /`-blok manglede oprindeligt `proxy_http_version 1.1;`, hvilket fik nginx til at tale HTTP/1.0 med Caddy og reelt buffere hele svaret til forbindelsen lukkede — for en uendelig strøm (fx AVM70-diagnostikken, BUGS.md #82) betød det at intet nogensinde nåede klienten. Rettet 2026-08-21 (`proxy_http_version 1.1;` + `proxy_buffering off;` tilføjet). En hvilken som helst FREMTIDIG SSE-/streaming-endpoint arves automatisk af rettelsen, da den ikke er sti-specifik — men vær opmærksom på at et fremtidigt genetableret proxy-VM (se runbook'ens afsnit 7) skal have samme to linjer med, hvis genetableringstrinene deri ikke allerede er opdateret til at inkludere dem.

**Vigtigt for `CORS_ORIGINS`**: appserverens `.env` skal indeholde ALLE hostnavne appen reelt tilgås under (`https://10.1.130.10`, `https://movie.laces.dk`) — ikke kun de(t) der er nødvendige for selve CORS-håndhævelsen (som kun rammer ægte cross-origin-kald; movie.laces.dk er same-origin via nginx-proxyen og krævede derfor aldrig CORS-tilladelse for at *virke*). `auth_service.resolve_reset_base_url` (feature #205, BUGS.md #92) bruger DENNE liste til at afgøre hvilket domæne der skal stå i en "glemt adgangskode"-mails link — mangler et domæne i listen, falder den tilbage til `CORS_ORIGINS`s FØRSTE indgang, uanset hvilket domæne brugeren rent faktisk kom ind fra. `https://movie.laces.dk` manglede fuldstændig i produktionens `CORS_ORIGINS` (kun `https://10.1.130.10` stod der) frem til 2026-08-29, hvilket fik alle reset-links fra movie.laces.dk til fejlagtigt at pege på IP-adressen. Rettet ved at tilføje `https://movie.laces.dk` til listen — `movie.ll.lan` blev bevidst IKKE tilføjet, da hostnavnet blev retired (se "Host" ovenfor) samme dag. **Enhver fremtidig ny adgangsvej til appen skal tilføjes her**, ikke kun i nginx/Caddy.

## Komponenter

| Komponent | Hvordan | Port/binding |
|---|---|---|
| MongoDB | `mongodb-org` 8.0 (MongoDB's officielle apt-repo, bookworm-pakken — trixie har endnu ingen egen) | `127.0.0.1:27017` (systemd: `mongod`) |
| Backend | Python venv (`/opt/moviedb/backend/.venv`) + uvicorn | `127.0.0.1:8000` (systemd: `moviedb-backend`) |
| Frontend | `npm run build` → statiske filer i `/opt/moviedb/frontend/dist`, serveret af Caddy | — |
| Reverse proxy / TLS | Caddy 2, `/etc/caddy/Caddyfile` | `:443` (HTTPS), `:80` (redirect til HTTPS) |

Kun port 22 (SSH), 80 og 443 er åbne udefra (`ufw`). MongoDB og backend er kun tilgængelige på `localhost` — nås udelukkende via Caddys reverse proxy.

### TLS-certifikat (se BUGS.md #23)

**RETIRED 2026-08-29** (Jan: *"movie.ll.lan skal ikke være en del af dns mere da vi er gået i prod med movie.laces.dk"*): den interne DNS-post er fjernet OG Caddyfilens `movie.ll.lan`-site-block er fjernet samme dag, så Caddyfilen nu kun har ét site-block (`10.1.130.10, movie.laces.dk { tls internal; import common }`). Selve certifikat-filerne (`/etc/caddy/certs/movie.ll.lan.{crt,key}`) ligger stadig på serveren, men refereres ikke længere af nogen config — de kan slettes ved lejlighed. `10.1.130.10` bruger fortsat Caddys egen selvsignerede `tls internal` (samme rotations-svaghed som beskrevet i BUGS.md #23), men er nu kun et LAN-fallback ved siden af den rigtige produktionsadgang via `movie.laces.dk` (Let's Encrypt-certifikat, termineret på nginx-proxyen — se "Offentlig adgang" ovenfor), ikke længere den anbefalede primære adresse. Resten af dette afsnit er bevaret som historisk baggrund for hvordan `movie.ll.lan`-certifikatet blev sat op — relevant hvis et lignende internt AD CA-udstedt certifikat til et fremtidigt LAN-hostnavn nogensinde bliver aktuelt igen, men ikke længere aktivt i drift.

Sitet blev tidligere serveret på to adresser med to forskellige certifikater (Caddyfile havde to site-blocks, der delte handler-logik via en `(common)`-snippet):

- **`https://movie.ll.lan`** (tidligere primær, anbefalet adresse — nu retired) — rigtigt certifikat udstedt af Jans **interne Windows AD CS-CA** (`ll-AD-CA`, allerede betroet på hans enheder), gyldigt 2 år (2026-08-02 → 2028-08-01), fil: `/etc/caddy/certs/movie.ll.lan.{crt,key}` (root:caddy, 640). Krævede en intern DNS-post for `movie.ll.lan` → `10.1.130.10`. Ingen certifikat-advarsler, ingen manuel per-enhed import nødvendig (enhederne stolede allerede på `ll-AD-CA`).
- **`https://10.1.130.10`** (fortsat i brug, IP-baseret LAN-fallback) — stadig Caddys egen selvsignerede `tls internal`, med samme rotations-svaghed som beskrevet i BUGS.md #23 (leaf roterer hver 12. time, intermediate hver 7. dag).

**Sådan blev certifikatet udstedt** (manuel CSR-signering, ikke ACME — Jans interne CA understøtter ikke automatisk udstedelse): en ECDSA P-256-nøgle + CSR (CN+SAN=`movie.ll.lan`) blev genereret direkte på serveren (nøglen forlod aldrig serveren), CSR'en blev signeret af Jans interne CA via Windows-certifikatanmodning, det signerede certifikat (`certnew.cer`, DER-format) og CA-rodcertifikatet (`CA.cer`) blev konverteret til PEM og verificeret (public key-hash) til at matche den lokale private nøgle, før det blev installeret.

**Fornyelse (fra 2026-08-03, via appen — feature #73, anbefalet)**: Indstillinger-siden har nu en admin-only "TLS-certifikat"-sektion der kan generere en ny CSR eller importere en færdig PKCS12 direkte i UI'et, uden manuel SSH-adgang. Se afsnittet "TLS-certifikat via appen" nedenfor. Den oprindelige manuelle proces (næste afsnit) er stadig gyldig som fallback, fx hvis backend'en slet ikke kan starte.

**Sådan blev det oprindelige certifikat udstedt manuelt** (CSR-signering, ikke ACME — Jans interne CA understøtter ikke automatisk udstedelse): en ECDSA P-256-nøgle + CSR (CN+SAN=`movie.ll.lan`) blev genereret direkte på serveren (nøglen forlod aldrig serveren), CSR'en blev signeret af Jans interne CA via Windows-certifikatanmodning, det signerede certifikat (`certnew.cer`, DER-format) og CA-rodcertifikatet (`CA.cer`) blev konverteret til PEM og verificeret (public key-hash) til at matche den lokale private nøgle, før det blev installeret.

**Udløb**: certifikatet udløber 2028-08-01 — brug fremover "TLS-certifikat"-sektionen i Indstillinger til fornyelse i god tid inden da (ingen automatisk fornyelse).

**Den tidligere manuelle sudoers-regel er ikke længere nødvendig**: `/etc/sudoers.d/jgl-tls-cert-install` (snævert scopet til install/`caddy validate`/`systemctl reload caddy`) blev brugt til at lade Claude installere det *oprindelige* certifikat via SSH. Feature #73's `moviedb-cert-install`-systemd-unit (se nedenfor) overtager denne rolle uden sudo overhovedet — reglen kan fjernes (`sudo rm /etc/sudoers.d/jgl-tls-cert-install`) når/hvis den nye unit er sat op og afprøvet.

### TLS-certifikat via appen (feature #73)

**Status 2026-08-29**: dette maskineri blev bygget til at forny/installere `movie.ll.lan`-certifikatet, som nu er retired (se ovenfor). Der er i øjeblikket intet certifikat der administreres via denne vej — `10.1.130.10` bruger Caddys egen `tls internal`, og den offentlige `movie.laces.dk`-adgang håndteres af Let's Encrypt på nginx-proxyen, uden for denne app. Beholdt som fungerende infrastruktur til en fremtidig situation med et nyt, rigtigt LAN-certifikat, ikke fjernet — men ikke aktivt i brug lige nu.

Samme ikke-sudo-trigger-arkitektur som OTA-opdatering (se `## Opdatere produktion` nedenfor og ARCHITECTURE.md's note): `moviedb-backend` kan aldrig skrive til `/etc/caddy/certs/` eller bruge sudo, så den lægger et nyt cert+nøgle i `/opt/moviedb/certs/pending/` (indenfor sine egne `ReadWritePaths`) og rører en trigger-fil; en separat, root-ejet systemd path-unit opdager den og udfører selve installationen.

**Opsætning på serveren (kun nødvendigt én gang — IKKE udført endnu, kræver eksplicit bekræftelse før udførelse jf. CLAUDE.md regel 16, da en fejl her kan tage produktionens HTTPS ned)**:

```bash
# Cert-install-scriptet — ligger uden for git-working-tree'en (samme grund som
# /opt/moviedb-deploy.sh), så en samtidig "git pull" ikke kan overskrive den
# fil bash er ved at eksekvere.
sudo cp /opt/moviedb/scripts/cert-install.sh /opt/moviedb-cert-install.sh
sudo chmod +x /opt/moviedb-cert-install.sh
sudo chown jgl:jgl /opt/moviedb-cert-install.sh

# Install-watcher (kører som root, uden for sandkassen — undgår sudo helt)
sudo cp /opt/moviedb/scripts/moviedb-cert-install.path /opt/moviedb/scripts/moviedb-cert-install.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now moviedb-cert-install.path
```

`moviedb-backend.service`s `ReadWritePaths` skal udvides til at inkludere cert-staging-mappen (den findes allerede rekursivt under `/opt/moviedb`, så ingen ændring nødvendig hvis `ReadWritePaths=/opt/moviedb ...` allerede er sat som ovenfor):

```ini
ReadWritePaths=/opt/moviedb /opt/moviedb-deploy.log
```

**Læse-adgang til det installerede certifikat** (for at `GET /api/system/cert` kan vise status for det *aktuelt kørende* certifikat, ikke kun det staged): `moviedb-backend`-brugeren (`jgl`) skal kunne læse `/etc/caddy/certs/movie.ll.lan.crt` (root:caddy, 640) — `jgl` er allerede i `caddy`-gruppen fra den oprindelige cert-opsætning (se installations-loggen nedenfor), så dette er formentlig allerede opfyldt; verificér med `sudo -u jgl cat /etc/caddy/certs/movie.ll.lan.crt` hvis statusvisningen viser "intet certifikat fundet" på trods af at ét er installeret.

`cert-install.sh` tager en `.bak`-kopi af det eksisterende cert+nøgle før overskrivning, kører `caddy validate` før `systemctl reload caddy`, og rydder både trigger-fil og staged nøgle/cert bagefter (se scriptet for detaljer). Fejler `caddy validate`, sker reload **ikke** — men filerne er allerede overskrevet på det tidspunkt, så en fejlet installation skal rulles tilbage manuelt fra `.bak`-filerne over SSH.

**HTTP/3 er slået fra** (`servers { protocols h1 h2 }` i Caddyfile'ens globale block). Caddy annoncerer ellers HTTP/3 (QUIC/**UDP** 443) via en `Alt-Svc`-header, men `ufw` åbner kun **TCP** 443 — browseren forsøger så at opgradere til QUIC, det fejler stille mod den lukkede UDP-port, og det viste sig i Firefox som `SSL_ERROR_INTERNAL_ERROR_ALERT` i stedet for det forventede "usikker forbindelse, fortsæt alligevel"-varsel. Løsningen er enten at slå HTTP/3 fra (valgt her — unødvendigt for en lille LAN-app) eller at åbne UDP 443 i firewallen også.

### Offentligt domæne + automatisk Let's Encrypt-certifikat (feature #74) — SUPERSEDET, aldrig udført

**Denne plan blev aldrig udført og er nu erstattet af den faktisk implementerede løsning**: reel offentlig adgang blev i stedet opnået 2026-08-09 via en separat nginx-reverse-proxy-VM (se "Offentlig adgang" øverst i denne fil, samt `movie-laces-dk-runbook.md`) — IKKE via et tredje Caddy site-block på appserveren selv, som denne sektion oprindeligt lagde op til. Bevaret som historisk kontekst for hvorfor og hvordan beslutningen faldt anderledes ud, men de konkrete kommandoer nedenfor skal IKKE følges.

Både `movie.ll.lan` (nu retired) og `10.1.130.10` var **kun** nåbare fra hjemmenetværket (intern DNS hhv. ingen router-portviderledning udefra) — hverken Let's Encrypt eller nogen anden public CA kan udstede til et privat IP eller et internt-kun-navn under alle omstændigheder. Jans ønske (2026-08-03) om ægte adgang udefra kræver derfor et **rigtigt, offentligt domænenavn** (DNS hos one.com/Larsen Data, fast offentlig IP bekræftet) og et **tredje** Caddy site-block — helt adskilt fra de to LAN-certifikater ovenfor, som forbliver uændrede.

**Hvorfor HTTP-01 (Caddys indbyggede automatiske HTTPS), ikke DNS-01**: en DNS-01-udfordring ville kræve et Caddy DNS-plugin til one.com (findes ikke som et etableret `caddy-dns`-modul, ville kræve en custom Caddy-build via `xcaddy`), uden nogen fordel her — port 80/443 skal alligevel åbnes udefra for at selve appen kan nås. Caddy 2 (allerede installeret) understøtter HTTP-01/automatisk udstedelse+fornyelse **indbygget uden plugins**: den eneste kode-ændring er at bruge det rigtige domænenavn som site-adresse i stedet for `tls internal` — ingen af feature #73's CSR/PKCS12/trigger-maskineri er involveret, Caddy passer sig selv resten af certifikatets liv (fornyer automatisk ~30 dage før hvert 90-dages Let's Encrypt-certifikat udløber).

**Forudsætninger Jan selv skal sætte op, før Claude rører Caddyfile**:
1. DNS A-record hos one.com for det valgte navn (fx `movie.<dit-domæne>.dk`) → den faste offentlige IP.
2. Router-portviderledning: **TCP 80 og 443** → `10.1.130.10:80`/`:443`. **Anbefaling: videresend ikke port 22** — SSH bør forblive LAN/VPN-only, selvom web-appen bliver offentligt tilgængelig.

**Caddyfile-tilføjelsen (afventer Jans "gør det nu"-bekræftelse — IKKE udført endnu)**, et tredje site-block der genbruger den eksisterende `(common)`-snippet (samme mønster som `movie.ll.lan`/`10.1.130.10`), uden `tls internal`:

```caddyfile
movie.dit-domæne.dk {
    import common
}
```

samt en global `email <jans e-mail>` i Caddyfile'ens øverste `{ ... }`-block (Let's Encrypt-notifikationer, anbefalet). Derefter samme to trin som ved den oprindelige #23-opsætning: `sudo caddy validate --config /etc/caddy/Caddyfile`, så `sudo systemctl reload caddy`.

**Sikkerhedskonsekvens**: login-siden bliver nu synlig for hele internettet, ikke kun LAN. Feature #66's admin-godkendelse af nye registreringer (`pending`-status uden adgang før godkendt) er den primære beskyttelse mod uønskede tilmeldinger og står allerede på plads — ingen kodeændring nødvendig. Den offentlige `/bio`-side (feature #70) er i forvejen designet til at være delbar/offentlig.

**Verifikation efter reload**:
```bash
curl -sk https://movie.dit-domæne.dk/api/health   # kør fra UDEN for hjemmenetværket (fx mobildata)
openssl s_client -connect movie.dit-domæne.dk:443 -servername movie.dit-domæne.dk </dev/null 2>/dev/null | openssl x509 -noout -issuer -dates
sudo journalctl -u caddy | grep -i "certificate obtained\|acme"
```
Udsteder skal vise `Let's Encrypt`, ikke `Caddy Local Authority`. Test bagefter at `movie.ll.lan`/`10.1.130.10` stadig svarer uændret, for at bekræfte at det nye site-block ikke har forstyrret dem.

## `.env` (produktion)

Ligger i `/opt/moviedb/backend/.env` (git-ignoreret, `chmod 600`, ejes af `jgl`). Indeholder en **unik** `JWT_SECRET_KEY` genereret direkte på serveren (ikke genbrugt fra dev), `TMDB_API_TOKEN`, og `COOKIE_SECURE=true` (rigtig HTTPS i produktion). `DISCOGS_TOKEN` er tom (Discogs-opslag virker uden token, bare med lavere rate-limit — se MOVIE_API_REFERENCE.md). `RESEND_API_KEY`/`EMAIL_FROM_ADDRESS` (feature #197) er som udgangspunkt **også** tomme her — den anbefalede vej er admin-UI'et, se næste afsnit. `CORS_ORIGINS` (siden 2026-08-29): `https://10.1.130.10,https://movie.laces.dk` — se "Vigtigt for `CORS_ORIGINS`" under "Offentlig adgang" ovenfor for hvorfor begge skal stå der, ikke kun det/de der teknisk kræves for selve CORS-håndhævelsen.

## E-mail (Resend) — opsætning (feature #197)

Appen sender udgående notifikations-mails (ønske godkendt/afvist/bestilt/flyttet, forvisnings-svar, admin-broadcasts m.fl.) via **Resend** (`https://resend.com`), en transaktions-mail-udbyder med et rent HTTP-API — valgt fremfor SMTP-relæ eller egen postserver, da appen ikke har (og ikke skal have) sin egen mailserver. Se FEATURES.md #197 for den fulde begrundelse.

**Kontoopsætning hos Resend** (én gang, uden for selve appen):

1. Opret en Resend-konto (gratis niveau: 3.000 mails/måned, 100/dag — rigeligt til en husstands-portal, men værd at kende hvis notifikationsvolumen nogensinde vokser).
2. **Verificér et afsender-domæne** under *Domains* i Resend-dashboardet — brug et rigtigt (sub)domæne appen allerede kontrollerer DNS'en for (fx `mail.laces.dk`), ikke selve `laces.dk` hvis andre systemer (fx almindelig e-mail) allerede bruger den. Resend viser de nødvendige DNS-records (SPF, DKIM, og en valgfri men anbefalet DMARC) — de tilføjes hos domænets DNS-udbyder, ikke på serveren. Verifikation tager typisk minutter til et par timer afhængig af DNS-propagering. **Uden et verificeret domæne** kan der kun sendes fra Resends eget `onboarding@resend.dev` og kun til kontoens egen, bekræftede e-mail — fint til en hurtig test, ikke brugbart i produktion.
3. Opret en API-nøgle under *API Keys* — vælg scope **"Sending access"** (Resends mindst-privilegerede, anbefalede type), ikke "Full access". Denne nøgletype kan ikke læse domæne-/kontooplysninger tilbage (`email_client.test_connection()` i koden håndterer eksplicit dens karakteristiske 401 `restricted_api_key`-svar på `GET /api-keys` som "nøglen virker", ikke som en fejl — se BUGS.md-mønsteret dokumenteret i koden).
4. Vælg en afsenderadresse **på det verificerede domæne** (fx `noreply@mail.laces.dk`) — det er værdien der skal i `EMAIL_FROM_ADDRESS`.

**I appen** (admin-only, Indstillinger → Eksterne API-nøgler → E-mail-notifikationer, feature #198): indsæt den nye API-nøgle i **Resend API-nøgle** og afsenderadressen fra trin 4 i **E-mail-afsenderadresse**. Aktiveres med det samme, ingen genstart nødvendig (samme mønster som TMDb/Discogs/Plex-nøglerne). Brug **"Test forbindelse"** for at bekræfte selve nøglen er gyldig, og **"Send testmail"** (feature #199) for at bekræfte en rigtig mail rent faktisk bliver leveret til en valgfri modtageradresse — de to knapper tester forskellige ting, se #199's begrundelse hvis kun den ene virker.

**`.env` som fallback**: `RESEND_API_KEY`/`EMAIL_FROM_ADDRESS` kan i stedet sættes i `/opt/moviedb/backend/.env` (samme to variabelnavne som `backend/.env.example`) hvis man foretrækker at undgå at have nøglen i databasen — en værdi sat i admin-UI'et overstyrer altid `.env`, som kun bruges hvis UI'et ikke har en værdi sat. Kræver backend-genstart for at slå igennem, i modsætning til UI-vejen.

**Uden konfiguration**: hverken nøgle eller afsenderadresse sat = e-mail-afsendelse er et rent, ulogget no-op — alle notifikationer fortsætter med at virke som in-app-beskeder i portalen, kun selve e-mail-delen udebliver. Ingen fejl, intet der stopper appen.

## Opdatere produktion til en ny version

### Via "Opdatér fra GitHub"-knappen (feature #20, anbefalet)

Indstillinger-siden har en **admin-only** "Opdatér fra GitHub"-knap. Den kalder `POST /api/system/deploy`, som starter `/opt/moviedb-deploy.sh` i baggrunden (`git fetch` + skift til/opdatér den valgte branch + geninstaller afhængigheder + `npm run build`) og svarer med det samme — siden poller derefter `/api/health`s `build`-felt indtil den nye version er oppe (typisk under et minut). Se ARCHITECTURE.md's note om OTA-opdatering for de tekniske detaljer.

**Branch-valg** (feature #194, Jan: *"vi skal have en mulighed for at opdater fra github på Main eller Dev på portal sådan det giver mening med main og dev versioner"*): knappen har nu et branch-valg, `main` (standard, forudvalgt) eller `dev`. Et valg af `dev` kræver en ekstra bekræftelse i UI'et og viser en tydelig advarsel om at koden ikke nødvendigvis er produktionsklar. Den kørende server skifter rent faktisk `git`-branch ved dette valg (`git checkout dev` første gang, derefter almindelige `pull`'er) — det er **ikke** en separat staging-server, kun én fysisk server der midlertidigt kan køre `dev`-koden. Skift tilbage til `main` ved at vælge `main` og opdatere igen.

**Live-verificeret** 2026-08-01 (efter at have fanget og rettet to reelle sandbox-relaterede fejl — se BUGS.md #18): hele kæden kørt igennem direkte inde i den *faktiske* sandboxede mount-namespace for den kørende `moviedb-backend`-proces (via `nsenter` på processens PID, ikke et almindeligt shell), for at reproducere præcis den kontekst en rigtig admin-klik kører i. `git pull` → `pip install` → `npm run build` → trigger-fil → automatisk genstart af `moviedb-backend` + genindlæsning af `caddy` gennemført uden fejl, `moviedb-backend`s `ActiveEnterTimestamp` bekræftede en reel genstart, `/api/health` svarede korrekt undervejs og efter. Selve knappen (admin-login → klik → polling i browseren) er endnu ikke afprøvet af Jan, men den underliggende mekanisme er nu verificeret i den rigtige runtime-kontekst.

**Vigtigt om `moviedb-backend.service`'s sandboxing**: servicen kører med `ProtectSystem=strict` + `NoNewPrivileges=true` (se opsætning nedenfor). `NoNewPrivileges=true` gør `sudo` **permanent ubrugeligt** for servicen og alle dens child-processer, uanset sudoers-opsætning — deploy-scriptet bruger derfor **ikke** `sudo` til at genstarte services. I stedet rører scriptet en trigger-fil (`/opt/moviedb/.deploy-restart-trigger`), som en separat, ikke-sandboxed root-ejet systemd path-unit (`moviedb-deploy-restart.path` → `.service`) reagerer på og udfører den faktiske genstart/reload. Se `scripts/moviedb-deploy-restart.path` og `scripts/moviedb-deploy-restart.service`.

**Opsætning på serveren** (kun nødvendigt én gang, eller hvis `scripts/deploy.sh`/de to nye unit-filer ændres i repoet — **feature #194 ændrede `scripts/deploy.sh`, så den eksekverbare kopi på serveren skal genindsættes én gang efter denne opdatering**, ellers kører den gamle, branch-uafhængige version indtil da):

```bash
# Deploy-scriptet
sudo cp /opt/moviedb/scripts/deploy.sh /opt/moviedb-deploy.sh
sudo chmod +x /opt/moviedb-deploy.sh
sudo chown jgl:jgl /opt/moviedb-deploy.sh
sudo touch /opt/moviedb-deploy.log && sudo chown jgl:jgl /opt/moviedb-deploy.log

# Restart-watcher (kører som root, uden for sandkassen — undgår sudo helt)
sudo cp /opt/moviedb/scripts/moviedb-deploy-restart.path /opt/moviedb/scripts/moviedb-deploy-restart.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now moviedb-deploy-restart.path
```

`moviedb-backend.service` skal have følgende `ReadWritePaths`/`PrivateTmp`, ellers fejler `git pull`/`npm run build`/log-skrivning med `Read-only file system` (BUGS.md #18):

```ini
ProtectSystem=strict
PrivateTmp=true
ReadWritePaths=/opt/moviedb /opt/moviedb-deploy.log
```

Der er **ingen** sudoers-regel involveret længere til selve deploy-flowet — den tidligere snævre `/etc/sudoers.d/jgl-deploy-ota`-regel (der viste sig aldrig at kunne virke pga. `NoNewPrivileges=true`) er fjernet fra serveren. `jgl` har fortsat almindelig (password-krævende) sudo-adgang via `sudo`-gruppen til manuel drift over SSH — det er en helt separat sti, upåvirket af servicens sandboxing, da et login-shell aldrig er en child-proces af `moviedb-backend`.

### Manuelt (uden knappen, fx hvis backend slet ikke kan starte)

```bash
ssh -i ~/.ssh/moviedb_deploy jgl@10.1.130.10
cd /opt/moviedb
git pull origin main

# Backend
cd backend
.venv/bin/pip install --quiet -r requirements.txt   # kun hvis requirements.txt ændret
sudo systemctl restart moviedb-backend

# Frontend
cd ../frontend
npm install --silent   # kun hvis package.json ændret
npm run build
sudo systemctl reload caddy   # for en sikkerheds skyld, filerne læses direkte fra dist/
```

## Systemovervågning og genstart (feature #154)

Indstillinger-siden har en admin-only "Systemovervågning"-sektion (under Drift) der viser CPU/RAM/disk (via `psutil`) og status for `mongod`/`caddy`/`moviedb-backend` (via `systemctl is-active`, som ikke kræver sudo). To handlinger er tilgængelige:

- **Genstart tjeneste** — ingen adgangskode-bekræftelse, samme lave friktion som "Opdatér fra GitHub". `POST /api/system/monitor/restart-service`.
- **Genstart serveren** — kræver admins eget password (samme mønster som database-reset), fordi hele VM'en er nede i genstarts-perioden, ikke kun web-laget. `POST /api/system/monitor/reboot`.

Samme sandboxing-begrundelse som deploy-flowet ovenfor gælder her: `moviedb-backend.service`s `NoNewPrivileges=true` gør `sudo`/`reboot` permanent utilgængeligt for servicen. Backend rører derfor kun en trigger-fil (`/opt/moviedb/.reboot-trigger`), som en separat, ikke-sandboxed root-ejet systemd path-unit reagerer på og selv udfører den faktiske `reboot`. "Genstart tjeneste" genbruger den **eksisterende** `moviedb-deploy-restart.path`/`.service` (samme trigger-fil, `/opt/moviedb/.deploy-restart-trigger`, allerede sat op ovenfor) — kun "Genstart serveren" kræver en ny unit.

**Opsætning på serveren** (kun nødvendigt én gang, eller hvis de to nye unit-filer ændres i repoet):

```bash
sudo cp /opt/moviedb/scripts/moviedb-reboot.path /opt/moviedb/scripts/moviedb-reboot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now moviedb-reboot.path
```

## Fejlsøgning

```bash
sudo systemctl status mongod moviedb-backend caddy
sudo journalctl -u moviedb-backend -f
sudo journalctl -u caddy -f
sudo caddy validate --config /etc/caddy/Caddyfile
```

## Databasen

Produktionsdatabasen startede **tom** (bevidst valg — ingen data migreret fra dev-maskinens lokale MongoDB). Første bruger der registrerer sig på `https://10.1.130.10` bliver automatisk admin (se ARCHITECTURE.md's note om bootstrap).

---

## Genanvendelig appliance-skabelon (feature #152)

En **frisk, generisk** VM-skabelon af basissystemet ovenfor (Debian 13 + MongoDB 8.0 + Node 22 + Caddy + ufw), byggeklar til import i **Synology Virtual Machine Manager** (`.ova`, som VMM importerer direkte via Image → Add → Import) eller enhver anden hypervisor der forstår OVA/OVF. Findes i `packer/` (repo-roden), bygget med [HashiCorp Packer](https://www.packer.io/) + VirtualBox — **ikke** afhængig af eller forbundet til den kørende prod-VM på noget tidspunkt.

**Bevidst uden hemmeligheder eller data** (CLAUDE.md regel 6/16 — en delt skabelon må aldrig indeholde rigtige secrets):
- **Login** (Jans valg 2026-08-14, efter første forsøg med SSH-nøgle-only — konsol-login i VMM skal virke uden en nøglefil): `jgl` / bootstrap-adgangskoden i `packer/variables.pkr.hcl` (`jgl_password`, default `ChangeMe123!`) + passwordless sudo. Adgangskoden er bevidst simpel, men **ubrugelig efter første login** — `chage -d 0` tvinger et skifte (både konsol og SSH) før en shell overhovedet startes, så standardværdien aldrig reelt forbliver i brug (regel 16).
- **Init-/velkomstrutine ved første login** (`scripts/moviedb-welcome-profile.sh`, installeret som `/etc/profile.d/moviedb-welcome.sh`): viser hostname + DHCP-tildelt IP og de næste skridt — løser det konkrete problem at et frisk importeret VM ikke har nogen kendt IP før man kan logge ind. Vises kun én gang pr. bruger (markørfil i `$HOME`).
- Intet app-repo klonet, intet rigtigt `JWT_SECRET_KEY`/GitHub-deploy-key/TMDb-token, ingen Caddyfile (afhænger af den endelige VM's hostname/IP), og `moviedb-backend`-servicen er *staged men ikke aktiveret* (den vil fejle uden appen).
- OTA-deploy og cert-install-scriptene/-units (`scripts/deploy.sh`, `scripts/cert-install.sh` + deres `.path`/`.service`-units) **er** forudinstalleret og aktiveret — de er passive indtil en trigger-fil røres, så det er sikkert.

**Kendt boot-fejl i VMM**: en importeret VM kan starte direkte i en UEFI-`Shell>`-prompt i stedet for at boote Debian. Skabelonens disk er installeret til **legacy BIOS-boot** (VirtualBox's standard), men VMM opretter/importerer nogle gange VM'en med UEFI-firmware — de to matcher ikke. Løsning: i VM'ens indstillinger i VMM, sæt boot-mode/firmware til **Legacy BIOS** og genstart.

**Bygge lokalt**:
```bash
cd packer
packer init .
packer build -force .
```
Producerer `packer/output/moviedb-appliance.ova`. Bygget/verificeret lokalt via VirtualBox (headless) — ingen ekstern hypervisor-adgang nødvendig for selve build-trinnet.

**Efter import i VMM** — find VM'ens IP via velkomstrutinen ovenfor (eller VMM's egen netværks-fane / DHCP-lease-tabellen for hostname `moviedb-appliance`), log ind, skift adgangskoden når du bliver bedt om det, og følg derefter samme trin som denne fils "Sådan blev serveren sat op" 7-10, kun kortere (1-6+11 er allerede i skabelonen):
```bash
ssh jgl@<den nye VM's IP>   # bedes om at skifte adgangskoden ved dette første login

sudo mkdir -p /opt/moviedb && sudo chown jgl:jgl /opt/moviedb   # allerede oprettet, men chown for en sikkerheds skyld
git clone <deploy-key-URL> /opt/moviedb   # ny/dedikeret deploy key til DENNE VM, se trin 7 ovenfor for mønsteret
cd /opt/moviedb/backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# .env: JWT_SECRET_KEY genereret PÅ denne VM (aldrig genbrugt), TMDB_API_TOKEN, COOKIE_SECURE=true — se "## .env (produktion)"
cd ../frontend && npm install && npm run build
sudo cp /opt/moviedb/scripts/moviedb-backend.service /etc/systemd/system/   # allerede staged af skabelonen, men opdatér hvis repoet har ændret den
# Caddyfile: se trin 10 ovenfor — tilpas hostname/IP til den nye VM
sudo systemctl daemon-reload && sudo systemctl enable --now moviedb-backend caddy
```

**Data-migrering** af en eksisterende prod-servers indhold til en ny VM bygget fra denne skabelon sker via appens egen fulde system-backup/-restore (feature #61, udvidet i BUGS.md #65) — tag en backup på den gamle server via Indstillinger, gendan den på den nye, **ikke** ved at forsøge at klone disken.

---

## Sådan blev serveren sat op (installations-log, 2026-08-01)

Trin-for-trin hvad der faktisk blev gjort for at gå fra en frisk Debian 13-installation til kørende produktion. Nyttig hvis serveren skal geninstalleres, eller en tilsvarende opsætning skal laves et andet sted.

### 1. SSH-adgang uden gentagen adgangskode

Serveren blev leveret med bruger `jgl` + adgangskode. For ikke at skulle sende adgangskoden i klartekst ved hvert kommando-kald:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/moviedb_deploy -N "" -C "moviedb-deploy"
```

Den nye offentlige nøgle blev installeret på serveren via **ét** password-baseret login (Windows' `ssh` kan ikke lave et ikke-interaktivt password-login selv, så PuTTYs `plink -pw` blev brugt til lige præcis dette ene bootstrap-trin):

```bash
plink -ssh -pw "<adgangskode>" jgl@10.1.130.10 \
  "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '<offentlig nøgle>' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

Herefter blev al efterfølgende adgang gjort med `ssh -i ~/.ssh/moviedb_deploy jgl@10.1.130.10` — ingen adgangskode involveret mere.

### 2. Sudo-adgang

`jgl` havde hverken `sudo` installeret eller adgang til det. `su` (med root's adgangskode, sendt via stdin — `su` kan læse derfra selvom den normalt foretrækker en TTY) blev brugt til at rette dette **én gang**:

- Apt havde **kun** en cdrom-kilde i `/etc/apt/sources.list` (ingen netværks-mirror) — blev overskrevet med rigtige `deb.debian.org`/`security.debian.org`-linjer for trixie, ellers fejlede al pakkeinstallation.
- `apt-get install sudo`, `usermod -aG sudo jgl`, og en `/etc/sudoers.d/jgl-deploy`-fil med `jgl ALL=(ALL) NOPASSWD:ALL` (valideret med `visudo -c` før den blev taget i brug).

Herefter blev root's adgangskode aldrig brugt igen — alt kørte via `sudo` som `jgl`.

### 3. Basis-pakker

```bash
sudo apt-get install -y git python3 python3-venv python3-pip curl gnupg ca-certificates ufw build-essential
```

### 4. MongoDB 8.0

Debian 13 (trixie) er for ny til at have sin egen officielle MongoDB-repo endnu, så bookworm-repoen blev brugt (virker fint, kun apt-metadata, ingen OS-specifik binær-afhængighed der driller):

```bash
curl -fsSL https://pgp.mongodb.com/server-8.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-8.0.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg] https://repo.mongodb.org/apt/debian bookworm/mongodb-org/8.0 main" | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
sudo apt-get update && sudo apt-get install -y mongodb-org
sudo systemctl enable --now mongod
```

Verificeret at `/etc/mongod.conf` fortsat binder til `127.0.0.1` (default) — ikke ændret, MongoDB skal aldrig være nåbar udefra.

### 5. Node.js 22 (til at bygge frontend)

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 6. Caddy 2 (reverse proxy + TLS)

```bash
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update && sudo apt-get install -y caddy
```

### 7. Kode fra GitHub (repoet er privat)

Et almindeligt `git clone` (HTTPS) fejlede — intet login. I stedet for at lægge en personlig GitHub-adgangstoken på serveren blev der lavet en **dedikeret, read-only deploy key**, kun gyldig for dette ene repo:

```bash
# På serveren:
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N "" -C "moviedb-prod-server"

# Lokalt (gh CLI allerede logget ind som Jan):
gh repo deploy-key add - --title "moviedb-prod-server (read-only)" --repo Jangreenlarsen/movie-database <<< "<serverens offentlige nøgle>"
```

```bash
# På serveren: ~/.ssh/config
Host github.com
    IdentityFile ~/.ssh/github_deploy
    IdentitiesOnly yes
```

```bash
sudo mkdir -p /opt/moviedb && sudo chown jgl:jgl /opt/moviedb
git clone git@github.com:Jangreenlarsen/movie-database.git /opt/moviedb
cd /opt/moviedb && git checkout main
```

### 8. Backend

```bash
cd /opt/moviedb/backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

`.env` blev skrevet direkte på serveren, med `JWT_SECRET_KEY` genereret **på serveren** (aldrig transporteret over SSH eller vist noget sted):

```bash
JWT_SECRET=$(.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))")
```

Se `## .env (produktion)` ovenfor for hvilke andre felter der blev sat. Filen fik `chmod 600`.

Testet manuelt først (5 sekunders kørsel, aflyst igen) for at fange evt. opstartsfejl *før* systemd-servicen blev lavet:

```bash
timeout 5 .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Derefter en systemd-service (`/etc/systemd/system/moviedb-backend.service`) der binder uvicorn til `127.0.0.1:8000` som bruger `jgl`, med et par hærdnings-flag (`NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp=true`, `ReadWritePaths=/opt/moviedb /opt/moviedb-deploy.log` — se "Opdatere produktion" ovenfor for hvorfor disse specifikke paths/flag er nødvendige) og `Restart=on-failure`:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now moviedb-backend
```

### 9. Frontend

```bash
cd /opt/moviedb/frontend
npm install
npm run build
```

Bygger til `dist/` — appens API-klient bruger som standard en relativ `/api`-sti, så den virker automatisk sammen med Caddys same-origin reverse proxy uden ekstra konfiguration (intet `VITE_API_BASE_URL` nødvendigt).

Verificeret at hele stien til `dist/` var læsbar for `caddy`-systembrugeren (`namei -l`) — ellers ville Caddy give 403 på alle statiske filer.

### 10. Caddy-konfiguration

`/etc/caddy/Caddyfile` — **den aktuelle, kørende konfiguration** (opdateret 2026-08-29 med cache-headers, BUGS.md #94):

```caddyfile
{
	servers {
		protocols h1 h2
	}
}

(common) {
	handle /api/* {
		reverse_proxy 127.0.0.1:8000
	}

	handle {
		root * /opt/moviedb/frontend/dist

		# BUGS.md #94 — se "Cache-styring" nedenfor for hvorfor alle tre lag
		# er nødvendige.
		@hashed path /assets/*
		header @hashed Cache-Control "public, max-age=31536000, immutable"

		@media path /cinema/*
		header @media Cache-Control "public, max-age=86400"

		@entry not path /assets/* /cinema/*
		header @entry Cache-Control "no-cache"

		file_server
		try_files {path} /index.html
	}
}

10.1.130.10, movie.laces.dk {
	tls internal
	import common
}
```

Valideret før brug (`sudo caddy validate --config /etc/caddy/Caddyfile`), derefter `sudo systemctl enable --now caddy` (eller `reload` ved ændringer).

**Ændringshistorik for denne fil** (alle tilføjet efter første opsætning, som rettelser):
- Den globale `protocols h1 h2`-block — se `SSL_ERROR_INTERNAL_ERROR_ALERT`-noten under "Komponenter" ovenfor.
- `movie.laces.dk` tilføjet til site-block'en (2026-08-09) da den offentlige adgang blev sat op — uden det matchende hostnavn svarede Caddy tomt `200 OK` på alt med `Host: movie.laces.dk`.
- `(common)`-snippet'en indført da der midlertidigt var to site-blocks (`movie.ll.lan` + IP'en); `movie.ll.lan`-blokken er siden fjernet igen (2026-08-29), men snippet-strukturen er beholdt.
- Cache-headers (2026-08-29, BUGS.md #94) — se næste afsnit.

### Cache-styring (BUGS.md #94)

Caddys `file_server` sætter som standard **ingen** `Cache-Control` — kun `ETag` og `Last-Modified`. Det er ikke neutralt: mangler `Cache-Control`/`Expires`, falder browsere tilbage på *heuristisk* caching (RFC 9111 §4.2.2) og gætter selv en holdbarhed, konventionelt ~10% af tiden siden `Last-Modified`. En `index.html` der er en uge gammel kan derfor betragtes som frisk i timevis uden at browseren overhovedet kontakter serveren — og den cachede `index.html` peger på de gamle, content-hashede bundles. Resultatet var at brugere først så nye versioner efter et manuelt hard reload.

De tre lag i konfigurationen ovenfor:

| Sti | Header | Hvorfor |
|---|---|---|
| `/assets/*` | `public, max-age=31536000, immutable` | Filnavnet indeholder en content-hash (`index-KziPAHxq.js`), så indholdet kan per definition aldrig blive forældet under samme navn. Permanent cache er både sikkert og hurtigere end det heuristiske gætværk det erstatter. |
| `/cinema/*` | `public, max-age=86400` | Billeder/PDF/video der ændres sjældent og får nyt filnavn når de gør. Et døgn sparer revaliderings-rundture på mobil uden nævneværdig risiko for forældet indhold. |
| Alt andet | `no-cache` | Gælder `index.html`, `sw.js`, `manifest.webmanifest` og ikoner. `no-cache` betyder **revalidér altid**, ikke "hent alt igen" — med den eksisterende `ETag` bliver et uændret svar et `304 Not Modified` uden body (verificeret: 0 bytes overført mod 996 ved fuld hentning). |

`/api/*` rammes ikke af reglerne — den `handle`-blok går til `reverse_proxy`, så backendens egne svar er upåvirkede.

**Samspil med service workeren**: frontendens PWA-lag (feature #190) er uafhængigt og allerede korrekt — `registerType: 'autoUpdate'` får `vite-plugin-pwa` til at kalde `window.location.reload()` når en ny service worker aktiveres, og `src/pwa.js` tjekker for nye versioner hvert 20. minut. Men en service worker registreres kun i en **betroet** secure context, så brugere på `https://10.1.130.10` (Caddys selvsignerede `tls internal`) får typisk slet ingen SW og kører rent på HTTP-cache — for dem er cache-headerne ovenfor den eneste beskyttelse mod at sidde fast på en gammel version.

**Ved fremtidige ændringer**: tilføjes en ny mappe med statisk indhold under `frontend/public/`, så overvej hvilket af de tre lag den hører til. Standarden (`no-cache`) er altid det sikre valg; de to andre er optimeringer.

### 11. Firewall

Port 22 blev tilladt **først** for ikke at lukke sig selv ude, derefter 443/80, og til sidst default-deny på resten:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp
sudo ufw default deny incoming
sudo ufw --force enable
```

SSH-adgang blev straks re-verificeret efter enable, før noget andet blev gjort.

### 12. Slut-til-slut test

- `curl -sk https://10.1.130.10/api/health` → `{"status":"ok","mongo":true,...}` (gennem hele kæden: Caddy → uvicorn → MongoDB).
- `curl -sk https://10.1.130.10/` → frontend-HTML'en serveres korrekt.
- `curl http://10.1.130.10/` → 308-redirect til HTTPS (Caddys automatiske redirect virker).
- `journalctl -u moviedb-backend` gennemgået — ingen fejl, og vigtigst: **ingen advarsel om usikker JWT-hemmelighed** (bekræfter at den genererede `.env`-værdi rent faktisk blev brugt, jf. CLAUDE.md regel 16's sikkerhedskonfigurations-tjek).
- Reel registrering + login testet med en midlertidig bruger (bekræftede at cookie-baseret auth virker korrekt over HTTPS med `COOKIE_SECURE=true`) — brugeren blev **slettet igen bagefter** (`mongosh moviedb --eval 'db.users.deleteOne(...)'`) så databasen forblev tom og Jans egen første registrering bliver den rigtige bootstrap-admin.
- Alle tre services (`mongod`, `moviedb-backend`, `caddy`) bekræftet `enabled` for opstart ved reboot.
