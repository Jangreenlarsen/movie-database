# Deployment (produktion)

Produktion kører **native** på en dedikeret Debian-server — ikke Docker Compose. `docker-compose.yml` i repo-roden er fra det oprindelige scaffold og er aldrig blevet færdiggjort/verificeret (se FEATURES.md #10); den bruges ikke.

---

## Server

| | |
|---|---|
| OS | Debian 13 (trixie) |
| Host | `10.1.130.10` (kun tilgængelig på hjemmenetværket — intet domænenavn) |
| Bruger | `jgl` (har passwordless sudo via `/etc/sudoers.d/jgl-deploy`) |
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

## `.env` (produktion)

Ligger i `/opt/moviedb/backend/.env` (git-ignoreret, `chmod 600`, ejes af `jgl`). Indeholder en **unik** `JWT_SECRET_KEY` genereret direkte på serveren (ikke genbrugt fra dev), `TMDB_API_TOKEN`, og `COOKIE_SECURE=true` (rigtig HTTPS i produktion). `DISCOGS_TOKEN` er tom (Discogs-opslag virker uden token, bare med lavere rate-limit — se MOVIE_API_REFERENCE.md).

## Opdatere produktion til en ny version

Når en release er merget til `main` og pushet:

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
