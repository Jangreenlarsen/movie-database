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
    # Feature #178 (Jan: "når man trykker på vis i plex så er option at
    # starte den i plex på shield der også") — Plex' egen client-id for
    # Nvidia Shield TV Pro'en, fundet én gang via GET /api/plex/clients og
    # gemt her. Ikke en hemmelighed (en Plex-intern GUID, ingen adgang i sig
    # selv) — samme "vis faktisk værdi"-princip som plex_server_url.
    plex_shield_client_identifier: str = ""

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

    # Feature #177 (Jan: "vi skal kunne sætte om guest ved film forvisnings
    # ønske skal bruge dato/tid eller ikke"), udvidet af feature #186 (Jan,
    # 2026-08-20: "angivning af dato/tid for forvisning skal gælde for alle
    # roller og ikke kun guest") — gjaldt oprindeligt kun gæste-rollen
    # (standard/admin var altid ufravigeligt krævet); omdøbt fra
    # `require_preferred_at_for_guests` og gælder nu alle roller ens. Default
    # `true` matcher feature #176's oprindelige opførsel, indtil en admin
    # slår den fra. Læst dynamisk af `screening_service.enforce_preferred_at`.
    require_preferred_at: bool = True

    # Feature #217 (Jan: "vi skal have en funktion for adm i settings hvor
    # vi kan sætte at 'test' tilstand som primæret vil betyde at email og
    # beskeder ikke sendes ud af system i test mode"). Ingen .env-modstykke,
    # samme mønster som adgangskode-politikken — kun sat via
    # PATCH /api/settings/test-mode. Default `false`: må aldrig glide stille
    # igennem til produktion (CLAUDE.md regel 16's "usikre default-værdier
    # skal advare/nægte" gælder i ånden også en tilstand der stille
    # undertrykker rigtige notifikationer). Læst dynamisk af
    # message_service.send() ved hvert kald.
    test_mode: bool = False

    # Feature #181 (Jan: "jeg tro tilgengæld at vi skal have en automatisk
    # scan af plex media server for ny film og tv serie, i dag er det en
    # manual funktion"). Ingen .env-modstykke, samme mønster som
    # adgangskode-politikken — kun sat via PATCH /api/settings/plex-auto-import.
    # Default `false`: en helt ny automatiseret handling der selv opretter
    # poster i biblioteket skal ikke stille og roligt begynde at køre uden
    # en admins eksplicitte tilvalg (i modsætning til fx feature #180, som
    # var en indskrænkning af noget der allerede kørte for alle).
    plex_auto_import_enabled: bool = False
    # Minutter mellem hver scan når slået til. 360 (6 timer) er Jans egen
    # anbefaling ved opklarende spørgsmål — fanger nye film/serier samme dag
    # uden at belaste Plex-serveren unødigt ofte. Læst dynamisk hver
    # iteration af `plex_service.run_auto_import_loop`, så en ændring slår
    # igennem med det samme, uden genstart.
    plex_auto_import_interval_minutes: int = 360
    # Delt mellem den manuelle "Importér fra Plex"-knap og auto-scan-loopet
    # ovenfor (Jan: "søger for at tag på importerede i auto-scan plex er det
    # tag som er difineret under 'importer fra plex'") — én fælles
    # definition i stedet for to steder der kan drifte fra hinanden. Sat via
    # `import_from_plex` selv (se plex_service.py) hver gang en admin (ikke
    # auto-scan-aktøren) kører en rigtig, ikke-dry-run import — bliver
    # dermed "den seneste faktisk brugte tag", som auto-scan derefter læser.
    plex_import_tag: str = "Plex-import"

    # Feature #183 (Jan: "lave en undersøgelse af hvad mulighed vi har for
    # at remote kontrollere AVM70"). Anthem AVM 70-lydprocessoren i Voldby
    # BIO, styret via `anthemav`-biblioteket (rå TCP, port 14999). Ikke en
    # hemmelighed — bare en LAN-adresse, samme "vis faktisk værdi"-princip
    # som plex_server_url ovenfor. Sat via SystemSettingsSection, ikke
    # diagnostik-siden selv (samme sted som Plex-server-URL'en).
    anthem_host: str = ""
    anthem_port: int = 14999

    # Feature #197 — udgående e-mail-notifikationer via Resend
    # (https://resend.com), en HTTP-API-baseret transaktions-mail-udbyder
    # (Jans valg, efter at være gjort opmærksom på at appen ikke har nogen
    # privat postserver). `resend_api_key` er en rigtig hemmelighed (masket,
    # samme mønster som tmdb_api_token ovenfor). `email_from_address` er
    # IKKE en hemmelighed — den optræder i hver afsendt mails synlige
    # "Fra"-felt uanset, så den vises med sin faktiske værdi via
    # GET /api/settings/system, samme princip som plex_server_url/anthem_host.
    # Ingen separat "slået til"-kontakt: er begge sat, forsøges e-mails
    # sendt — præcis som TMDb/Discogs/OMDb/Plex ikke har deres egen
    # aktiverings-boks ud over selve nøglen.
    resend_api_key: str = ""
    email_from_address: str = ""

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
    "plex_shield_client_identifier": settings.plex_shield_client_identifier,
    "primary_barcode_source": settings.primary_barcode_source,
    "anthem_host": settings.anthem_host,
    "resend_api_key": settings.resend_api_key,
    "email_from_address": settings.email_from_address,
    # anthem_port er bevidst UDELADT her: denne dict bruges kun til at
    # falde tilbage til .env-værdien når en admin rydder en override tilbage
    # til tom streng (se system_settings_service.update_settings) — det
    # sammenligner `value != ""`, som for et int-felt aldrig er sandt, så
    # grenen der læser herfra kan aldrig rammes for anthem_port alligevel.
}
