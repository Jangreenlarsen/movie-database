# Deployment (produktion)

Produktion kører **native** på en dedikeret Debian-server — ikke Docker Compose. `docker-compose.yml` i repo-roden er fra det oprindelige scaffold og er aldrig blevet færdiggjort/verificeret (se FEATURES.md #10); den bruges ikke.

---

## Server

| | |
|---|---|
| OS | Debian 13 (trixie) |
| Host | `10.1.130.10` (kun tilgængelig på hjemmenetværket — intet domænenavn) |
| Bruger | `jgl` (har **kun** snæver passwordless sudo til to specifikke kommandoer, via `/etc/sudoers.d/jgl-deploy-ota` — se "Opdatere produktion" nedenfor) |
| Repo | klonet til `/opt/moviedb` fra `main`-branchen, via en **read-only deploy key** (ikke en personlig adgangstoken) — se GitHub repo → Settings → Deploy keys, "moviedb-prod-server" |

## Komponenter

| Komponent | Hvordan | Port/binding |
|---|---|---|
| MongoDB | `mongodb-org` 8.0 (MongoDB's officielle apt-repo, bookworm-pakken — trixie har endnu ingen egen) | `127.0.0.1:27017` (systemd: `mongod`) |
| Backend | Python venv (`/opt/moviedb/backend/.venv`) + uvicorn | `127.0.0.1:8000` (systemd: `moviedb-backend`) |
| Frontend | `npm run build` → statiske filer i `/opt/moviedb/frontend/dist`, serveret af Caddy | — |
| Reverse proxy / TLS | Caddy 2, `/etc/caddy/Caddyfile` | `:443` (HTTPS, selvsigneret via `tls internal`), `:80` (redirect til HTTPS) |

Kun port 22 (SSH), 80 og 443 er åbne udefra (`ufw`). MongoDB og backend er kun tilgængelige på `localhost` — nås udelukkende via Caddys reverse proxy.

Certifikatet er **selvsigneret** (Caddys interne CA, samme tilgang som dev-serveren) — telefonen/browseren skal acceptere sikkerhedsadvarslen første gang. Intet domænenavn er sat op, så en rigtig Let's Encrypt-cert er ikke muligt lige nu (kræver et domæne der peger på serveren).

**Vigtigt (se BUGS.md #23)**: Caddys interne CA-hierarki roterer *automatisk og hyppigt* — root-certifikatet er langtidsholdbart (~10 år), men det udstedte **intermediate**-certifikat roteres hver **7. dag**, og selve **leaf**-certifikatet der reelt serveres roteres hver **12. time**. En browser-sikkerhedsundtagelse der kun blev accepteret for det *specifikke* certifikat (fx Firefox' "Tilføj undtagelse", som er bundet til certifikatets fingerprint, ikke selve CA'en) holder derfor kun indtil næste rotation — herefter fejler baggrunds-`fetch()`-kald (API-kald) stille med en netværksfejl (typisk `NetworkError when attempting to fetch resource` i Firefox), selvom selve siden stadig kan loade fra cache. **Den korrekte, holdbare løsning er at importere selve root-CA'en** som en betroet rod-autoritet på hver klientenhed (ikke bare klikke sig forbi advarslen) — så holder tilliden på tværs af alle fremtidige intermediate-/leaf-rotationer uden gentagne advarsler. Root-certifikatet kan hentes fra serveren via Caddys admin-API (kun tilgængeligt lokalt på serveren): `curl -s http://127.0.0.1:2019/pki/ca/local` (JSON-felt `root_certificate`).

**HTTP/3 er slået fra** (`servers { protocols h1 h2 }` i Caddyfile'ens globale block). Caddy annoncerer ellers HTTP/3 (QUIC/**UDP** 443) via en `Alt-Svc`-header, men `ufw` åbner kun **TCP** 443 — browseren forsøger så at opgradere til QUIC, det fejler stille mod den lukkede UDP-port, og det viste sig i Firefox som `SSL_ERROR_INTERNAL_ERROR_ALERT` i stedet for det forventede "usikker forbindelse, fortsæt alligevel"-varsel. Løsningen er enten at slå HTTP/3 fra (valgt her — unødvendigt for en lille LAN-app) eller at åbne UDP 443 i firewallen også.

## `.env` (produktion)

Ligger i `/opt/moviedb/backend/.env` (git-ignoreret, `chmod 600`, ejes af `jgl`). Indeholder en **unik** `JWT_SECRET_KEY` genereret direkte på serveren (ikke genbrugt fra dev), `TMDB_API_TOKEN`, og `COOKIE_SECURE=true` (rigtig HTTPS i produktion). `DISCOGS_TOKEN` er tom (Discogs-opslag virker uden token, bare med lavere rate-limit — se MOVIE_API_REFERENCE.md).

## Opdatere produktion til en ny version

### Via "Opdatér fra GitHub"-knappen (feature #20, anbefalet)

Indstillinger-siden har en **admin-only** "Opdatér fra GitHub"-knap. Den kalder `POST /api/system/deploy`, som starter `/opt/moviedb-deploy.sh` i baggrunden (`git pull` + geninstaller afhængigheder + `npm run build`) og svarer med det samme — siden poller derefter `/api/health`s `build`-felt indtil den nye version er oppe (typisk under et minut). Se ARCHITECTURE.md's note om OTA-opdatering for de tekniske detaljer.

**Live-verificeret** 2026-08-01 (efter at have fanget og rettet to reelle sandbox-relaterede fejl — se BUGS.md #18): hele kæden kørt igennem direkte inde i den *faktiske* sandboxede mount-namespace for den kørende `moviedb-backend`-proces (via `nsenter` på processens PID, ikke et almindeligt shell), for at reproducere præcis den kontekst en rigtig admin-klik kører i. `git pull` → `pip install` → `npm run build` → trigger-fil → automatisk genstart af `moviedb-backend` + genindlæsning af `caddy` gennemført uden fejl, `moviedb-backend`s `ActiveEnterTimestamp` bekræftede en reel genstart, `/api/health` svarede korrekt undervejs og efter. Selve knappen (admin-login → klik → polling i browseren) er endnu ikke afprøvet af Jan, men den underliggende mekanisme er nu verificeret i den rigtige runtime-kontekst.

**Vigtigt om `moviedb-backend.service`'s sandboxing**: servicen kører med `ProtectSystem=strict` + `NoNewPrivileges=true` (se opsætning nedenfor). `NoNewPrivileges=true` gør `sudo` **permanent ubrugeligt** for servicen og alle dens child-processer, uanset sudoers-opsætning — deploy-scriptet bruger derfor **ikke** `sudo` til at genstarte services. I stedet rører scriptet en trigger-fil (`/opt/moviedb/.deploy-restart-trigger`), som en separat, ikke-sandboxed root-ejet systemd path-unit (`moviedb-deploy-restart.path` → `.service`) reagerer på og udfører den faktiske genstart/reload. Se `scripts/moviedb-deploy-restart.path` og `scripts/moviedb-deploy-restart.service`.

**Opsætning på serveren** (kun nødvendigt én gang, eller hvis `scripts/deploy.sh`/de to nye unit-filer ændres i repoet):

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

`/etc/caddy/Caddyfile`:

```caddyfile
{
    servers {
        protocols h1 h2
    }
}

10.1.130.10 {
    tls internal

    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle {
        root * /opt/moviedb/frontend/dist
        file_server
        try_files {path} /index.html
    }
}
```

Valideret før brug (`sudo caddy validate --config /etc/caddy/Caddyfile`), derefter `sudo systemctl enable --now caddy`.

Den globale `protocols h1 h2`-block blev tilføjet **efter** første opsætning, som en rettelse — se `SSL_ERROR_INTERNAL_ERROR_ALERT`-noten under "Komponenter" ovenfor.

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
