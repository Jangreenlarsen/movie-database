# Deployment (produktion)

Produktion kører **native** på en dedikeret Debian-server — ikke Docker Compose. `docker-compose.yml` i repo-roden er fra det oprindelige scaffold og er aldrig blevet færdiggjort/verificeret (se FEATURES.md #10); den bruges ikke.

---

## Server

| | |
|---|---|
| OS | Debian 13 (trixie) |
| Host | `10.1.130.10` (hjemmenetværket), `movie.ll.lan` (intern DNS), og offentligt via `movie.laces.dk` (se "Offentlig adgang" nedenfor) |
| Hypervisor | Kører som **gæste-VM under Synology Virtual Machine Manager** på `ds5.ll.lan`/`10.1.1.17` — ikke bare metal. "Native" i denne fils overskrift betyder fortsat *ingen Docker inde i gæsten*, ikke at gæsten selv kører uden virtualisering. Se feature #152/FEATURES.md for en genanvendelig VM-skabelon af denne stack til import i VMM. |
| Bruger | `jgl` (har **kun** snæver passwordless sudo til to specifikke kommandoer, via `/etc/sudoers.d/jgl-deploy-ota` — se "Opdatere produktion" nedenfor) |
| Repo | klonet til `/opt/moviedb` fra `main`-branchen, via en **read-only deploy key** (ikke en personlig adgangstoken) — se GitHub repo → Settings → Deploy keys, "moviedb-prod-server" |

### Offentlig adgang (`movie.laces.dk`)

Siden 2026-08-09 er appen desuden nået fra det åbne internet via `movie.laces.dk`, gennem en **separat nginx-reverse-proxy-VM** (ikke Caddy, ikke beskrevet ovenfor) der terminerer TLS (Let's Encrypt) og videresender til `10.1.130.10:443` over et privat netværkssegment — proxyen fungerer samtidig som NAT-gateway for appserverens segment, da dettes egen router-SVI bevidst er fjernet. Fuld arkitektur, netværkstopologi og genetablerings-trin står i `movie-laces-dk-runbook.md` i repo-roden (**bevidst git-ignoreret** — indeholder adgangsoplysninger til den infrastruktur og må aldrig committes, se BUGS.md #66). Konsultér den fil direkte, ikke denne, ved arbejde på proxy-laget.

**Vigtigt for enhver langvarig/streaming-respons (SSE, chunked)**: denne nginx-VM's `location /`-blok manglede oprindeligt `proxy_http_version 1.1;`, hvilket fik nginx til at tale HTTP/1.0 med Caddy og reelt buffere hele svaret til forbindelsen lukkede — for en uendelig strøm (fx AVM70-diagnostikken, BUGS.md #82) betød det at intet nogensinde nåede klienten. Rettet 2026-08-21 (`proxy_http_version 1.1;` + `proxy_buffering off;` tilføjet). En hvilken som helst FREMTIDIG SSE-/streaming-endpoint arves automatisk af rettelsen, da den ikke er sti-specifik — men vær opmærksom på at et fremtidigt genetableret proxy-VM (se runbook'ens afsnit 7) skal have samme to linjer med, hvis genetableringstrinene deri ikke allerede er opdateret til at inkludere dem.

## Komponenter

| Komponent | Hvordan | Port/binding |
|---|---|---|
| MongoDB | `mongodb-org` 8.0 (MongoDB's officielle apt-repo, bookworm-pakken — trixie har endnu ingen egen) | `127.0.0.1:27017` (systemd: `mongod`) |
| Backend | Python venv (`/opt/moviedb/backend/.venv`) + uvicorn | `127.0.0.1:8000` (systemd: `moviedb-backend`) |
| Frontend | `npm run build` → statiske filer i `/opt/moviedb/frontend/dist`, serveret af Caddy | — |
| Reverse proxy / TLS | Caddy 2, `/etc/caddy/Caddyfile` | `:443` (HTTPS), `:80` (redirect til HTTPS) |

Kun port 22 (SSH), 80 og 443 er åbne udefra (`ufw`). MongoDB og backend er kun tilgængelige på `localhost` — nås udelukkende via Caddys reverse proxy.

### TLS-certifikat (se BUGS.md #23)

Sitet serveres nu på to adresser med to forskellige certifikater (Caddyfile har to site-blocks, der deler handler-logik via en `(common)`-snippet):

- **`https://movie.ll.lan`** (primær, anbefalet adresse) — rigtigt certifikat udstedt af Jans **interne Windows AD CS-CA** (`ll-AD-CA`, allerede betroet på hans enheder), gyldigt 2 år (2026-08-02 → 2028-08-01), fil: `/etc/caddy/certs/movie.ll.lan.{crt,key}` (root:caddy, 640). Kræver en intern DNS-post for `movie.ll.lan` → `10.1.130.10`. Ingen certifikat-advarsler, ingen manuel per-enhed import nødvendig (enhederne stoler allerede på `ll-AD-CA`).
- **`https://10.1.130.10`** (midlertidig fallback, IP-baseret) — stadig Caddys egen selvsignerede `tls internal`, med samme rotations-svaghed som beskrevet i BUGS.md #23 (leaf roterer hver 12. time, intermediate hver 7. dag). Bevaret bevidst under overgangen, så eksisterende bogmærker/PWA-ikoner ikke brækker akut — udfases når alle enheder er skiftet til `movie.ll.lan`.

**Sådan blev certifikatet udstedt** (manuel CSR-signering, ikke ACME — Jans interne CA understøtter ikke automatisk udstedelse): en ECDSA P-256-nøgle + CSR (CN+SAN=`movie.ll.lan`) blev genereret direkte på serveren (nøglen forlod aldrig serveren), CSR'en blev signeret af Jans interne CA via Windows-certifikatanmodning, det signerede certifikat (`certnew.cer`, DER-format) og CA-rodcertifikatet (`CA.cer`) blev konverteret til PEM og verificeret (public key-hash) til at matche den lokale private nøgle, før det blev installeret.

**Fornyelse (fra 2026-08-03, via appen — feature #73, anbefalet)**: Indstillinger-siden har nu en admin-only "TLS-certifikat"-sektion der kan generere en ny CSR eller importere en færdig PKCS12 direkte i UI'et, uden manuel SSH-adgang. Se afsnittet "TLS-certifikat via appen" nedenfor. Den oprindelige manuelle proces (næste afsnit) er stadig gyldig som fallback, fx hvis backend'en slet ikke kan starte.

**Sådan blev det oprindelige certifikat udstedt manuelt** (CSR-signering, ikke ACME — Jans interne CA understøtter ikke automatisk udstedelse): en ECDSA P-256-nøgle + CSR (CN+SAN=`movie.ll.lan`) blev genereret direkte på serveren (nøglen forlod aldrig serveren), CSR'en blev signeret af Jans interne CA via Windows-certifikatanmodning, det signerede certifikat (`certnew.cer`, DER-format) og CA-rodcertifikatet (`CA.cer`) blev konverteret til PEM og verificeret (public key-hash) til at matche den lokale private nøgle, før det blev installeret.

**Udløb**: certifikatet udløber 2028-08-01 — brug fremover "TLS-certifikat"-sektionen i Indstillinger til fornyelse i god tid inden da (ingen automatisk fornyelse).

**Den tidligere manuelle sudoers-regel er ikke længere nødvendig**: `/etc/sudoers.d/jgl-tls-cert-install` (snævert scopet til install/`caddy validate`/`systemctl reload caddy`) blev brugt til at lade Claude installere det *oprindelige* certifikat via SSH. Feature #73's `moviedb-cert-install`-systemd-unit (se nedenfor) overtager denne rolle uden sudo overhovedet — reglen kan fjernes (`sudo rm /etc/sudoers.d/jgl-tls-cert-install`) når/hvis den nye unit er sat op og afprøvet.

### TLS-certifikat via appen (feature #73)

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

### Offentligt domæne + automatisk Let's Encrypt-certifikat (feature #74)

Både `movie.ll.lan` og `10.1.130.10` er **kun** nåbare fra hjemmenetværket (intern DNS hhv. ingen router-portviderledning udefra) — hverken Let's Encrypt eller nogen anden public CA kan udstede til et privat IP eller et internt-kun-navn under alle omstændigheder. Jans ønske (2026-08-03) om ægte adgang udefra kræver derfor et **rigtigt, offentligt domænenavn** (DNS hos one.com/Larsen Data, fast offentlig IP bekræftet) og et **tredje** Caddy site-block — helt adskilt fra de to LAN-certifikater ovenfor, som forbliver uændrede.

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

Ligger i `/opt/moviedb/backend/.env` (git-ignoreret, `chmod 600`, ejes af `jgl`). Indeholder en **unik** `JWT_SECRET_KEY` genereret direkte på serveren (ikke genbrugt fra dev), `TMDB_API_TOKEN`, og `COOKIE_SECURE=true` (rigtig HTTPS i produktion). `DISCOGS_TOKEN` er tom (Discogs-opslag virker uden token, bare med lavere rate-limit — se MOVIE_API_REFERENCE.md).

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
