from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_JWT_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "moviedb"

    tmdb_api_token: str = ""
    discogs_token: str = ""
    # Tredje stregkode-opslags-fallback (efter UPCitemdb og Discogs) — fri
    # niveau, 100 opslag/dag, se MOVIE_API_REFERENCE.md. Tilføjet 2026-08-03
    # for at forsøge bedre dækning af nordiske DVD/Blu-ray-stregkoder, som
    # hverken UPCitemdb eller Discogs typisk har katalogiseret.
    upcdatabase_token: str = ""
    # Fjerde stregkode-opslags-fallback (efter UPCitemdb, Discogs,
    # UPCDatabase.org) — betalt konto, Jans eget køb 2026-08-03 i håb om
    # bedre dansk/nordisk EAN-dækning end de tre gratis kilder.
    ean_search_api_key: str = ""
    # Faktisk IMDb-rating (feature #46) — TMDb's egen vote_average er ikke
    # det samme tal som vises på imdb.com.
    omdb_api_key: str = ""

    # Plex-integration (feature #45) — server_url er ikke en hemmelighed
    # (bare en LAN-adresse) og eksponeres derfor med sin faktiske værdi via
    # GET /api/settings/system, i modsætning til token'et og de tre nøgler
    # ovenfor, som altid kun rapporterer configured/source.
    plex_server_url: str = ""
    plex_token: str = ""

    # Feature #88 — hele Plex-biblioteket hentes i ét hug og caches, i stedet
    # for ét opslag pr. film. TTL'en er afvejningen mellem "badges er friske
    # efter du lige har lagt en film i Plex" og "biblioteksvisningen belaster
    # ikke Plex-serveren ved hver eneste sideskift". 0 slår cachen fra.
    plex_cache_ttl_seconds: int = 300
    # Plex' egne certifikater udstedes til *.plex.direct og validerer derfor
    # ikke mod en rå LAN-IP over https. Sæt til false hvis plex_server_url
    # peger på https:// med et selvsigneret/ikke-matchende certifikat —
    # trafikken er stadig krypteret, men værtsnavnet verificeres ikke.
    plex_verify_ssl: bool = True

    # Hvilken stregkode-kilde der prøves FØRST (feature #77) — resten af de
    # fire (se scan_service.BARCODE_SOURCES) prøves stadig som fallback i
    # deres normale rækkefølge, bare med denne trukket forrest. Ikke en
    # hemmelighed — samme "vis faktisk værdi"-princip som plex_server_url.
    primary_barcode_source: str = "upcitemdb"

    # Adgangskode-politik (feature #174, Jan: "vi skal have en password
    # politik config del i setting"). Ingen .env-modstykke (giver ikke
    # mening at sætte fra miljøvariabler) — kun her som kode-standarder, der
    # matcher den hidtidige faste opførsel (min_length=8, ingen
    # kompleksitetskrav), indtil en admin ændrer dem via
    # PATCH /api/settings/password-policy. Læst dynamisk af
    # `models.user.validate_password_policy` ved hver adgangskode-sætning
    # (registrering, eget skift, admin-genereret midlertidig kode).
    password_min_length: int = 8
    password_require_uppercase: bool = False
    password_require_lowercase: bool = False
    password_require_digit: bool = False

    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    jwt_secret_key: str = INSECURE_DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    # Feature #148 — 8 timers skydende idle-timeout (Jans ønske 2026-08-13): en
    # aktiv bruger smides aldrig ud midt i arbejdet (sessionen forlænges ved
    # aktivitet, se _sliding_session-middleware i main.py), men 8 timers
    # inaktivitet lader cookien/tokenet udløbe. Både JWT-`exp` og cookiens
    # Max-Age læser herfra.
    jwt_expire_minutes: int = 60 * 8  # 8 timer
    cookie_secure: bool = False

    # OTA-opdatering (feature #20) — kun meningsfuldt i produktion, se DEPLOYMENT.md.
    # Scriptet ligger bevidst uden for git-working-tree'en (/opt/moviedb), så
    # `git pull` aldrig overskriver den fil der er ved at blive eksekveret.
    deploy_script_path: str = "/opt/moviedb-deploy.sh"
    deploy_log_path: str = "/opt/moviedb-deploy.log"
    # BUGS.md #36 — deploy.sh skriver sit udfald hertil (up-to-date/updated),
    # så frontend kan skelne "intet nyt at hente" fra en reel fejl i stedet
    # for udelukkende at gætte ud fra om build-nummeret ændrede sig.
    deploy_status_path: str = "/opt/moviedb/.deploy-status"
    # Feature #154 — samme trigger-fil deploy.sh selv rører til sidst; en ren
    # "genstart nu" (uden git pull/npm build) rører den bare direkte.
    deploy_restart_trigger_path: str = "/opt/moviedb/.deploy-restart-trigger"
    # Feature #154 — genstart af HELE serveren (fysisk/VM), ikke kun
    # backend-tjenesten. Nyt, separat root-ejet systemd-trigger, samme
    # sudo-fri mønster som deploy/cert ovenfor — se DEPLOYMENT.md.
    reboot_trigger_path: str = "/opt/moviedb/.reboot-trigger"

    # TLS-certifikat-styring (feature #73) — kun meningsfuldt i produktion,
    # se DEPLOYMENT.md/BUGS.md #23. `cert_live_path` er den faktisk
    # installerede Caddy-cert (root:caddy, 640 — kræver læse-adgang, se
    # DEPLOYMENT.md). `cert_staging_dir` er indenfor `moviedb-backend`s egen
    # ReadWritePaths, hvor en ny nøgle/CSR/cert lægges midlertidigt før
    # installation. Samme ikke-sudo-trigger-mønster som deploy ovenfor.
    cert_live_path: str = "/etc/caddy/certs/movie.ll.lan.crt"
    cert_staging_dir: str = "/opt/moviedb/certs/pending"
    cert_install_trigger_path: str = "/opt/moviedb/.cert-install-trigger"
    cert_common_name: str = "movie.ll.lan"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def using_insecure_jwt_secret(self) -> bool:
        return self.jwt_secret_key == INSECURE_DEFAULT_JWT_SECRET


settings = Settings()

# Immutable snapshot of the .env-derived values, taken once at import time —
# used to restore the "no override" value when an admin clears a custom
# key via `PATCH /api/settings/system` (feature #36). `settings` itself gets
# mutated in place at runtime (see system_settings_service), so this is the
# only remaining record of what .env actually provided.
ENV_DEFAULT_API_KEYS: dict[str, str] = {
    "tmdb_api_token": settings.tmdb_api_token,
    "discogs_token": settings.discogs_token,
    "upcdatabase_token": settings.upcdatabase_token,
    "ean_search_api_key": settings.ean_search_api_key,
    "omdb_api_key": settings.omdb_api_key,
    "plex_server_url": settings.plex_server_url,
    "plex_token": settings.plex_token,
    "primary_barcode_source": settings.primary_barcode_source,
}
