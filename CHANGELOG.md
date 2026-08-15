# Changelog

Nyeste øverst. Hver entry tagges med `[version build NNNN]` (jf. CLAUDE.md regel 4).

## [0.130.0 build 0176] — 2026-08-15 — feature: paginering af "Slettede film" i Indstillinger (FEATURES.md #155)

Jan: *"Deleted movies i settings skal være en page model med 10 max per side sådan den ikke kommer til at fylde hele siden op hvis der er mange slette film."* Listen hentede før op til 1000 slettede film i ét kald og viste dem alle i ét langt scroll. `GET /api/movies/deleted?skip=&limit=` (standard 10) returnerer nu `{entries, total}` i stedet for en rå liste — samme form som audit-loggens paginering (feature #65), og frontend genbruger dens præcise "← Forrige"/"Side X af Y"/"Næste →"-UI og oversættelser uændret. Ny `DeletedMoviePage`-model, ny `movie_repository.count_deleted`. TV-serier har ingen tilsvarende sektion i Indstillinger i dag og er ikke rørt. Berørte filer: `backend/app/models/movie.py`, `backend/app/repositories/movie_repository.py`, `backend/app/services/movie_service.py`, `backend/app/api/movies.py`, `frontend/src/api/client.js`, `frontend/src/pages/Settings.jsx`. Tests: `test_deleted_movies.py`/`test_database_reset.py` opdateret til det nye svar-format. Fuld backend-suite + frontend (62) grøn.

## [0.129.0 build 0175] — 2026-08-15 — feature: systemovervågnings-side under Indstillinger → Drift (FEATURES.md #154)

Jan: *"og lave en monitor side under settings hvor vi kan se status helbred på system samt genstart server se cpu ram disk m.m."* Ny admin-only sektion øverst under Drift: CPU/RAM/disk (via `psutil`) + status for `mongod`/`caddy`/`moviedb-backend` (via `systemctl is-active`, Linux-only, falder pænt tilbage uden for Linux). To genstarts-handlinger (Jan valgte "begge dele" da han blev spurgt): "Genstart tjeneste" (ingen adgangskode, genbruger den eksisterende `moviedb-deploy-restart`-trigger-fil) og "Genstart serveren" (kræver admins eget password, ny `moviedb-reboot.path`/`.service` — samme sudo-frie trigger-fil-mønster som deploy-flowet, nødvendigt fordi `moviedb-backend.service`s `NoNewPrivileges=true` gør `sudo`/`reboot` permanent utilgængeligt for servicen selv). Begge logges i audit-loggen. Frontend poller status hvert 10. sekund via `X-Background-Poll` (feature #148 — må ikke forlænge en uovervåget idle-session) og venter derefter på at `/api/health` svarer igen efter en udløst handling. Ingen backup/restore-ændring nødvendig (regel 20) — monitor-data er live driftsdata, ikke et persisteret datasæt. Berørte filer: `backend/app/services/monitor_service.py` (ny), `backend/app/models/monitor.py` (ny), `backend/app/api/monitor.py` (ny), `backend/app/core/config.py`, `backend/app/core/errors.py`, `backend/app/main.py`, `backend/requirements.txt`, `scripts/moviedb-reboot.path` (ny), `scripts/moviedb-reboot.service` (ny), `frontend/src/api/client.js`, `frontend/src/pages/Settings.jsx`, `frontend/src/pages/Settings.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `DEPLOYMENT.md`. Tests: `test_monitor.py` (ny, 7), `Settings.test.jsx` (ny, `formatUptime`). Fuld backend-suite (657) + frontend (62) grøn. **Rettelse 2026-08-15**: denne entry påstod oprindeligt fejlagtigt "set i browser" (regel 18) — admin-login til Drift-fanen blev reelt aldrig opnået (forsøg på at give en test-bruger admin-rolle i dev-databasen blev blokeret som rettigheds-eskalering), så kun build/lint/tests er faktisk verificeret, se FEATURES.md #154.

## [0.127.1 build 0173] — 2026-08-14 — juster: appliance-skabelon skiftet til bruger/adgangskode-login (FEATURES.md #152)

Jan, efter første import-forsøg: *"lave ny OVA som ikke er lås ind til key fil men kun user/pass og så skal vi have en init setup rutine kørt i console ved første gangs login"*. `jgl` har nu almindeligt bruger/adgangskode-login (bootstrap-adgangskode i `packer/variables.pkr.hcl`, tvunget skiftet ved første login via `chage -d 0`) i stedet for SSH-nøgle-only — konsol-login i VMM virker nu uden en nøglefil. Ny `scripts/moviedb-welcome-profile.sh` (installeret som `/etc/profile.d/`) viser hostname + DHCP-IP ved første login (konsol eller SSH) — løser at en frisk importeret VM ikke havde nogen synlig IP. Rettede undervejs en reel fejl: sudo-opsætningen lå i `provision.sh`, som selv kræver sudo for at starte — løst ved at sende adgangskoden ind til det første `sudo`-kald. Kendt VMM-boot-fejl dokumenteret (UEFI `Shell>` ved boot-mode-mismatch, løses ved at sætte Legacy BIOS i VM-indstillingerne). **Status**: build afventer stadig en vellykket kørsel (ramte undervejs en Windows Defender-relateret performance-flaskehals under gentagne builds på denne maskine — ikke en fejl i skabelonen) — sat i bero efter Jans prioritering af databaseproblemet (FEATURES.md #153) frem for appliance-arbejdet. Berørte filer: `packer/*`, `scripts/moviedb-welcome-profile.sh` (ny), `DEPLOYMENT.md`.

## [0.128.0 build 0174] — 2026-08-14 — feature: permanent lokal poster-cache (FEATURES.md #153)

Jan (opdaget under en ægte internet-udsving på prod): *"da der ikke var inet kunne jeg se alt men ikke billeder ... find ud af hvordan vi få hentet ... fra extern server en gang og cache det for altid i backend"*. `poster_url` har altid været en fuld TMDb-CDN-URL — frontend hentede derfor postere direkte fra TMDb ved hver sidevisning, uafhængigt af vores egen backend. Ny doven cache: ny `poster_cache`-collection (unikt index `(size, path)`), ny login-fri endpoint `GET /api/posters/{size}/{path}` (skal virke på den offentlige `/bio`-side), ny `tmdb_client.fetch_poster_image` + `poster_cache_service.get_or_fetch`. `posterUrl.js` peger nu på vores egen endpoint i stedet for TMDb direkte — dækker hele det eksisterende bibliotek automatisk, uden migrering. `mongo_json.py` udvidet med `{"$binary": ...}`-kodning (base64) for BSON `Binary`. `poster_cache` føjet til den fulde system-backup (regel 20), bevidst ikke ryddet af `/api/system/reset`. Berørte filer: `backend/app/repositories/poster_cache_repository.py` (ny), `backend/app/services/poster_cache_service.py` (ny), `backend/app/api/posters.py` (ny), `backend/app/integrations/tmdb_client.py`, `backend/app/core/mongo_json.py`, `backend/app/models/backup.py`, `backend/app/services/system_backup_service.py`, `backend/app/main.py`, `frontend/src/utils/posterUrl.js`, `ARCHITECTURE.md`. Tests: `test_posters.py` (ny, 5), `test_system_backup.py` udvidet, `posterUrl.test.js` opdateret. Fuld backend-suite (650) + frontend grøn.

## [0.127.0 build 0172] — 2026-08-14 — feature: genanvendelig VM-skabelon til Synology VMM (FEATURES.md #152)

Jan: *"kan vi lave en ova eller hvad esx og synology vmm kræver for install på deres hyperviser af vores prod server?"* → afklaret til en **frisk, genanvendelig skabelon**, ikke en klon af den kørende prod-VM. Ny `packer/`-mappe: en HashiCorp Packer-skabelon (VirtualBox lokalt) der installerer Debian 13 unattended og provisionerer basissystemet 1:1 efter DEPLOYMENT.md's installations-log (MongoDB 8.0, Node 22, Caddy, ufw), eksporteret til `.ova` — Synology VMM's dokumenterede importformat. Ingen hemmeligheder/data bagt ind: kun SSH-nøgle-login for `jgl` (ingen adgangskode), ingen appkode/secrets — de forbliver et kort manuelt trin efter import. Ny fil `scripts/moviedb-backend.service` (var hidtil kun prosa i DEPLOYMENT.md). DEPLOYMENT.md opdateret: prod kører faktisk som gæste-VM under Synology VMM (`ds5.ll.lan`/`10.1.1.17`), samt `movie.laces.dk`s reverse-proxy-lag nævnt (uden secrets). **Bygget og lokalt verificeret** (regel 16): build lykkedes på 7 min 28 sek, den eksporterede `.ova` importeret+bootet igen i VirtualBox — SSH-nøgle-login OK, adgangskode-login reelt afvist, alle forventede services aktive/enablede, `moviedb-backend` korrekt inaktiv (appen ikke klonet endnu), ufw og MongoDB-binding korrekt. Automatisk upload til Synology'en via DSM's File Station-API stødte på en rettighedsfejl (kontoen kan ikke skrive til de mapper den ser) — filen ligger klar lokalt til manuel/efterfølgende upload. Ingen forbindelse til den kørende prod-VM `10.1.130.10` på noget tidspunkt. Berørte filer: `packer/*`, `scripts/moviedb-backend.service`, `DEPLOYMENT.md`.

## [0.126.2 build 0171] — 2026-08-14 — fix: klartekst-produktionsadgangskoder ubeskyttet i repo-roden (BUGS.md #66)

Opdaget under research til feature #152: `movie-laces-dk-runbook.md` (proxy-server-dokumentation) indeholder rigtige klartekst-adgangskoder til prod-infrastruktur, lå utracket men **ikke** i `.gitignore` — ét `git add -A` fra at blive committet til GitHub. Tilføjet `movie-laces-dk-runbook.md` + mønsteret `*-runbook.md` til `.gitignore`. Selve adgangskoderne er ikke roteret (uden for scope, kræver adgang til kørende infrastruktur) — Jan er gjort opmærksom på at rotation stadig udestår. Berørt fil: `.gitignore`.

## [0.126.1 build 0170] — 2026-08-14 — fix: system-backup/-restore manglede seks collections (BUGS.md #65)

Jan: *"det se ud til at backup/restore mangler en del"*. Feature #61's fulde system-backup dumpede kun movies/tv_shows/deleted/tags/users/counters — men siden er `screenings`/`screening_requests` (Voldby BIO's program), `seat_reservations` (feature #133), `messages` (feature #100), `audit_log` og `visits` kommet til uden at backup'en blev udvidet, så en gendannelse ville stiltiende have slettet programmet og alle sæde-reservationer. `SystemBackup`/`SystemRestoreResult` udvidet med alle seks. Fandt undervejs to relaterede huller: `reset_library` ryddede ikke `seat_reservations` (dinglende referencer til slettede screenings efter et bibliotek-reset) — rettet; og en første udgave lod restore erstatte `audit_log` wholesale, hvilket viste sig at slette dele af sit eget revisionsspor (`system_backup.created`-loggen skrives efter snapshottet tages, så den kan aldrig være med i det der gendannes) — rettet med en ny insert-only `_merge_raw_collection`, kun brugt til `audit_log`. Ny ufravigelig CLAUDE.md-regel (20): backup/restore skal tjekkes for huller som del af enhver feature der udvider et data-sæt, ikke bagefter. Tests: `test_system_backup.py`/`test_database_reset.py` udvidet, fuld suite (645) grøn.

## [0.126.0 build 0169] — 2026-08-14 — feature: mindre knap-tekst + fane-linjen ombryder på mobil (FEATURES.md #151)

Jan: *"gør tekst i de 3 felter mindre og se på hoved menu line da den også er meget lang på en mobil, kan vi ikke lave den i 2 line eventuelt"*. To mobil-justeringer (≤640px, ren CSS): (a) de tre værktøjs-knapper (Sortér/Filtrér/Vis felter) fik mindre tekst (`Library.css`, font 0.8→0.72rem). (b) Fane-linjen lå på én lang, vandret-scrollende linje — med 7 faner blev den for lang. Nu ombryder den til flere linjer (`App.css`: `flex-wrap:wrap`, `overflow-x:visible`, centreret, knap-font 0.9→0.82rem): 2 linjer ved ~390px, 3 ved ~320px. Ingen JSX-/i18n-ændring. Berørte filer: `frontend/src/pages/Library.css`, `frontend/src/App.css`. Regel 18: visuelt verificeret i Edge (playwright) ved 390px og 320px.

## [0.125.0 build 0168] — 2026-08-14 — feature: kompakt værktøjslinje på mobil (FEATURES.md #150)

Jan: *"sorte, filter, vis felter samt list view mode skal kunne være på en linie"*. Biblioteks-værktøjslinjen (delt af Film, TV og indkøbslisten) ombrød knapperne til flere linjer på en telefon. Ny mobil-regel (≤640px, ren CSS i `Library.css`): søgefeltet tvinges op på sin egen linje (`min-width:100%`), og de fire kontroller — Sortér, Filtrér, Vis felter + visnings-toggelen — lægges på linjen under, hvor de tre tekst-knapper deler bredden (`flex:1; min-width:0; white-space:nowrap`, så de aldrig ombryder til to linjer) og toggelen beholder sin bredde. Ingen JSX-/i18n-ændring. Berørt fil: `frontend/src/pages/Library.css`. Regel 18: visuelt verificeret i Edge (playwright) ved 360px og 320px — alle fire kontroller på én linje uden klipning.

## [0.124.0 build 0167] — 2026-08-14 — feature: kompakt hoved på mobil (FEATURES.md #149)

Jan: *"vi skal have se på layout når en mobil tlf er på, lige nu fylder portal for meget i primæet i breden"* (valg: topmenuen/hovedet). App-headeren fyldte for meget i bredden på en telefon. Opdater-knappen (#136) er nu kun ikon (🔄) på mobil: emoji'en flyttet fra `app.refresh`-strengen ud i JSX (`<span aria-hidden>🔄</span>` + `.header-btn-label` med teksten), labelen skjules under 640px via CSS, og knappen får strammere padding. Tættere afstande i hovedet på mobil: `.header-user` gap 10→6px, `.header-counts` gap 6→4px. Ingen ændring i hvad der vises — kun bredde-forbrug. Berørte filer: `frontend/src/App.jsx`, `frontend/src/App.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`. Ren frontend; i18n-parity uændret. Regel 18: bygget, afventer visuelt tjek på telefon.

## [0.123.0 build 0166] — 2026-08-13 — feature: 8 timers skydende idle-session-timeout (FEATURES.md #148)

Jan: *"Max-Age skal ned på 8 timer, men ... de 8 timer først fra når session bliver idel"*. Login-sessionen er sat fra 30 dage til **8 timer** (`jwt_expire_minutes`), men som en **skydende idle-timeout**: en ny `_sliding_session`-middleware gen-udsteder session-cookien med frisk 8-timers levetid ved hver aktivitet, så en aktiv bruger aldrig smides ud midt i arbejdet — 8 timers inaktivitet lader den udløbe. Undtaget: `/api/auth` (så logout ikke genoplives) og baggrunds-polls markeret med `X-Background-Poll` (besked-pollen hvert 20. sek, sat på `getInbox`), så et åbent uovervåget vindue faktisk timeouter. Ny pæn udløbs-håndtering: en 401 på et almindeligt endpoint fører nu tilbage til login (`setOnSessionExpired` i client.js → `setUser(null)` i App.jsx) frem for en rå fejl. Tests: `test_session_sliding.py` (4). Cookien er i forvejen httpOnly + SameSite=Lax + Secure (i produktion).

## [0.122.0 build 0165] — 2026-08-13 — feature: tilbyd at fjerne ønsket ved registrering til biblioteket (FEATURES.md #147)

Jan: *"ved registrering af film/tv ... og film/tv findes i ønske seksion skal man have valg ... om man vil slette den i ønske seksion"*. Bygger på #38/#128's dublet-tjek (`DuplicateMatch` bærer `is_wishlist` + `id`): gemmer man en kladde til biblioteket og en dublet er et ønske, spørger en dialog efter oprettelsen om ønsket skal fjernes fra indkøbslisten (Ja → `deleteMovie`/`deleteTvShow`). Kun ønske-dubletter, kun ved oprettelse, film+TV. Ren frontend + i18n `scan.removeFromWishlistConfirm` (da+en).

## [0.121.0 build 0164] — 2026-08-13 — feature: genre som sorterings-valg (FEATURES.md #146)

Jan: *"i sorte liste er der ikke kategori genrer som valg"*. "Genrer" er nu et valg i sorterings-dropdownen på både Film- og TV-siden. `genres` tilføjet til `SORT_FIELDS`-whitelisten i begge repos; MongoDB sorterer array-feltet på dets mindste element, så posterne grupperes efter deres alfabetisk første genre. Genbruger `field.genres`-nøglen. Tests: `test_sort_genre.py` (stigende/faldende).

## [0.120.0 build 0163] — 2026-08-13 — feature: ønske-godkendelse + navne-sammenfald-badge (FEATURES.md #144, #145)

To wishlist-ændringer (Jan, samme besked). **#144 — godkendelse:** en ikke-admins ønske oprettes nu som `pending` og skal godkendes af en admin; admin-oprettede ønsker er godkendt fra start (nyt `WishlistStatus`-felt på film+TV). Kun admin må godkende — håndhævet i backend (`update_*` afviser `wishlist_status` fra ikke-admins med 403). Frontend: afventende ønsker får en "⏳ Afventer"-badge, og admin får en "Godkend ønske"-knap på ønske-kortet. **#145 — navne-badge:** et ønske får en rød "⚠ I biblioteket"-badge hvis titlen falder sammen med en titel der allerede er i biblioteket — på tværs af både film og TV (normaliseret, læse-tids-beregning i `list_*`, `library_titles_normalized` i begge repos). Fanger navne-match selv når TMDb-id'et er et andet. Tests: `test_wishlist_approval.py` (6), `test_wishlist_name_match.py` (4).

## [0.119.0 build 0162] — 2026-08-13 — feature: poster-optimering — mindre billeder til små kort (FEATURES.md #143)

Jans ønske: *"kan du optimere de film/tv iconer vi bruger så hvis det er små icon så loader side hurtige"*. Backenden gemmer poster-URL'en i TMDb-`w500`, unødigt stor for et lille kort. Ny frontend-util `utils/posterUrl.js` omskriver TMDb-URL'ens størrelse (`w500`→`w185`/`w342`) til visnings-konteksten; null/manuelle URL'er røres ikke. Biblioteks-/TV-kort henter nu efter kortstørrelse (small→w185, medium→w342, large→w500); program-kort → w342; små thumbnails → w185; detalje-modalen beholder w500. Ren frontend (den gemte w500-URL er uændret, kun det hentede billede skaleres). Test: `posterUrl.test.js` (5). Frontend-suite 57 grøn.

## [0.118.1 build 0161] — 2026-08-13 — fix: antal-overskrift viste side-antal frem for total (BUGS.md #64)

Jan: *"i top af seksionen hvor mange film/tv der er, den viser hvor mange elementer der vise på side ... den skal vise total antal"*. Overskriften "X film"/"X serier" øverst på Film-/TV-siderne brugte `movies.length`/`shows.length` (kun den aktuelle sides poster) i stedet for `total` (hele antallet på tværs af alle sider). `Library.jsx`/`TvShows.jsx` bruger nu `total`. Ren frontend.

## [0.118.0 build 0160] — 2026-08-13 — feature: indkøbsliste-antal i top-baren (FEATURES.md #142)

Jans ønske: *"i top bar hvor der stå hvor mange film og serie der så også stå hvor mange film/tv der er på indkøbs listen"*. App-headeren viser nu et tredje tal — antal film+serier på indkøbslisten — ved siden af film- og serie-tællerne. Ren frontend: `GET /library/counts` returnerede allerede `wishlist` pr. ressource (feature #94), så headeren summerer `counts.movies.wishlist + counts.tv_shows.wishlist`. Ny `header-count--wishlist`-stil (stiplet kant) + i18n `counts.wishlist` (da+en).

## [0.117.0 build 0159] — 2026-08-13 — feature: besked når et ønske flyttes til biblioteket (FEATURES.md #141)

Jans ønske: *"hvis en film/tv bliver indkøbt og flyttet til film/tv database efterfølgende så skal den user som har tilføret den til indkøbs listen have besked"*. Når `update_movie`/`update_tv_show` flytter en post fra ønskelisten ind i biblioteket (`is_wishlist` true→false), sendes en besked (feature #100's system) til den der satte den på listen (`registered_by`): "Din ønskede film/serie er nu i biblioteket". Fælles helper `message_service.notify_wishlist_moved`. Springes over hvis flytteren selv er opretteren. Best-effort (try/except) så en notifikations-fejl ikke vælter flytningen. Dukker op via besked-banneret (auto-poll #135). Tests: `test_wishlist_move_notification.py` (3).

## [0.116.0 build 0158] — 2026-08-13 — feature: fuldt navn ved registrering + rolle i header (FEATURES.md #140)

Jans ønsker: obligatorisk fuldt navn ved bruger-oprettelse (så admin ser hvem der beder om adgang), og vis brugerens rolle i portalen. **(a)** Nyt `full_name` på `UserRegister`/`User`, gemt + returneret. Håndhæves som `required` i registrerings-formularen (`Login.jsx` + offentlig `/bio`-login), kun i opret-tilstand; backend-modellen holder feltet valgfrit (tomt→None) så den eksisterende API-kontrakt + testsuiten (113 register-kald) ikke brydes — det er et identitets-, ikke sikkerhedsfelt. Admin ser navnet i Indstillinger → Brugere ("brugernavn · Fuldt navn"). Eksisterende konti: None. **(b)** Den indloggede brugers rolle vises nu i headeren ("brugernavn · Admin/Standard/Guest"). `api.register` fik `fullName`-param; nye i18n `auth.fullName`/`auth.fullNamePlaceholder` (da+en). Tests: `test_full_name.py` (3).

## [0.115.0 build 0157] — 2026-08-13 — feature: delt 5000+-serie for "andre ejere" (FEATURES.md #139)

Jans regel: en post får serienummer fra en **delt 5000+-pulje** hvis ejeren (normaliseret: små bogstaver + mellemrum fjernet) ikke er blandt `{jan, lis, jan&lis, lis&jan}` **og** posten ikke er oprettet af en admin. Ellers de normale M#/T#/D#-serier. Jans valg: **ÉN fælles pulje** på tværs af film/TV/fysisk/digital. Implementering: ny `other_serial`-tæller i `digital_serial_repository` (start 5000, kun opad, race-sikker); `_uses_other_pool(owner, creator_is_admin)` i begge services; `create_movie`/`create_tv_show` tager nu `creator_is_admin` (default True → normal serie, så interne kaldere/Plex aldrig utilsigtet rammer 5000+; API sender den faktiske rolle). Gælder også wishlist→bibliotek-flyt og medietype-skift. De tre `free_serial_numbers` ekskluderer nu ≥ 5000, så "Ledige numre"/genbrug (#131) ikke viser falske huller. Ingen migration (kun nye poster; eksisterende numre urørt). Tests: `test_serial_other_pool.py` (5 — andre→5000, jan/lis→normal, admin→normal, delt pulje, gaps-eksklusion). Fuld suite grøn.

## [0.114.1 build 0156] — 2026-08-13 — fix: print gav kun én side på iOS (BUGS.md #63)

Jan: *"print se ud til kun at printe en side på ios"*. På iPhone/iPad (Safari) blev kun første side af print-listen udskrevet. Årsag: `html, body, #root` er låst til `height: 100%` (og `#root` er flex-column) for app-layoutet; iOS Safari tvinger derved hele dokumentet ind i én sidehøjde ved print. `@media print` i `index.css` frigiver nu rod-elementerne (`height: auto; min-height: 0; overflow: visible` + `#root { display: block }`), så listen paginerer over flere sider (kompletterer BUGS #49's flex→block-reset af `.app`/`.app-main`). Ren CSS, kun ved print. **Skal bekræftes på iPhone** (regel 16/18 — kan ikke verificeres fra desktop).

## [0.114.0 build 0155] — 2026-08-13 — feature: tag-UI — gæst obligatorisk auto-tag, andre dropdown (FEATURES.md #138)

Jans ønske: gæster skal altid have det obligatoriske "Tilføjet af"-tag (intet valg), og alle andre skal vælge tags fra en dropdown. I detalje-modalen (film + TV): **(#4)** for en gæst er tag-feltet erstattet af en note ("Tilføjes automatisk med tagget 'Tilføjet af {navn}'") — backenden tilføjer i forvejen ubetinget tagget (feature #18), så det er obligatorisk uanset UI. **(#5)** for alle andre er væggen af klikbare tag-chips erstattet af en dropdown ("Vælg et eksisterende tag…"), mens fri-tekst-feltet til nye tags er bevaret. Rører kun tag-*indtastningen* — filter-panelernes tag-chips er urørt. Ren frontend; nye i18n-nøgler `detail.guestTagNote`/`detail.pickTag` (da+en). Frontend-suite grøn.

## [0.113.0 build 0154] — 2026-08-13 — feature: konduktør ser + tilbagetrækker godkendte/for-reserverede sæder (FEATURES.md #137)

Jans ønske: *"admin af sæder skal kunne se hvad sæder som er godkendt sådan man kan tilbage træk godkendelse og det skal også gælde for global admin sæder"*. Konduktør-modulet (`ReservationAdmin`, Voldby BIO-fanen) fik en ny sektion "Godkendte / for-reserverede sæder" ud over den ventende kø. Den henter `GET /api/reservations?status=approved` — både godkendte gæste-reservationer og admin-hold har status `approved`, så begge vises — med sæde, film/global-beskrivelse og hvem, hver med en "Tilbagetræk"-knap (`DELETE` efter bekræftelse) der frigiver sædet. Dækker også globale hold. Ren frontend (backend understøttede allerede `?status=approved` + DELETE); ny `ApprovedRow` + i18n (da+en). Backend-test `test_list_approved_includes_holds_and_guest_reservations` låser antagelsen (21 reservations-tests grøn).

## [0.112.0 build 0153] — 2026-08-13 — feature: generel opdater-knap i portalen (FEATURES.md #136)

Jans ønske: *"vi skal brug en generalt refresh knap i portal"*. Ny "🔄 Opdatér"-knap i app-headeren (ved Log ud) der genindlæser siden (`window.location.reload()`), så man kan hente friske data på tværs af faner uden log ud/ind. Ren frontend, ny i18n-nøgle `app.refresh` (da+en).

## [0.111.0 build 0152] — 2026-08-13 — feature: beskeder dukker op automatisk uden genindlæsning (FEATURES.md #135)

Jans ønske: *"kan vi lave sådan at hvis besked bliver sendt til en user så kommer den automatisk op på skræm uden de skal logout og login igen"*. `MessageBanner` hentede før kun indbakken **én gang** ved mount, så en besked sendt til en allerede-indlogget bruger (fx en godkendt sæde-reservation, #134) først dukkede op ved næste sideindlæsning. Nu poller banneret `GET /api/messages/inbox` hvert 20. sekund (`POLL_INTERVAL_MS`, overstyrbart via `pollIntervalMs`-prop til test) og **tilføjer** nye beskeder til de viste — fjerner aldrig en åben besked ved poll, så den ikke blinker/genopstår. En `dismissedRef` (lokalt lukkede id'er) sikrer at en netop lukket besked ikke kommer tilbage hvis en poll når indbakken før `markMessageRead` er registreret (race-værn). Poll-fejl er tavse som før. Ren frontend; besked-API'et er uændret. Tests: `MessageBanner.test.jsx` +2 (besked dukker op ved næste poll; lukket besked kommer ikke igen). Frontend-suite 52 grøn, build OK.

## [0.110.1 build 0151] — 2026-08-13 — juster: seat-valg-knap som kompakt ikon (FEATURES.md #133)

Jans ønske: *"sæde icon er udfoldet nu skal det ikke være først når man trykker på den"*. Knappens billede var `Seat valg.png` — et screenshot af HELE sæde-modulet — så knappen så "udfoldet" ud. Skiftet til det rene biografstole-billede (`movie-seat.png`) vist som et lille rundt ikon (26px, beskåret cirkel) med "Vælg plads"-label i en kompakt vandret knap. Selve sædekortet folder først ud i modalen ved klik. Ren layout/asset-ændring i Cinema.jsx/Cinema.css.

## [0.110.0 build 0150] — 2026-08-13 — feature: besked til bruger ved godkendt sæde-reservation (FEATURES.md #134)

Jans ønske: *"lave en meddeles til user som har få godkendt sin sæd resevasion ved godkendelse fra admin"*. Genbruger feature #100's besked-system: `reservation_service.approve_reservation` sender efter godkendelsen en personlig besked til reservationens ejer via `message_service.send` (afsender = den godkendende admin, modtager = ejeren, slået op på normaliseret brugernavn). Beskeden — "Din pladsreservation er godkendt" — indeholder sæde-nummer + film + dato/tid og lander i ejerens indbakke (den eksisterende besked-banner i UI'et, ingen frontend-ændring). Notifikationen er en **best-effort sidekanal** i try/except, så en fejl aldrig vælter selve godkendelsen (regel 16). `approve_reservation` tager nu hele admin-dict'en (til afsender). Test: `test_approving_notifies_the_owner`. Backend-suite grøn.

## [0.109.1 build 0149] — 2026-08-13 — juster: seat-valg-knap under film-ikonet (FEATURES.md #133)

Jans ønske: *"sæt plads bestilling under film icon så film icon og tekst få plads i boks"*. Film-ikonet (poster) og seat-valg-knappen er nu samlet i en lodret media-kolonne (`.cinema-card-media`) i `ScreeningCard`, så knappen står **under** posteren i stedet for som en egen kolonne ved siden af. Titlen og teksten får dermed fuld bredde i program-boksen. Knappen fylder posterens bredde (capped 160px på mobil). Ren layout-ændring i Cinema.jsx/Cinema.css.

## [0.109.0 build 0148] — 2026-08-13 — feature: sæde-reservation til Voldby BIO — frontend (FEATURES.md #133)

Anden milepæl: hele brugerfladen oven på build 0147's backend.

- **`SeatSelectionModal`** (`components/SeatSelectionModal.jsx` + `.css`): sæde-vælgeren som modal, portet fra den godkendte sæde-vælger-artefakt (lærred → hjørnesofa med ~10°-vinklede fløje → to stolerækker → dør), men data-drevet fra `GET /api/screenings/{id}/seats`. Backend-tilstande `free`/`mine`/`pending`/`taken` → ledig (klikbar) / din plads (grøn, klik = annullér) / afventer (deaktiveret) / optaget (deaktiveret). Vælg ledige sæder → `Reservér valgte (n)` → `pending`. Genbruger appens design-tokens (tema-korrekt); grøn "din plads"-farve defineret lokalt for begge temaer.
- **Seat-valg-knap på `ScreeningCard`** (Cinema.jsx): `Seat valg.png` (Jans valg) ved siden af film-ikonet i program-boksen, åbner modalen for den fremvisning.
- **Konduktør-modul** (admin, Cinema.jsx): reservations-kø (`GET /api/reservations?status=pending`) med Godkend/Afvis pr. reservation, + hold-værktøj (vælg sæde 1–14 × global/film-specifik).
- **API-klient**: `getSeatMap`/`reserveSeats`/`listReservations`/`myReservations`/`approveReservation`/`cancelReservation`/`holdSeat`. **i18n**: nye `seat.*` + `cinema.*`-nøgler i da+en (katalog-parity-test grøn).
- Tests: `SeatSelectionModal.test.jsx` (3 — tilstand→klikbarhed, valg aktiverer Reservér + sender sæde-id, fravalg). Frontend-suite **50 passed**, build + lint grøn.
- **Regel 18**: rum-geometrien er godkendt via artefakten; modal-ramme/kort-knap/konduktør-panel i appen afventer visuelt tjek. Offentlig `/bio` har bevidst ikke knappen endnu (kræver login-gating).

## [0.109.0 build 0147] — 2026-08-13 — feature: sæde-reservation til Voldby BIO — backend/API (FEATURES.md #133)

Første milepæl af det fulde sæde-reservationssystem (Jans valg: fuldt system for registrerede gæster). **Backend/API + tests**; frontend (sæde-vælger-modal, knap på program-boksen, konduktør-modul) følger i næste commit under samme version.

- **Ny `seat_reservations`-collection** + lag: `models/reservation.py` (fast 14-sæde-katalog — sofa 1–4, række 2 sæde 5–9, række 3 sæde 10–14 — samt Reservation/SeatMap-modeller), `reservation_repository`, `reservation_service`, `api/reservations.py`.
- **Sædekort pr. fremvisning** (`GET /api/screenings/{id}/seats`): de 14 sæder med tilstand `free`/`mine`/`pending`/`taken` set fra kalderens perspektiv. Kræver login.
- **Gæst reserverer** (`POST /api/screenings/{id}/reservations`): et eller flere ledige sæder → `pending`. Tilladt for guests (som `POST /api/screening-requests`, #62/#72). Race-sikkert unikt index `(seat_id, screening_id)` (BUGS #44-mønster) + `SeatTakenError`→409 mod dobbelt-booking; hele reservationen fejler fremfor at efterlade en delvis (regel 16).
- **Konduktør-modul** (admin): `GET /api/reservations` (kø, `?status=`/`?screening_id=`), `POST /api/reservations/{id}/approve`, `DELETE /api/reservations/{id}` (ejer eller admin — håndhævet i backend), `POST /api/reservations/hold` (global eller film-specifik for-reservation).
- **Oprydning**: sletning af en fremvisning fjerner dens reservationer (`screening_service.delete_screening`).
- Nye fejl: `ReservationNotFoundError`/`InvalidSeatError`/`SeatTakenError` (404/400/409). ARCHITECTURE.md endpoint-tabel opdateret.
- Tests: `test_reservations.py` (19 — sædekort, gæst-reservation, dobbelt-booking + ingen delvis, idempotens, godkend/annullér-rettigheder, global vs. film-hold, sletning rydder). Fuld suite: **616 passed**.

## [0.108.1 build 0146] — 2026-08-12 — fix: fire systematiske fejl fra to-fase system-analyse (BUGS.md #59-#62)

Rettelse af de fire fund fra den dybe to-fase-gennemgang:

- **#59** `watched_at` gemtes som ISO-streng frem for Date (BUGS #33-klassen, latent): `mode="json"` fjernet fra `update_movie`/`update_tv_show`, + idempotent migration `_migrate_watched_at_to_date` (film+TV). Verificeret mod ægte MongoDB at feltet nu er en BSON Date.
- **#60** En gæst kunne hente `GET /api/tv-shows/deleted` (mens `movies/deleted` blokerer dem, BUGS #46): tilføjet `require_not_guest` + test.
- **#61** Tavs genindlæsning efter mutation i `Library.jsx`/`TvShows.jsx`: `refresh()` viser nu fejlen i et banner (`lib.refreshFailed`). Verificeret i browser.
- **#62** En serienr-kollision (fra #131's ikke-atomiske genbrug) blev fejlmeldt som stregkode-dublet: ny `_is_serial_collision` + retry af assign+insert i `create_movie`/`create_tv_show` + tests.

Verifikation: backend 597, frontend 47, build OK. Ingen regression fra `mode="json"`-fjernelsen (enums er `str`-enums og gemmes uændret).

Berørte filer: `backend/app/services/movie_service.py`, `backend/app/services/tv_show_service.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/app/api/tv_shows.py`, `backend/tests/{test_watched_status,test_label_migrations,test_serial_reuse,test_review_findings}.py`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/i18n/{da,en}.json`, `BUGS.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.108.0 build 0145] — 2026-08-12 — feature: format-oprydning (F-præfiks, D-480, VHS fjernet) (FEATURES.md #132)

Fysiske formater fik "F-"-præfiks: DVD→F-DVD, BD→F-BD, UHD→F-UHD. D-SD→D-480 (opløsnings-baseret). VHS fjernet som format. Enum-medlemsnavne uændrede.

- **Migration** ved opstart: de fem omdøbninger i `_FORMAT_LABEL_MIGRATIONS` (begge repos, kaskade). VHS-poster migreres til F-DVD (Jans valg). TV-migrationen fik også de fysiske renames.
- Plex-fallback/i18n-beskrivelse opdateret (D-SD→D-480). Frontend læser formaterne dynamisk.
- Tests: ny `test_v0_108_format_renames_and_vhs_removal`, `attribute-options` udvidet (+ `not in` på de gamle), ~270 test-format-værdier opdateret. Backend + frontend suiter grønne.

Berørte filer: `backend/app/models/movie.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, mange `backend/tests/*.py`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.107.0 build 0144] — 2026-08-12 — feature: genbrug af frigjorte serienumre (FEATURES.md #131)

Ny til/fra "Genbrug frigjorte numre" i serienummer-sektionen (Indstillinger → Bibliotek), fælles for alle tre serier (M#/T#/D#). Slået til får en ny post det laveste frigjorte nummer i sin serie før tælleren går videre; slået fra = hidtidig adfærd (tæller kun opad). Et "frigjort" nummer = et hul i det brugte interval, opstået ved sletning eller ønskeliste-flyt (selv-korrigerende — ingen separat bogføring). Sektionen viser desuden de ledige numre pr. serie.

- Backend: hvert `next_serial_number` (movie/tv/digital) genbruger laveste hul når `reuse_freed` er til, ellers `_next_from_counter` (uændret race-sikker tæller; digital backfill bruger tælleren direkte). Flaget bor i `digital_serial_repository` (ingen cirkulær import). `GET/PATCH /api/settings/serial-number` fik `reuse_freed` + read-only `free_numbers`.
- **Afgrænsning**: kun huller mellem laveste og højeste brugte nummer genbruges (så et flyttet start-tal ikke udpeger lave numre). Race: laveste-hul er ikke atomisk som tælleren — acceptabelt for et enkelt-admin hjemme-bibliotek (unikt index er backstop).
- Tests: `test_serial_reuse.py` (6). Backend 592, frontend 47. Live-verificeret (regel 18): slettet M#2 genbrugt af næste post.

Berørte filer: `backend/app/models/settings.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/app/repositories/digital_serial_repository.py`, `backend/app/services/movie_service.py`, `backend/tests/test_serial_reuse.py`, `backend/tests/test_settings.py`, `frontend/src/pages/Settings.jsx`, `frontend/src/pages/Settings.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.106.0 build 0143] — 2026-08-12 — feature: biograf-historik under Indstillinger (FEATURES.md #130)

Ny "Biograf"-fane i Indstillinger med en historik over afholdte Voldby BIO-fremvisninger (nyeste øverst: titel + evt. note + dato/tid). Backend: `GET /api/screenings?past=true` — filtrerer `scheduled_at < now` og sorterer faldende (så 500-cap'en beholder de nyeste). Ren læse-udvidelse; planlægning sker fortsat på Voldby BIO-fanen. Fanen er synlig for alle ikke-gæster. Test: `test_list_screenings_past_filter_returns_history_newest_first`. Live-verificeret (regel 18).

Berørte filer: `backend/app/api/screenings.py`, `backend/app/services/screening_service.py`, `backend/app/repositories/screening_repository.py`, `backend/tests/test_screenings.py`, `frontend/src/api/client.js`, `frontend/src/pages/Settings.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `ARCHITECTURE.md`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.105.0 build 0142] — 2026-08-12 — feature: omdøbte/nye format- og lyd-type-labels (FEATURES.md #129)

Opløsnings-baserede labels. Format: "D-HD"→"D-1080", "D-UHD"→"D-4K", ny "D-720". Lyd: ny "DTS5.1", "DTS-HD-M"→"DTS-HD5.1", "DTS-HD-MA-7.1"→"DTS-HD7.1". Enum-medlemsnavne uændrede (kode der refererer dem er urørt).

- **Migration** af eksisterende data ved opstart: format-renames i `_FORMAT_LABEL_MIGRATIONS` (begge repos, kaskade via sekventielle `update_many`); audio-renames i movie-repoets `_AUDIO_TYPE_LABEL_MIGRATIONS` (mellemliggende labels mapper direkte til slutværdien); TV-serier fik deres **egen nye** `_migrate_audio_type_labels` (jf. regel 16).
- **Plex**-import router nu 720p → D-720 (ikke sammen med 1080 som HD); i18n-beskrivelse + fallback-tekst opdateret.
- Frontend læser format/lyd dynamisk fra `attribute-options` — nye/omdøbte labels dukker automatisk op.
- Tests: migrations-tests udvidet (film-format-kaskade, film+TV-audio, TV-format→D-4K), `format_for_resolution("720")→D-720`, alle Plex-format-assertions + `attribute-options` opdateret. Backend + frontend suiter grønne.

Berørte filer: `backend/app/models/movie.py`, `backend/app/models/plex.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/app/services/plex_service.py`, `backend/tests/test_label_migrations.py`, `backend/tests/test_plex.py`, `backend/tests/test_movies.py`, `backend/tests/test_library_counts.py`, `backend/tests/test_serial_number_rules.py`, `backend/tests/test_serial_sort_and_search.py`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.104.0 build 0141] — 2026-08-12 — feature: blokerende dublet-bekræftelse før en kopi mere tilføjes (FEATURES.md #128)

Supplerer #38's passive dublet-banner med en aktiv OK/Annuller-dialog: når du opretter en titel der allerede findes (på ønskelisten eller i biblioteket), popper `window.confirm("Denne findes allerede {where}. Vil du tilføje en kopi mere?")` før oprettelsen. Annuller afbryder (ingen kopi); OK opretter kopien. Tilføjet i `MovieDetailModal.save()` og `TvShowDetailModal.save()` (kun kladde-oprettelse), så det dækker både film og TV. Dublet-tjekket er `tmdb_id`-baseret (som #38). Ny i18n-nøgle `scan.duplicateConfirm`. Live-verificeret ende-til-ende (Playwright mod ægte TMDb): Annuller holder antallet på 1, OK gør det til 2.

Berørte filer: `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.103.0 build 0140] — 2026-08-12 — feature: sortering på bestillingsstatus (FEATURES.md #127)

`order_status` (ønskeliste-feltet fra #114) er nu et sorterbart felt. Backend: tilføjet til `SORT_FIELDS` + index i både `movie_repository` og `tv_show_repository`. Frontend: nyt "Bestillingsstatus"-punkt i sorterings-dropdownen på både Film-/ønske- og TV-siderne (genbruger `field.orderStatus`). Ikke-bestilt (None) sorteres først stigende. Test: `test_sorting_by_order_status_works_end_to_end` (asc+desc).

Berørte filer: `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/tests/test_serial_sort_and_search.py`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.102.1 build 0139] — 2026-08-12 — juster: længere knap-tekster på tilføj-knapperne (Jans ønske)

Tydeligere tekst på de to store tilføj-knapper (feature #126): "Scan cover" → "Tilføre film med scan cover", "Søg titel" → "Tilføre film på title". Kun i18n-værdier (`lib.addScan`/`lib.addSearchTitle`) i begge kataloger. Knapperne deles af Film-, TV- og ønskeliste-siderne, så teksten er ens alle tre steder. Live-verificeret i mobil-viewport (regel 18): den længere tekst ombryder pænt inde i knapperne (begge lige høje, ingen vandret overflow).

Berørte filer: `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.102.0 build 0138] — 2026-08-12 — feature: to store scan/søg-titel-knapper også på Film- og TV-siderne (FEATURES.md #126)

Breder #124's to-knap-mønster ud fra ønskelisten til Film-biblioteket og TV-serie-siden: øverst "📷 Scan cover" og "🔍 Søg titel", der hver åbner kun den relevante del af `MovieLookupForm`, så den manuelle titel-søgning ikke forveksles med bibliotekets generelle søgning.

- På Film/TV **beholdes den generelle søgning fremtrædende** (fuld række, Jans valg), i modsætning til ønskelisten hvor den er demoted.
- Det gamle `showAddPanel`-toggle er fjernet fra `Library.jsx` og `TvShows.jsx`; begge bruger nu `addMode` i alle fire mode-kombinationer (Film, TV, film-ønske, TV-ønske). Delte toolbar-dele (søgefelt + sortér/filter/felter) udtrukket også i `TvShows.jsx`.
- i18n omdøbt: `lib.wishScan`/`lib.wishSearchTitle` → generiske `lib.addScan`/`lib.addSearchTitle`. CSS: `.wishlist-add-actions`/`.wishlist-action` → `.add-actions`/`.add-action`.
- Ren frontend. Tests: frontend-suite grøn (47). Live-verificeret (regel 18): begge sider viser de to knapper med prominent søgning; hver knap åbner kun sit eget panel.

Berørte filer: `frontend/src/pages/Library.jsx`, `frontend/src/pages/Library.css`, `frontend/src/pages/TvShows.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.101.0 build 0137] — 2026-08-12 — feature: besøgs-statistik på Statistik-siden (FEATURES.md #125)

Ny "Besøg"-sektion på Statistik-siden: hvem der besøger, hvad de besøger, antal om dagen og total m.m. Jans scope: alle besøg (offentlig /bio + indloggede), sider + åbnede titler, og med brugernavn (anonyme = "gæst").

- **Nyt lag** (ARCHITECTURE.md-endpoints tilføjet): `visits`-collection, `models/analytics.py` (`VisitCreate`/`VisitStats`), `visit_repository`, `analytics_service` (aggregering i Python — mongomock-sikkert, ingen `$dateToString`), `api/analytics.py`.
- **`POST /api/analytics/visit`** er offentligt (så /bio kan poste uden login) via ny `deps.get_optional_user` (bruger hvis gyldig cookie, ellers None — aldrig 401). Brugernavnet sættes server-side, aldrig fra payloaden. **`GET /api/analytics/summary`** kræver ikke-gæst (som `/api/movies/stats`).
- **Frontend-tracking** (alt fire-and-forget): fane-skift i `App.jsx`, `CinemaPublic`-mount (offentlig /bio = gæst), og åbning af en gemt film-/TV-detalje-modal (titel-besøg).
- **Statistik-siden**: summary-fliser (total, i dag, unikke brugere, gæste-besøg) + `BarList` (genbrugt) for pr. dag (sidste 14, kontinuerlig serie), mest besøgte sider (oversat til nav-etiketter, /bio adskilt), mest åbnede titler, mest aktive brugere ("gæst" for anonyme).
- Besøg indgår bevidst ikke i backup/reset (ren analytik).
- **Tests**: `test_analytics.py` (7 — record side/titel, indlogget/gæst, per-dag-serie, gating), `Statistics.test.jsx` (4 — dato-format + side-etikette-fallback). Backend 583, frontend 47.
- **Verifikation**: begge suiter + lint/build grønne. Live-verificeret i browseren (regel 18): Besøg-sektionen viser fliser, pr.-dag-serie, sider, titler og brugere (inkl. "Gæst").

Berørte filer: `backend/app/models/analytics.py` (ny), `backend/app/repositories/visit_repository.py` (ny), `backend/app/services/analytics_service.py` (ny), `backend/app/api/analytics.py` (ny), `backend/app/api/deps.py`, `backend/app/main.py`, `backend/tests/conftest.py`, `backend/tests/test_analytics.py` (ny), `frontend/src/api/client.js`, `frontend/src/App.jsx`, `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/pages/Statistics.jsx`, `frontend/src/pages/Statistics.css`, `frontend/src/pages/Statistics.test.jsx` (ny), `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `ARCHITECTURE.md`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.100.0 build 0136] — 2026-08-12 — feature: mobilvenlig indkøbsønsker-side med to store handlingsknapper (FEATURES.md #124)

Indkøbsønsker-fanen havde tre lignende tekstfelter — bibliotekets generelle filtersøgning (altid synlig) og, gemt bag "+ Tilføj", scan-panelets stregkode-felt + titel-søgning — så den generelle søgning blev forvekslet med "søg manuelt". På ønskelisten tilføjer man mest, så tilføj-flowet er nu det fremtrædende (Jans valg: to store handlingsknapper).

- **Kun `wishlist`-varianten** (biblioteket urørt): øverst to store knapper "📷 Scan cover" og "🔍 Søg titel", der hver åbner *kun* den relevante del. Den generelle søgning er flyttet til en lille, demoted sekundær-række med sit eget "Filtrér dine ønsker"-placeholder, sammen med Sortér/Filter/Felter.
- **`MovieLookupForm`** fik en `mode`-prop (`scan`/`manual`/`both`, default `both` = uændret bibliotek): i single-mode vises kun det ene kort, med et "Søg på titel i stedet"/"Scan cover i stedet"-skift, så scan→titel-fallbacken (forudfyldt gæt) bevares.
- Ren frontend. Delte toolbar-dele (søgefelt + sortér/filter/felter-knapper) udtrukket i Library.jsx, så biblioteks- og ønske-layoutet ikke duplikerer dem.
- **Tests**: `MovieLookupForm.test.jsx` (4 nye — mode viser kun det rette kort, fallback-skift). Frontend-suite grøn (43).
- **Verifikation**: lint/build grønne. Live-verificeret i mobil-viewport (390×844, regel 18): to store knapper + demoted "Filtrér dine ønsker", "Søg titel" viser kun titel-søgningen, "Scan cover" viser kun scanneren.

Berørte filer: `frontend/src/components/MovieLookupForm.jsx`, `frontend/src/components/MovieLookupForm.test.jsx` (ny), `frontend/src/pages/Library.jsx`, `frontend/src/pages/Library.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.99.0 build 0135] — 2026-08-11 — feature: undertekster som liste (Eng/DK + Andet-fritekst) med datamigration (FEATURES.md #123)

Underteksterne gik fra ét frit tekstfelt (#109) til en liste: faste afkrydsnings-valg **Eng**/**DK** plus et **"Andet"**-fritekst-felt til alt andet (fx "Fastbrændt DA", "Norsk"). Jans valg: flere valg (afkrydsning), "Andet" åbner fritekst, og eksisterende data konverteres.

- **Datamodel**: `subtitles` `str | None` → `list[str]` i Movie og TvShow (Create/Update/read). Ny delt `models/movie.py`-helper: `SUBTITLE_STANDARD_OPTIONS`, `subtitles_from_free_text` (migrerings-parsing), `coerce_subtitles` (læse-side normalisering).
- **Migration** (skema-ændring): `_migrate_subtitles_to_list` i movie_repository + tv_show_repository, kaldt fra `ensure_indexes` — konverterer eksisterende streng-værdier til liste-form (idempotent, dokument-for-dokument). Kører automatisk ved backend-opstart, som de øvrige label-migrationer.
- **API**: begge `attribute-options`-endpoints eksponerer nu `subtitles: ["Eng", "DK"]`.
- **Frontend**: ny genbrugelig `SubtitlesPicker` (chips + "Andet"-fritekst), brugt i film- og TV-detaljemodalerne (dækker både tilføj og redigér).
- **Tests**: backend create/update/ryd + migration (film+TV) + attribute-options; frontend `SubtitlesPicker.test.jsx` (6 nye).
- **Verifikation**: begge testsuiter grønne (backend 576, frontend 39). Live-verificeret i browseren (regel 18): Eng+DK+Andet-chips aktive med "Norsk" i fritekst-feltet, konsistent med lyd-type-rækken.

Berørte filer: `backend/app/models/movie.py`, `backend/app/models/tv_show.py`, `backend/app/services/movie_service.py`, `backend/app/services/tv_show_service.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/app/api/movies.py`, `backend/app/api/tv_shows.py`, `backend/tests/test_movies.py`, `backend/tests/test_tv_shows.py`, `frontend/src/components/SubtitlesPicker.jsx` (ny), `frontend/src/components/SubtitlesPicker.test.jsx` (ny), `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/components/MovieLookupForm.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.98.0 build 0134] — 2026-08-11 — feature: nye lyd-typer DTS:X og DTS-HD-MA-7.1 (FEATURES.md #122)

To nye værdier i `AudioType`-enummet (`backend/app/models/movie.py`): `DTS:X` og `DTS-HD-MA-7.1`, placeret ved de øvrige DTS-varianter. Enummet deles af film og TV-serier, og frontend henter lyd-typerne dynamisk fra `attribute-options`, så begge dukker automatisk op i afkrydsnings-listerne på tilføj/rediger uden frontend-ændring. Ingen datamigration. `test_attribute_options_endpoint` udvidet til at dække begge nye værdier.

Berørte filer: `backend/app/models/movie.py`, `backend/tests/test_movies.py`, `FEATURES.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.97.1 build 0133] — 2026-08-11 — fix: "+ Tilføj" på samlings-del fra ønskelisten virker nu (BUGS.md #58)

`CollectionSection.addPart` i `Library.jsx` sendte ikke `is_wishlist` med til `createMovie`, så en tilføjelse fra ønskelisten blev afvist af backend-validatoren (`format`/`media_type` kræves for biblioteksposter) og fejlen blev slugt tavst — knappen så ud til ikke at gøre noget. Nu følger tilføjelsen forælderen: fra ønskelisten tilføjes søsterfilmen til ønskelisten (knap: "+ Ønskeliste"); fra en ejet film henvises til det fulde tilføj-flow, da format/medietype ikke kan vælges i samlingslisten. Fejl vises nu i et banner i stedet for at sluges (CLAUDE.md regel 16).

Berørte filer: `frontend/src/pages/Library.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `BUGS.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `version.json`.

## [0.97.0 build 0132] — 2026-08-11 — feature: mørkt tema som default + baggrund tilbage til blødt udtonet top-motiv (FEATURES.md #121, #119)

To ting fra Jans feedback (2026-08-11).

**#121 — mørkt tema som default** (*"mørk team skal være default"*). #110 gjorde tema personligt med "usat = følg systemets `prefers-color-scheme`". Nu er default mørkt: `App.jsx` sætter `data-theme="dark"` når intet er valgt (usat bruger, plus de ikke-autentificerede /bio- og login-sider) i stedet for at fjerne attributten. Et eksplicit personligt valg (Lyst/Mørkt under Indstillinger → Konto) vinder stadig, og tema-vælgeren markerer nu "Mørkt" som aktiv når intet er valgt. Selve CSS-variabelsystemet er uændret.

**#119 — baggrunden tilbage til top-motiv** (*"kun i toppen men tonet blødt ud ned mod bund ... ikke fliser"*). v0.96.1's fuldside-fliser er droppet igen. `.cinema-public-backdrop` er nu ét billede (`no-repeat`) i toppen (760px, 560px på mobil) med en lang, blød `mask-image`-udtoning (opaque til 12% → gennemsigtig ved bunden), så collagen glider umærkeligt over i sidens baggrund. Ingen dæmpning nødvendig: den hvide hero-tekst ligger enten på det uigennemsigtige skilt eller i den udtonede zone over den nu mørke baggrund. Grynetheden fra `cover`-opskaleringen er langt mindre synlig nu, hvor mørkt tema er default og collagens mørke frames dominerer.

Visuelt verificeret i browseren (CLAUDE.md regel 18): den offentlige side i mørkt (default) og lyst tema, desktop + mobil — collagen toner blødt ud i toppen, teksten er læsbar, ingen fliser.

Berørte filer: `frontend/src/App.jsx`, `frontend/src/pages/Settings.jsx`, `frontend/src/pages/CinemaPublic.css`, `FEATURES.md`, `version.json`.

## [0.96.1 build 0131] — 2026-08-11 — juster: film-collage-baggrunden dækker nu hele siden og er ikke længere grynet (FEATURES.md #119)

Opfølgning på #119. Jans feedback på første udgave (v0.96.0): *"baggrunds billede er for stor, den bliver for grynet og den er kun synlig i den øverste del af siden"*.

Årsag: `baggrund2.png` er kun 712px bred, så `background-size: cover` opskalerede den kraftigt på brede skærme (→ gryn), og backdrop'en lå kun i toppen (620px høj + udtoning).

Rettet: `.cinema-public-backdrop` er nu `inset: 0` (hele siden) med `background-repeat: repeat` og `background-size: 460px auto` (340px på mobil). Billedet vises altså i naturlig/nedskaleret størrelse og gentages som fliser — nedskalering giver skarpe fliser uden gryn, og de dækker hele siden i stedet for kun toppen. `filter`/`mask`-udtoningen er fjernet; i stedet holder `opacity: 0.16` det som et dæmpet motiv bag indholdet, så tekst og kort forbliver læsbare i begge temaer.

Visuelt verificeret i browseren (CLAUDE.md regel 18) desktop lyst/mørkt + mobil — collagen er nu synlig hele vejen ned, skarp, og alt er læsbart.

Berørte filer: `frontend/src/pages/CinemaPublic.css`, `frontend/src/pages/CinemaPublic.jsx` (kommentar), `FEATURES.md`, `version.json`.

## [0.96.0 build 0130] — 2026-08-11 — feature: film-collage som top-motiv på den offentlige BIO-side (FEATURES.md #119)

Jan ville have et billede som baggrund på den offentlige Voldby BIO-side, i sidens nuværende (varme) farver. Et første forsøg med en selv-tegnet SVG-film-stribe blev droppet (*"drop den opgave vi bruger et andet billede"*); i stedet leverede Jan `baggrund2.png` — en RGBA-collage af film-frames i varme orange/sorte/creme-toner.

`.cinema-public-backdrop` skifter billede fra #105's slørede skilt-JPG til `baggrund2.png` (`background-size: cover`, `center top`). `filter: brightness(0.5) saturate(1.05)` dæmper collagen, så hero'ens hvide tekst forbliver læsbar oven på dens lyse partier i begge temaer, og den eksisterende `mask-image`-udtoning nedad (til 45%) beholdes, så motivet kun præger toppen bag hero'en og toner blødt ud i indholdet.

Bevidst valg: IKKE et fuldside-billede bag alt indhold. Et billede bag den gennemsigtige `main` ville give mørk tekst på et mørkt billede og ødelægge læsbarheden; hero-top-udtoningen (samme struktur som #105) giver et stemningsfuldt motiv uden at røre læsbarheden længere nede. Farverne matcher den nuværende palette (Jans ønske).

Visuelt verificeret i browseren (CLAUDE.md regel 18) desktop lyst/mørkt + mobil — collagen står bag hero'en, toner ud i indholdet, og al tekst er læsbar.

Berørte filer: `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/pages/CinemaPublic.css`, `frontend/public/cinema/baggrund2.png` (ny), `FEATURES.md`, `version.json`.

## [0.95.0 build 0129] — 2026-08-11 — feature: dato/tid-badge i hjørnet på offentlige visnings-kort (FEATURES.md #120)

Jan: *"for public film side kan du ikke flytte tidspunkt og dato badge op til højre hjørne på visnings kort for de film som stå til display"*. Følger #118's brede kort.

Ny modifier-klasse `.cinema-card--public` på `PublicScreeningCard`, så ændringen kun rammer den offentlige side: kortet bliver `position: relative`, og dato/tid-badgen (`.cinema-card-time`) placeres absolut i øverste højre hjørne (`top: 10px; right: 10px`). `.cinema-card-body` får `padding-top: 22px`, så titlen — også en lang, ombrudt titel — starter under badgen uden at kollidere i desktop-layoutet. Den indloggede `.cinema-card` (Cinema.jsx) er bevidst urørt: den er dag-grupperet og har admin-værktøjer, der forventer badgen i tekst-flowet.

Visuelt verificeret i browseren (CLAUDE.md regel 18) desktop + mobil — badgen står i hjørnet, og en lang titel ombryder pænt nedenunder uden overlap.

Berørte filer: `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/pages/CinemaPublic.css`, `FEATURES.md`, `version.json`.

## [0.94.1 build 0128] — 2026-08-11 — fix: login-/opret-dialog som centreret modal på offentlig side (BUGS.md #57, opfølgning)

Opfølgning på #57. Den første rettelse (v0.93.1 — `.cinema-public-hero` løftet til `z-index: 2`) hit-testede grønt i harness, men løste det **ikke** i Jans faktiske brug: *"det er stedigværk det samme"*. Panelet var stadig absolut placeret op i hero-hjørnet og afhang af hero'ens højde.

Jans forslag: gør boksen til en centreret dialog midt i skærmen. Login-/opret-panelet er nu et **modal-overlay** — `.cinema-public-login-overlay` med `position: fixed; inset: 0`, flex-centreret indhold og `z-index: 100` (samme mønster som appens egen `.modal-backdrop` i Library.css), renderet sidst i `.cinema-public-page` frem for absolut inde i hero'en. Et `position: fixed`-element centreres mod viewporten uanset hero-højde og orientering og klippes ikke af containerens overflow, så hele klassen af overflow-/stacking-fejl forsvinder. Klik på det mørke backdrop (eller Annullér) lukker dialogen; klik inde i den lukker ikke (`stopPropagation`).

Oprydning: hero'ens `z-index` rullet tilbage fra 2 til 1 (nu overflødigt), og den forældede absolut-placerings-CSS for `.cinema-public-login-panel` + dens mobil-override (`@media (max-width: 560px)`) fjernet. `.cinema-public-login-panel` er nu et alm. centreret kort (`width: 320px; max-width: 100%; max-height: 90vh; overflow-y: auto`).

Verificeret med hit-test (`document.elementFromPoint`) mod den rigtige CSS: panelets centrum = viewportens centrum i både portræt (492×752) og landskab (820×328), og "Opret bruger" er `TAPPABLE` begge steder. Set i browseren (CLAUDE.md regel 18) — dialogen står centreret med dæmpet baggrund bag.

Berørte filer: `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/pages/CinemaPublic.css`, `BUGS.md`, `version.json`.

## [0.94.0 build 0127] — 2026-08-11 — feature: rigere visnings-kort på den offentlige BIO-side (FEATURES.md #118)

Jan: *"på public side gør icon fremvisnings siderne mere interessante eventuelt med samme info som hvis man er logget ind hvor imdb og trailer info er med også"*. Forelagt tre former (klik→detalje / rigere kort inline / brede kort som indlogget) valgte Jan de brede kort som den indloggede Voldby BIO-fane.

Rent frontend — dataene var der allerede: `Screening`-modellen og det offentlige (ikke-autentificerede) `GET /api/screenings` returnerede allerede `overview`/`genres`/`trailer_url`/`imdb_url`, beriget ved læsning fra den refererede film/serie (feature #63). Den offentlige `PublicScreeningCard` viste dem bare ikke — kun dato, poster, titel og genrer.

Kortet er omskrevet fra det kompakte `bio-poster-card` til det brede `cinema-card`-layout (poster + tekst side om side: tid, titel+år, genrer, plot, evt. note, trailer- og IMDb-links), genbrugt fra `Cinema.css` (nu importeret i `CinemaPublic.jsx`) frem for duplikeret styling — så den offentlige og indloggede visning aldrig kan drive fra hinanden. Den offentlige udgave har ingen admin-værktøjer, og tids-badgen viser dato+tid, da den offentlige liste er flad (ingen dag-gruppering — bevidst valg fra #64 v2). De nu ubrugte `.bio-poster-*`-regler er fjernet fra `CinemaPublic.css`. Den indloggede `ScreeningCard` er urørt.

Visuelt verificeret i browseren (CLAUDE.md regel 18) i både lyst og mørkt tema, desktop og mobil — de brede kort viser plot + trailer/IMDb-links, og på mobil stakkes de lodret med posteren capped (målt `posterW=160px`, `cardDir=column`) via den genbrugte, uændrede `.cinema-card`-CSS.

Berørte filer: `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/pages/CinemaPublic.css`, `FEATURES.md`, `version.json`.

## [0.93.1 build 0126] — 2026-08-11 — fix: "Opret bruger" kunne ikke trykkes i portræt på den offentlige side (BUGS.md #57)

Jan: på iPhone i portræt kunne man ikke trykke på "Opret bruger" på den offentlige Voldby BIO-side — kun i landskab.

Årsag: login-panelet er absolut placeret inde i `.cinema-public-hero` (`z-index: 1`), hvis højde følger skiltbilledets faste `aspect-ratio: 2.5/1`. I portræt er skærmen smal → skiltet lavt → hero'en kort, så det høje login-panel flyder ud *under* hero'ens boks. `.cinema-public-main` er næste søskende med samme `z-index: 1` men senere i DOM, og malede derfor oven på panelets nederste knapper i overlaps-området og opsnappede trykkene. I landskab er skiltet højt nok til at hele panelet bliver inde i hero'en, så knapperne virkede.

Fix: `.cinema-public-hero` løftet til `z-index: 2` (over main), så hele hero'ens stacking-kontekst inkl. panelet males foran main og modtager trykkene. Ren stacking-rettelse — hero og main overlapper kun via panelet, så der er ingen anden visuel ændring.

Verificeret med et hit-test (`document.elementFromPoint` midt på "Opret bruger"-knappen) mod den rigtige CSS: portræt gik fra `hit=[cinema-public-main] BLOCKED` → `hit=[#opret-link] TAPPABLE`, landskab forblev TAPPABLE (CLAUDE.md regel 18 — layout set/afprøvet, ikke kun bygget).

Berørte filer: `frontend/src/pages/CinemaPublic.css`, `BUGS.md`, `version.json`.

## [0.93.0 build 0125] — 2026-08-11 — feature: omdøb "Ønsker" → "Indkøbsønsker" i UI'et (FEATURES.md #117)

Jan: *"rename 'ønske' til 'indkøbs ønsker'"*. Ren tekst-ændring i de to i18n-kataloger (`da.json`/`en.json`) — ingen kode-, endpoint- eller datamodel-ændring (feltet hedder fortsat `is_wishlist` internt).

Dansk: feature-navnet er nu **"Indkøbsønsker"** (nav-fane + sidetitel), enkelt-post "indkøbsønske", og "på indkøbslisten" hvor teksten refererer til listen som sted (fx franchise-badge og dublet-advarsel). Engelsk følger med som **"Shopping list"**. Kun selve indkøbsliste-teksterne er rørt — `request.*`/`cinema.*` ("Send ønske", "✓ Ønsket til Voldby BIO", "Ønsket tidspunkt", "Ønsket af") handler om Voldby BIO-visningsanmodninger, ikke indkøbslisten, og er bevidst uændrede.

Nav'ens `.tabs` bruger `white-space: nowrap` + `overflow-x: auto` på mobil, så den længere label scroller vandret frem for at ombryde (rule 18-relevant, men allerede afværget i eksisterende CSS; længden er på niveau med "Indstillinger"/"TV-serier"). i18n-katalogtesten (feature #103) bekræfter at begge kataloger stadig har samme nøgler og pladsholdere efter renamet.

Berørte filer: `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `version.json`.

## [0.92.0 build 0124] — 2026-08-11 — feature: gæster kan oprette ønsker (FEATURES.md #116)

Jan: *"lave det muligt for guest user at kunne oprette ønsker også men ikke noget med status på order"*. Feature #72 gjorde gæste-rollen fuldstændig læse-kun; denne feature åbner **kun** oprettelse af ønskeliste-poster for dem — de kan stadig ikke oprette bibliotekspost, redigere/flytte/slette eksisterende poster eller sætte bestillingsstatus.

Backend: `POST /api/movies` og `POST /api/tv-shows` skifter fra `require_not_guest` til `get_current_user` + en ny fælles `enforce_guest_wishlist_only(current_user, payload)` i `deps.py`. For en gæst kræver den `is_wishlist=True` (ellers 403 "Gæster kan kun oprette ønsker") og **tvinger `order_status=None`** uanset hvad payloaden indeholder — så bestillingsstatus aldrig kan sættes af en gæst, håndhævet i backend og ikke kun i UI (CLAUDE.md regel 16's adgangskontrol-punkt). Alle øvrige skrive-endpoints (update/delete, sæson-/episode-toggles) beholder `require_not_guest` uændret.

Frontend: Ønsker-fanen er fjernet fra `GUEST_RESTRICTED_TABS` og vises nu i nav'en for gæster (Print/Statistik forbliver spærret). "+ Tilføj ønske"-knappen og MovieLookupForm-panelet vises for gæster, men **kun** i ønske-fanen (`!isGuest || wishlist`), aldrig i selve biblioteket. Bestillingsstatus-feltet (rediger-dropdown, læse-linje og kort-badge) er skjult for gæster, så de aldrig møder order-status-begrebet. Film og TV ens.

Ændringen er en betinget synligheds-/tilladelses-ændring (ikke en placerings-ændring), så den er verificeret via testsuiten frem for skærmbillede: nye `test_guest_role.py`-tests dækker at en gæst kan oprette film-/TV-ønske, ikke kan oprette bibliotekspost, og at order_status tvinges til None selv når den sendes med.

Berørte filer: `backend/app/api/deps.py`, `backend/app/api/movies.py`, `backend/app/api/tv_shows.py`, `backend/tests/test_guest_role.py`, `frontend/src/App.jsx`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `ARCHITECTURE.md`, `FEATURES.md`, `version.json`.

## [0.91.0 build 0123] — 2026-08-11 — feature: feature-liste synlig i portalen (FEATURES.md #115)

Jan: *"feature listen kan du lave et url til den på github under settings på portal sådan folk kan se hvad bliver lavet på film portal"*. Oprindeligt ønske var et GitHub-link, men repo'et er **privat** — et link ville ramme en login-væg for alle uden repo-adgang, så det ville ikke opfylde formålet. Forelagt tre muligheder (vis listen inde i appen / GitHub-link alligevel / gør repo'et offentligt) valgte Jan at vise listen inde i portalen.

Ny `GET /api/system/feature-list` (kræver login, ikke admin — enhver rolle, inkl. guest) der server-side parser **kun** oversigts-tabellen i `FEATURES.md` (nummer/navn/status/version) og returnerer den nyeste-først. Detalje-tabellen med de interne implementerings-noter og Jans egne citater parses bevidst ikke — kun de fire offentlige kolonner eksponeres. Ny `feature_list_service.py` finder filen via samme `parents[3]`-mønster som `core/version_info.py` (repo-roden) og degraderer til en tom liste hvis filen mangler i et afvigende deploy-layout (CLAUDE.md regel 16), i stedet for at kaste en 500. Klipper `FEATURES.md` ved "## Detaljer" før parsning, så detalje-tabellens rækker (samme markdown-format) ikke tælles med — verificeret af en test der kræver unikke feature-numre. Holder FEATURES.md som single source of truth i stedet for en dublet-liste at vedligeholde.

Frontend: ny "Nyheder"-fane på Indstillinger-siden (synlig for alle roller, i modsætning til de admin-gatede faner), der henter listen og viser hver feature nyeste-først med en status-badge (Færdig=grøn, I gang=rav, Planlagt=dæmpet, Droppet=overstreget). En ukendt status vises råt frem for at forsvinde. Badge-farverne er tema-tilpassede (egne `data-theme`/`prefers-color-scheme`-regler i `Settings.css`).

Visuelt verificeret i browseren (CLAUDE.md regel 18) i både lyst og mørkt tema — fanen, rækkerne og alle fire status-badges læser korrekt i begge temaer.

Berørte filer: `backend/app/models/feature.py` (ny), `backend/app/services/feature_list_service.py` (ny), `backend/app/api/system.py`, `backend/tests/test_feature_list.py` (ny), `frontend/src/api/client.js`, `frontend/src/pages/Settings.jsx`, `frontend/src/pages/Settings.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `ARCHITECTURE.md`, `FEATURES.md`, `version.json`.

## [0.90.0 build 0122] — 2026-08-11 — feature: bestillingsstatus på ønskeliste-poster (FEATURES.md #114)

Jan: *"vi skal have en status felt i ønske seksion på film/tv hvor vi kan sætte status for om film/tv er bestilt"* — som dropdown med Ikke bestilt / Bestilt ved Laserdisken / Bestilt ved iMusic / Bestilt ved div. Efterfulgt af *"lave også en list form i ønske med kolon status m.m."*, som blev afklaret med ham: genbrug den eksisterende grid/liste-toggle (#108) og vis status som en badge på ønske-kortene, frem for en helt ny tabel-visning.

Nyt `order_status`-felt på både `Movie` og `TvShow`, kun meningsfuldt for ønskeliste-poster (man ejer ikke det man ønsker sig endnu, så der er intet at bestille i biblioteket). Backend: ny `OrderStatus`-enum i `models/movie.py`, genbrugt af `tv_show.py` som de øvrige delte enums. Kun de *tre bestilte* tilstande er enum-værdier; "ikke bestilt" repræsenteres bevidst som fravær (`None`), så feltet følger `subtitles`' valgfri-mønster i stedet for at gemme en fjerde "tom" værdi (jf. CLAUDE.md regel 16's "tomhed"-punkt). Feltet er tilføjet til create-/update-/read-modellerne for begge ressourcer, til `attribute-options` (film + TV) og til dokument-mappingen i service-laget (create gemmer `.value`; update går via det eksisterende `model_dump(exclude_unset=True)`→`$set`, så en `None` også rydder feltet igen). En ukendt kilde afvises som 422 frem for at blive gemt som fritekst.

Frontend: dropdown i rediger-boksen vises **kun** når posten er en ønskeliste-post (`is_wishlist`) — første valg "Ikke bestilt" (tom → `None`), derefter de tre kilder fra `attribute-options`. Tilsvarende læse-linje i detaljevisningen, og en farvet `.movie-order-badge`-pille på ønske-kortene i både grid- og liste-visning (samme markup begge steder, jf. #108 — de to visninger kan aldrig vise forskelligt). Bestilt = fast rav-farve med hvid tekst (læser på ethvert kort i begge temaer, samme begrundelse som den grønne set-badge); ikke bestilt = dæmpet med accent-tokens. Film og TV ens.

Visuelt verificeret i browseren (CLAUDE.md regel 18) i både lyst og mørkt tema, grid + liste — rav-pillen er tydelig, "Ikke bestilt" er dæmpet men læsbar, og pillen flyder korrekt i begge visninger uden at forstyrre format-badgen i liste-tilstand.

Berørte filer: `backend/app/models/movie.py`, `backend/app/models/tv_show.py`, `backend/app/services/movie_service.py`, `backend/app/services/tv_show_service.py`, `backend/app/api/movies.py`, `backend/app/api/tv_shows.py`, `backend/tests/test_wishlist.py`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/pages/Library.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `version.json`.

## [0.89.1 build 0121] — 2026-08-11 — fix: serienummer-redigering byttede forkert serie / fejlede rå + byt-plads-bekræftelse (BUGS.md #56)

Jan: redigering af en films serienummer gav ingen klar tilbagemelding om, hvorvidt byttet skete, og han spurgte om det samme gjaldt digitale. Analysen fandt en dybere fejl: byt-plads-omnummereringen (`_reassign_serial_number` i både `movie_service` og `tv_show_service`) slog den kolliderende post op på **tallet alene** (`find_by_serial_number`), uden hensyn til hvilken serie nummeret hørte til. Men et serienummer er kun entydigt inden for sin serie (fysisk M#/T#, eller den delte digitale D#), så et fysisk skift til et optaget nummer kunne gribe en digital post med samme tal — enten omnummerere den forkerte post stiltiende, ramme en `DuplicateKeyError` (rå 500), eller (for den delte digitale serie på tværs af collections) få to poster til at hedde D#-samme-nummer. Se BUGS.md #56 for de tre udfald.

Rettelse: opslaget er nu serie-bevidst (`digital_serial_repository.find_series_holder` — fysisk matches kun mod ikke-digitale i egen collection, digital mod digitale i begge collections), swap'et skriver tilbage i den rigtige collection (også digital film ↔ digital TV-serie) og er wrappet i `try/except DuplicateKeyError` → ny `SerialNumberConflictError` (409) frem for en rå 500. De serie-blinde `find_by_serial_number` er fjernet fra begge repositories.

Tilbagemelding (Jans valg 2026-08-11 — "bekræft før, kan annulleres"): bibliotekets rediger-vindue slår først op via nyt `GET /api/movies/{id}/serial-holder`, og er nummeret optaget i samme serie, beder det brugeren bekræfte at de to bytter plads — med titlen på den post man bytter med (kan være en digital TV-serie). Serie-præfikset M/D styres fortsat af medietypen; man taster kun selve tallet.

Berørte filer: `backend/app/core/errors.py`, `backend/app/main.py`, `backend/app/repositories/digital_serial_repository.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/app/services/movie_service.py`, `backend/app/services/tv_show_service.py`, `backend/app/models/movie.py`, `backend/app/api/movies.py`, `backend/tests/test_serial_number_rules.py`, `frontend/src/api/client.js`, `frontend/src/pages/Library.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `ARCHITECTURE.md`, `BUGS.md`, `version.json`.

## [0.89.0 build 0120] — 2026-08-10 — feature: genrer på detaljevisningen + "Vis felter"-kort-toggle (FEATURES.md #113)

#111 gjorde genrer filtrerbare, men rørte hverken detaljevisningen (genrer stod kun som en ulabeled linje under titlen, sammen med år/rating) eller "Vis felter"-panelet, hvor de øvrige felter (Format, Lyd-type, Medietype, Rating, Spilletid, Plex) allerede kan slås til/fra som kort-badges. Jan: *"vi mangler også at Genre kan se på film detaje og at vi har den som en 'Show on card' funktion også"*.

Rettet ens for film og TV: (1) den ulabelede genre-linje under titlen i detalje-modalen er erstattet af en `modal-section-label`-sektion ("Genrer") i den strukturerede felt-liste, samme placering/stil som Tags — ren tekst-omplacering, ingen ny data. (2) nyt `genres: bool = False`-felt på `VisibleFields`-modellen (`backend/app/models/user.py`) og i `DEFAULT_SETTINGS` (`user_repository.py`, begge `visible_fields`/`tv_visible_fields`) — jf. BUGS.md #22's lektion om at et manglende Pydantic-felt gør `PATCH /api/users/me/settings` tavst ignorerer værdien i stedet for at afvise den, hvilket ellers ville have givet en togglen-der-ikke-huskes-fejl identisk med #22's. Ny "Genrer"-toggle i "Vis felter"-panelet (samme generiske `VISIBLE_FIELD_OPTIONS`-liste som de øvrige felter, ingen særskilt UI-kode nødvendig) og en genre-liste på kortet i samme stil som Lyd-type (`movie-meta-item`), begge betinget af at filmen/serien rent faktisk har genrer registreret.

Verificeret i browseren (CLAUDE.md regel 18): togglen tænder/slukker kortets genre-badge, overlever en fuld genindlæsning (persisteret via `PATCH /api/users/me/settings`), og detalje-modalens nye "Genrer"-sektion vises korrekt for en film med genrer. TV-siden verificeret uden fejl i konsollen (tom TV-bibliotek i test-databasen forhindrede en fuld kort/detalje-visning der, men toggle-panelet og dets tilstand virker identisk med filmsiden).

Berørte filer: `backend/app/models/user.py`, `backend/app/repositories/user_repository.py`, `backend/tests/test_auth.py`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `FEATURES.md`, `version.json`.

## [0.88.0 build 0119] — 2026-08-10 — feature: genre-filter (FEATURES.md #111) + browser-tilbage mellem faner (FEATURES.md #112)

To uafhængige features:

**Genrer som filtrerbart felt**: `genres` fandtes allerede som TMDb-hentet metadata (vist i detaljevisningen, og allerede med i `sync_all_from_tmdb` for både film og TV-serier — verificeret eksplicit efter Jans opfølgning "synkronisering fra TMDB skal opdatere det ny felt også", ingen kodeændring nødvendig dér). Det nye er filtrerbarheden. TMDb's genre-liste er ikke modelleret som en Python-enum her (i modsætning til Format/Lyd-type/Medietype), så genrer følger tags/lokation/ejers "distinct fra biblioteket"-mønster i stedet for attribute-options' faste liste: `movie_repository.distinct_genres`/`tv_show_repository.distinct_genres` (nye funktioner) bag nye `GET /api/movies/genres`/`GET /api/tv-shows/genres`-endpoints — kaldt fra service-laget (`movie_service.list_genres`/`tv_show_service.list_genres`), ikke direkte fra API-routeren, jf. CLAUDE.md regel 5's lag-arkitektur. Bevidst IKKE slået sammen på tværs af film/TV (modsat owner/location i `attribute_service.py`): TMDb's film- og serie-genre-lister er reelt forskellige lister, og hver fanes filter-panel filtrerer alligevel kun sin egen ressource. `$in`-semantik (mindst én valgt genre matcher), samme som format/audio_types/media_types, ikke tags' `$all`.

**Browser-tilbage mellem fanerne**: appen har bevidst intet router-bibliotek (samme begrundelse som `/bio`/`/login`'s rene pathname-tjek), så løsningen er et URL-hash pr. fane (`#library`, `#tv`, `#wishlist`, `#cinema`, `#print`, `#stats`, `#settings`). `window.location.hash = "..."` skubber selv en historik-post og udløser `hashchange` — den ENESTE ting der opdaterer `tab`-state, så et klik og browserens egen frem/tilbage-knap går gennem samme kodesti i stedet for to der kan drive fra hinanden. `tab` initialiseres fra et evt. hash ved opstart (direkte/delt link til en bestemt fane virker nu også). En guest der lander på en begrænset fane (Ønsker/Print/Statistik) via et gammelt hash sendes til Voldby BIO.

**Derudover**: `.claude/settings.local.json` og denne fils regel 12 er udvidet til eksplicit at nævne at test-/build-/dev-server-kommandoer (`pytest`, `npm test`, `npm run lint`, `npm run build`, `npm run dev`, `uvicorn`) er forhåndsgodkendt uden at skulle spørge — var reelt allerede dækket af den eksisterende `bypassPermissions`-tilstand, men er nu skrevet eksplicit ind i stedet for kun underforstået.

Berørte filer: `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/app/services/movie_service.py`, `backend/app/services/tv_show_service.py`, `backend/app/api/movies.py`, `backend/app/api/tv_shows.py`, `frontend/src/api/client.js`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/App.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `.claude/settings.local.json`, `CLAUDE.md`, `FEATURES.md`, `version.json`.

## [0.87.0 build 0118] — 2026-08-10 — feature: personligt lyst/mørkt tema (FEATURES.md #110)

Jan bad om at kunne vælge lyst eller mørkt tema under Indstillinger, personligt pr. bruger.

Det viste sig at være næsten intet nyt CSS-arbejde: `frontend/src/index.css` havde allerede fulde `:root[data-theme="light"]`/`:root[data-theme="dark"]`-variabelblokke plus en `prefers-color-scheme`-fallback fra projektets opstart — de var bare aldrig koblet til noget i JavaScript.

Ny `theme`-indstilling på brugeren (`Theme = Literal["light", "dark"] | None`, samme mønster som `card_size`/`view_mode`), men bevidst *valgfri* (default `None`), i modsætning til de to andre: en eksisterende bruger hvis system allerede står i mørk tilstand skal ikke pludselig blive tvunget til lys bare fordi feltet fik en fast standardværdi ved denne udrulning. Usat betyder "følg systemets `prefers-color-scheme`" — præcis den adfærd alle har haft indtil nu.

Selve koblingen er én `useEffect` øverst i `App()` (kører uanset hvilken betinget gren — login, afventer-godkendelse, den autentificerede app — der rent faktisk returneres, da hooks altid kaldes ubetinget), som sætter/fjerner `data-theme` på `document.documentElement`. Spejler `I18nProvider`s `document.documentElement.lang`-mønster for sprog stort set 1:1.

Ny `ThemeSection` i Indstillinger → Konto, lige efter sprogvalget — samme chip-baserede UI-mønster som `CardSizeSection`/`LanguageSection`.

Verificeret ved faktisk at åbne Film, TV-serier, Indstillinger, Print, login-siden og den offentlige BIO-side i browseren i begge temaer (CLAUDE.md regel 18). Det fangede én reel regression: `.cinema-public-hero`/`.cinema-public-tagline` (feature #104/#105) brugte `var(--accent-contrast)` til hero-teksten oven på skiltets faste, mørke baggrundsbillede — den variabel er beregnet til at kontrastere mod `var(--accent)` og skifter derfor betydning mellem temaerne (hvid i lyst tema, næsten sort i mørkt), så teksten blev praktisk talt usynlig i mørkt tema. Rettet til en fast hvid farve, da baggrunden bag den altid er mørk uanset app-tema. Alle øvrige `var(--accent-contrast)`-brug i kodebasen er korrekt parret med `background: var(--accent)` og er tema-sikre i forvejen.

En anden, mere alvorlig regression blev fanget ved at emulere `@media print` med mørkt tema aktivt (Playwright): Print-sidens tabeltekst arvede mørkt temas næsten-hvide `--text` og blev praktisk talt usynlig oven på hvidt papir — baggrunde springes typisk over ved print, men tekstfarven gør ikke. Rettet med en ny `@media print` i `index.css`, der nulstiller `--bg`/`--surface`/`--text`/`--text-muted`/`--border`/`--accent*` til de lyse værdier med `!important` (nødvendigt fordi `:root[data-theme="dark"]` ellers vinder på specificitet uanset regel-rækkefølge) — samme "print skal aldrig følge skærm-tilstanden"-begrundelse som `PrintList.css`'s egne `!important`-regler for at skjule hoved/fod ved print.

Berørte filer: `backend/app/models/user.py`, `backend/tests/test_auth.py`, `frontend/src/App.jsx`, `frontend/src/pages/Settings.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `version.json`.

## [0.86.0 build 0117] — 2026-08-10 — feature: nyt felt "Undertekst" på film og TV-serier (FEATURES.md #109)

Jan bad om en ny "undertekst"-kategori. Forelagt valget mellem en struktureret attribut med fast værdiliste (som Lyd-type) og et almindeligt tag, valgte han i stedet en tredje mulighed: et helt nyt felt, men med fritekst-redigering — ingen fast liste at vælge fra.

Samme mønster som `location`/`owner`: et fritekst `str | None`-felt på `Movie`/`TvShow` (`subtitles`), redigerbart i rediger-boksen og vist i læsevisningen. I modsætning til location/owner har det **ikke** fået sit eget Combobox-autocomplete-opslag (intet `find_all_subtitles`), da det ikke blev bedt om — et almindeligt tekstfelt er nok for et felt uden en naturlig, genbrugt værdimængde. Heller ikke sortering, filtrering eller en print-kolonne, af samme grund; nemt at tilføje senere hvis det viser sig at være ønsket.

Placeret som sin egen fuld-bredde-række mellem Lyd-type og Din note i begge rediger-bokse (`Library.jsx`/`TvShows.jsx`). `movie_service.sync_all_from_tmdb`/`tv_show_service.sync_all_from_tmdb` rører uændret aldrig feltet — samme beskyttelse af brugerindtastede felter som location/owner/tags allerede har.

Berørte filer: `backend/app/models/movie.py`, `backend/app/models/tv_show.py`, `backend/app/services/movie_service.py`, `backend/app/services/tv_show_service.py`, `backend/tests/test_movies.py`, `backend/tests/test_tv_shows.py`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/components/MovieLookupForm.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `version.json`.

## [0.85.0 build 0116] — 2026-08-10 — feature: grid-/listevisning (FEATURES.md #108) + fix: fysisk kopi blokerede digital Plex-import/badge (BUGS.md #55)

To uafhængige ændringer:

**Grid-/listevisning** (Jans ønske: *"lave en tilførelse til view sådan man kan vælge om film/tv skal stå i list form eller i icon som nu"*). Ny `ViewModeToggle`-komponent (delt af Film- og TV-siden) i værktøjslinjen, ved siden af "Vis felter" — to ikon-knapper der skifter og gemmer valget øjeblikkeligt. Ny `view_mode`-indstilling på brugeren (`UserSettings.view_mode`, `"grid"`/`"list"`), fælles for begge faner, samme begrundelse som `card_size` (feature #59). Listevisningen genbruger bevidst samme `<li>`-markup som grid-kortene — kun en ny `.movie-grid--list`-CSS-klasse lægger om fra en grid af poster-kort til en lodret stak af kompakte rækker, så de to visninger aldrig kan vise forskellige felter eller badges. Posteren skrumpes til en 48px-miniature; serienummer-/format-badgene, der i grid-tilstand er absolut placeret oven på en fuld-bredde-poster, flyder i stedet med som almindelige piller via `order` — ellers ville deres position regne forkert mod hele den brede række i stedet for mod den lille poster.

**Fix (BUGS.md #55)**: en fysisk registreret film/serie blokerede uforvarende den digitale Plex-udgave af samme titel — badget dukkede fejlagtigt op på den fysiske post, og Plex-importens dublet-tjek sprang den digitale udgave over fordi den fysiske allerede "fandtes". `find_all_for_plex_match` i begge repositories udelukker nu poster med `media_type: "Fysisk"` (via `$ne`, ikke et eksplicit `"Digital"`-filter, så ønskeliste-poster uden medietype stadig er med). Samme filter retter automatisk alle tre forbrugere: badget, import-dublet-tjekket og fejlsøgnings-panelets audit. Detaljevinduets "Ikke fundet i Plex"-linje er desuden skjult for fysiske poster — ellers støj på hver eneste DVD/Blu-ray for et rent fysisk bibliotek.

Berørte filer: `frontend/src/components/ViewModeToggle.jsx` (ny), `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/pages/Library.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `backend/app/models/user.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/tests/test_plex.py`, `FEATURES.md`, `BUGS.md`, `version.json`.

## [0.84.0 build 0115] — 2026-08-10 — feature: header-optælling med fysisk/digital-fordeling + kortere digitale formatlabels (FEATURES.md #107)

To uafhængige justeringer Jan bad om samme dag:

**Header-optællingen** (feature #94/#95): "142 film" / "38 serier" ved siden af login/logout viste allerede fordelingen på fysisk/digital, men kun i hover-teksten — usynlig på en telefon uden mus. Selve mærkatet viser nu fordelingen direkte: "142 film (98 fysisk / 44 digital)". `counts.movies`/`counts.shows` i18n-nøglerne fik to nye pladsholdere (`{physical}`/`{digital}`); ingen backend-ændring, da `/api/library/counts` allerede returnerede tallene (bare ubrugt til andet end hover-titlen).

**Digitale format-labels forkortet**: `Digital-UHD`/`Digital-HD`/`Digital-STD` hedder nu `D-UHD`/`D-HD`/`D-SD` — samme korte-labels-behandling som v0.22.0 gav VHS/DVD/BD/UHD (og Blu-ray→BD, 4K Ultra HD→UHD dengang). `MovieFormat`-enummet i `backend/app/models/movie.py` er kilden; formatet vises direkte fra det gemte felt på biblioteks-kortene (`.movie-format-badge`), så ingen separat frontend-label-tabel skulle opdateres. `movie_repository._FORMAT_LABEL_MIGRATIONS` fik tre nye rækker, tilføjet *efter* den eksisterende "Digital"→"Digital-HD"-række — dict-rækkefølgen betyder at en gammel, ren "Digital"-post (fra før v0.22.0) kaskaderer korrekt gennem begge omdøbninger i samme kørsel: "Digital" → "Digital-HD" → "D-HD". TV-serier fandtes ikke endnu ved v0.22.0's første omdøbning og har derfor ingen ældre labels at rydde op i, men *kan* have digitale format-værdier fra Plex-importen (feature #91) — `tv_show_repository.py` fik sin egen kopi af migrationen (kun de tre digitale rækker) kørt fra `ensure_indexes`.

Berørte filer: `frontend/src/App.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `backend/app/models/movie.py`, `backend/app/models/plex.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/tests/test_label_migrations.py`, `backend/tests/test_library_counts.py`, `backend/tests/test_movies.py`, `backend/tests/test_serial_sort_and_search.py`, `backend/tests/test_serial_number_rules.py`, `backend/tests/test_plex.py`, `MOVIE_API_REFERENCE.md`, `ARCHITECTURE.md`, `FEATURES.md`, `version.json`.

## [0.83.0 build 0114] — 2026-08-10 — feature: scan/søg går direkte til redigering, med tilbage-knap i rediger-boksen (FEATURES.md #106)

Jans ønske: et klik på en kandidat i scan-/søge-flowet skulle gå direkte til redigering i stedet for at kræve et scroll ned til et separat "review-form"-kort og et ekstra klik på "Fortsæt til redigering" dernede — og rediger-boksen manglede en vej tilbage til kandidat-valget hvis det viste sig at være det forkerte match.

For film er det tidligere mellemtrin fjernet helt: `selectCandidate` kalder nu `proceedToEdit` med det samme, og dublet-tjekket (som ikke ændrer noget ved selve oprettelsen) kører parallelt og vises som et banner *inde i* `MovieDetailModal` i stedet for at stoppe flowet. `proceedToEdit` tager nu en valgfri `candidateOverride`, fordi den kaldes synkront lige efter `setSelectedCandidate` — React har på det tidspunkt endnu ikke opdateret `selectedCandidate`.

For TV-serier er der ét reelt valg der ikke kan springes stiltiende over: findes der allerede en post af samme slags (bibliotek/ønske), skal brugeren selv vælge mellem at tilføje sæson(er) til den (feature #53) eller oprette en ny separat serie — ellers ville hvert scan af en ny sæson-boks stille oprette sin egen serie. Det samme gælder sæson-forudvalget for en helt ny serie (feature #54): det skal ske *før* rediger-boksen, fordi dens sæson-liste er read-only i kladde-tilstand (ingen `show.id` at gemme et toggle imod endnu). Begge vises nu som en rigtig `modal-backdrop`/`modal-card`-dialog (dukker op med det samme, intet scroll) i stedet for det gamle in-page `.review-form`-kort — og kun når der reelt er et valg; er der intet at gruppere ind i og ingen sæsoner at vælge, fortsætter flowet selv direkte til redigering ligesom for film.

`MovieDetailModal`/`TvShowDetailModal` har fået to nye, valgfri props — `duplicates` og `onBackToCandidates` — kun sat af `MovieLookupForm` i kladde-tilstand (`!movie.id`/`!show.id`). En ny "← Vælg en anden"-knap i rediger-boksens fod kalder `onBackToCandidates`, som rydder det aktuelle valg uden at rydde `candidates`/`barcode`/`manualQuery` — modsat `resetFormAfterSave`, som stadig bruges når hele flowet er afsluttet (gemt, eller sæson(er) tilføjet til en eksisterende serie).

De nu ubrugte `.review-form`/`.review-header`/`.review-actions`-CSS-klasser er fjernet fra `MovieLookupForm.css`.

Berørte filer: `frontend/src/components/MovieLookupForm.jsx`, `frontend/src/components/MovieLookupForm.css`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `version.json`.

## [0.82.0 build 0113] — 2026-08-10 — feature: skiltets farver som udtonet baggrund for toppen af BIO-siden (FEATURES.md #105)

Jan pegede direkte på det #104 efterlod: banneret stod i en flad, mørk boks — en isoleret enhed frem for en del af siden. Ønsket var at klippe baggrunden fra skiltet og bruge den som baggrund for resten af siden, så toppen glider ind i helheden.

Der var intet billedredigeringsværktøj installeret — hverken PIL eller ImageMagick. Løsningen er derfor ren CSS: samme skilt-JPG genbruges som `background-image` på et separat lag bag hero'en, zoomet langt ind og slørt kraftigt, så kun farvestemningen (guld/rødbrun/cremet) er tilbage. Ingen genkendelige objekter, ingen tekst — kun stemning. Et `mask-image`-gradient toner laget ud nedad, så det kun farver toppen af siden og ikke bliver ved med at konkurrere med "Om Voldby BIO" og billedgalleriet længere nede.

Den flade mørke bund fra #104 (`#1c1712`) er fjernet. Skiltet selv har i stedet fået en skygge til at løfte det af den nye, bløde baggrund — samme visuelle dybde, uden en hård kant omkring det.

Et første forsøg brugte samme baggrundshøjde (620px) uanset skærmbredde. På en smal telefon, hvor hero'en i forvejen er lavere fordi skiltet holder sin 2,5:1-facon, strakte den udtonede baggrund sig ned bag hele billedgalleriet i stedet for at være færdig med at fade ud før det. Det blev opdaget ved faktisk at se skærmbilledet ved 390px — ikke af `npm run build` eller `npm run lint`, som begge var grønne hele vejen (jf. CLAUDE.md regel 18, indført tidligere samme session, netop af denne grund). Rettet med en kortere baggrund under 640px.

Verificeret i browseren (Playwright, headless) ved 1400px og 390px, samt med login-panelet åbent, før noget blev meldt færdigt.

Berørte filer: `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/pages/CinemaPublic.css`, `FEATURES.md`, `version.json`.

## [0.81.0 build 0112] — 2026-08-10 — feature: Voldby BIOs eget skilt som topbillede på den offentlige side (FEATURES.md #104)

Jan leverede en billedfil af Voldby BIOs eget skilt (bioklassisk pergament-look, guld/rødbrunt, "VOLDBY BIO" + undertekst indbygget i grafikken). Den erstatter nu tekstoverskriften øverst på `/bio`.

Skiltet ligger i `frontend/public/cinema/voldby-bio-sign.jpg` (omdøbt fra den leverede filnavn til samme navnekonvention som de tre eksisterende showcase-fotos) og vises i et `<h1>` der ombryder billedet — alt-teksten giver skærmlæsere en rigtig overskrift uden en visuelt skjult tekst-duplikat ved siden af.

Hero-baggrunden skiftede fra accent-gradienten til en fast mørk bund. Skiltets eget stærke farvesæt ville have konkurreret med en farvet ramme rundt om det.

Login-knappen og sprogvælgeren fra feature #99 fik en ny stil: en mørk, halvgennemsigtig "glas"-flade med `backdrop-filter: blur` i stedet for den lyse flade der virkede på en ensfarvet gradient. Skiltets baggrund varierer fra cremefarvet til mørkt rødbrunt alt efter hvor gruppen lander i hjørnet, og kun en mørk flade er sikkert læselig uanset det.

Mobiltilpasningen fandt en reel fejl på egen hånd, netop den slags CLAUDE.md regel 18 (indført tidligere samme session) findes for at fange. Et første forsøg gjorde billedcontaineren højere ved smalle bredder for at "forstørre" teksten. Med `object-fit: cover` gør en smallere aspect-ratio (relativt højere container) at kilden beskæres *mere* fra siderne, ikke mindre — det modsatte af hensigten. Et screenshot ved 390px viste "VOLDBY" og "BIO" delvist skåret af i hver sin kant. Rettelsen er at lade billedet beholde sin naturlige 2,5:1-facon på alle bredder: uden nogen aspect-ratio-ændring er der intet sidebeskæring nogensinde, skiltet bliver bare kortere og teksten mindre — den rigtige måde et wordmark skal skalere. Under 380px lægges knap-gruppen i to rækker i stedet for at skrumpe knap-teksten til ulæselighed.

Verificeret ved faktisk at åbne `/bio` i en browser (Playwright, headless) ved 1400px, 390px og 360px, samt med login-panelet åbent for at bekræfte at BUGS.md #53's rettelse stadig holder oven på det nye banner — ikke kun ved `build`/`lint`, som ikke kan fange den slags kombinations-fejl.

Berørte filer: `frontend/public/cinema/voldby-bio-sign.jpg` (ny), `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/pages/CinemaPublic.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `version.json`.

## [0.80.0 build 0111] — 2026-08-09 — feature: frontend-testramme sat op (FEATURES.md #103)

BUGS.md #54 satte spørgsmålet skarpt: en fejl i `client.js` sad urørt indtil en bruger ramte den, fordi der ikke fandtes noget der kunne have fanget den før. Frontend havde `oxlint`, men ingen tests.

Vitest + Testing Library, konfigureret i `vite.config.js`s egen `test`-blok frem for en separat `vitest.config.js` — appens aliasser og plugins gælder så automatisk i testene, uden at de to konfigurationer kan drive fra hinanden. `npm test` kører suiten én gang, `test:watch` holder den kørende, `test:coverage` lægger dækning oveni.

De første fire testfiler er ikke vilkårlige eksempler — de dækker netop de klasser af fejl sessionen allerede havde stødt på uden en test til at fange dem:

- `client.test.js` låser BUGS.md #54's rettelse fast: `HTTPException` giver `detail` som en streng, FastAPIs validering giver en liste, og begge skal blive til en læsbar besked.
- `serialNumber.test.js` dækker serienummer-reglen, som skiftede tre gange på én dag (#92 → #93 → #96) — kun fysiske, så tre serier, så uden `#`.
- `i18n.test.js` tjekker at `da.json` og `en.json` har samme nøgler og samme pladsholdere. En nøgle der kun findes på det ene sprog er usynlig i koden, men synlig for brugeren.
- `MessageBanner.test.jsx` beviser at et banner bliver stående når læse-markeringen fejler, i stedet for at forsvinde og lyve over for brugeren om at han har kvitteret.

33 tests i alt, alle grønne. `npm audit fix` rettede en `nanoid`-sårbarhed der fulgte med som transitiv afhængighed af testværktøjerne.

CLAUDE.md er opdateret med to lektioner fra sessionens fejlrettelser (et rammeværks fejl har typisk en anden form end koden vores egen, og en regel indført for én gren skal gennemgås for de øvrige grene med det samme) og en ny regel 18: layout-ændringer skal ses i en browser, fordi `npm run build`/`lint` ikke kan fange at en absolut placeret container kom til at indeholde en anden (BUGS.md #53).

Berørte filer: `frontend/vite.config.js`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/test/setup.js` (ny), `frontend/src/api/client.test.js` (ny), `frontend/src/utils/serialNumber.test.js` (ny), `frontend/src/i18n/i18n.test.js` (ny), `frontend/src/components/MessageBanner.test.jsx` (ny), `CLAUDE.md`, `TECH_REFERENCE.md`, `FEATURES.md`, `version.json`.

## [0.79.1 build 0110] — 2026-08-09 — fix: valideringsfejl blev vist som "[object Object]" (BUGS.md #54)

Jans melding: oprettelse fejler hvis brugeren skriver sin e-mailadresse.

Selve afvisningen er tilsigtet. Brugernavne må kun indeholde bogstaver, tal, `-` og `_`, fordi navnet vises for alle andre i portalen — "Registreret af", "Ønsket af", audit-loggen, bruger-listen, modtagerlisten på beskeder. Registrerede folk sig med deres e-mail, ville adressen dermed være synlig for alle, også gæster. Jan valgte at beholde reglen.

Fejlen lå i beskeden. Vores egne `HTTPException`-svar har `detail` som en streng, men FastAPIs indbyggede validering (422) sender en *liste* af `{loc, msg, type}`. `client.js` gav den direkte til `new Error(detail)`, og JavaScript gør et array til teksten "[object Object]". Brugeren fik altså en uforståelig fejl uden nogen anelse om hvad der skulle rettes.

Det ramte alle valideringsfejl i appen, ikke kun brugernavnet: for kort adgangskode, ugyldigt format, ukendt sprog, tomt beskedemne. Og det er præcis det CLAUDE.md regel 16 forbyder — reglen var overholdt for vores egne fejl, men aldrig for rammeværkets, fordi de to har forskellig form på `detail`.

`readableDetail()` håndterer nu begge: en streng bruges som den er, en 422-liste trækkes ned til sine `msg`-felter og samles med punktum-adskiller, da en formular sagtens kan have to felter galt. Pydantics `"Value error, "`-præfiks fjernes — det er en implementeringsdetalje fra valideringslaget, ikke noget der giver mening for den der læser fejlen.

Beskeden om brugernavne nævner nu e-mail eksplicit, siden det er det folk faktisk prøver.

Der er ingen frontend-testsuite i projektet (kun `oxlint`), så `readableDetail` er ikke dækket af en automatisk test. Backend-testen låser fast at 422-svaret rent faktisk indeholder den besked frontend nu viser.

Berørte filer: `frontend/src/api/client.js`, `backend/app/models/user.py`, `backend/tests/test_auth.py`, `BUGS.md`, `version.json`.

## [0.79.0 build 0109] — 2026-08-09 — feature: læsevisning som standard (#101) + ryd-knap i søgefelterne (#102)

### Detaljevinduet åbner i læsevisning (FEATURES.md #101)

Jans ønske: man skal ikke lande midt i en redigeringsformular, bare fordi man klikker på en film for at se hvad den handler om.

Læsevisningen fandtes allerede — den blev bygget til guest-rollen i feature #72 og grupperet om i #87. Ændringen er derfor ikke en ny visning, men at den nu gælder alle der ikke aktivt har trykket Redigér, i stedet for at være bestemt af rollen. Kun selve knappen er rolle-betinget: en guest ser den ikke og bliver i læsevisningen.

Undtagelsen er "kladde"-tilstanden fra scan-flowet, hvor filmen endnu ikke findes. Der er intet at læse, og man er kommet for at udfylde den, så den åbner direkte i redigering — og har af samme grund ingen Fortryd-knap at vende tilbage til.

`cancelEditing` nulstiller felterne til postens gemte værdier og er placeret lige efter `useState`-linjerne. De to skal holdes ens når der kommer et felt til, og det er lettere at få øje på når de står ved siden af hinanden.

Sæsoner og episoder forbliver klikbare i læsevisningen. De gemmes hver for sig med det samme og hører ikke til Gem/Fortryd; at kræve et klik på Redigér for at hakke et afsnit af ville lægge friktion på den hyppigste handling på en TV-serie.

### Ryd-knap i søgefelterne (FEATURES.md #102)

Et kryds i højre side af søgefeltet i Film, TV-serier og print-listen, som rydder søgningen.

Egen knap frem for at stole på browserens indbyggede: `type="search"` viser kun et kryds i WebKit og Chrome, ikke i Firefox — så muligheden var usynlig for en del af brugerne. Browserens eget kryds skjules hvor det findes, så der ikke står to side om side.

Print-siden har fået sin egen wrapper-klasse i stedet for at genbruge `.search-input-wrap` fra Library.css. Den importerer ikke det stylesheet, og en klasse defineret i en anden sides fil ville kun virke sålænge begge tilfældigvis endte i samme bundle.

Berørte filer: `frontend/src/pages/Library.jsx`, `frontend/src/pages/Library.css`, `frontend/src/pages/TvShows.jsx`, `frontend/src/pages/PrintList.jsx`, `frontend/src/pages/PrintList.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `version.json`.

## [0.77.0 build 0108] — 2026-08-09 — feature: besked-system fra admin til brugerne (FEATURES.md #100)

En admin skriver emne og tekst og vælger enten "alle aktive brugere" eller én enkelt. Modtagerne ser beskeden som en banner øverst i indholdet indtil de lukker den, og afsenderen kan se hvem der har gjort det.

Modtagerlisten er et øjebliksbillede taget ved afsendelse og gemmes på beskeden frem for at blive slået op ved hver visning. Det var Jans valg, og det har to konsekvenser der begge er ønskede: en besked om fredagens visning møder ikke en bruger der opretter sig tre måneder senere, og "læst af 2 af 5" er et fast tal i stedet for et der ændrer sig når der kommer nye brugere til.

Kun aktive konti kommer med. En `pending` eller `disabled` bruger kan ikke bruge appen og ville bare stå som ulæst for evigt. Afsenderen springes over — man skal ikke mødes af en banner om sin egen besked.

To detaljer i datalaget er værd at nævne, fordi begge er den slags der virker indtil to personer gør noget samtidig:

Læse-markeringen er et punktum-sti-`$set` med positional operator (`recipients.$.read_at`), aldrig en read-modify-write af hele modtagerlisten. To brugere der lukker den samme rundsendte besked samtidig ville ellers kunne overskrive hinandens markering — netop mønstret CLAUDE.md regel 16 og BUGS.md #13 handler om.

Indbakke-opslaget bruger `$elemMatch` frem for to separate `recipients.`-betingelser. Uden det kan de to betingelser opfyldes af hvert sit element i arrayet, så en besked dukker op i din indbakke fordi *en anden* modtager ikke har læst den.

At markere en besked man ikke selv har modtaget giver 404 — samme svar som en besked der ikke findes. Hvilke beskeder der findes til andre brugere er ikke ens egen oplysning.

Bannere frem for en klokke med ulæst-tæller er en bevidst afvejning, ikke en forenkling: beskeden er svær at overse, men en lukket besked er væk, og der er ingen historik at finde den frem i.

Fundet under test: `Field(min_length=1)` tæller mellemrum med, så en besked med kun mellemrum i emnet slap igennem og blev tom når teksten trimmes ved gem. Feltet trimmes nu *før* validering — samme "tjek alle former for tom"-princip som CLAUDE.md regel 16 beskriver.

Berørte filer: `backend/app/models/message.py` (ny), `backend/app/repositories/message_repository.py` (ny), `backend/app/services/message_service.py` (ny), `backend/app/api/messages.py` (ny), `backend/app/core/errors.py`, `backend/app/main.py`, `backend/tests/test_messages.py` (ny), `frontend/src/components/MessageBanner.jsx` (ny), `frontend/src/components/MessageBanner.css` (ny), `frontend/src/App.jsx`, `frontend/src/api/client.js`, `frontend/src/pages/Settings.jsx`, `frontend/src/pages/Settings.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `ARCHITECTURE.md`, `FEATURES.md`, `version.json`.

## [0.76.1 build 0107] — 2026-08-09 — fix: login-boksen på /bio blev mast sammen (BUGS.md #53)

En regression fra feature #99 samme dag.

#99 samlede sprogvælgeren og login-knappen i én gruppe øverst til højre. Gruppen er `position: absolute` og kun så bred som sit indhold. `PublicLoginToggle` returnerede enten knappen *eller* hele login-panelet — så da knappen flyttede ind i gruppen, fulgte panelet med. Panelets eget `position: absolute` og `max-width: calc(100% - 40px)` blev derefter beregnet mod gruppens få pixels i stedet for mod hero-området, og panelet blev nogle få pixels bredt.

Fejlen slap gennem både bygge- og lint-trin: JSX og CSS var hver for sig gyldige, og det var kun kombinationen af de to placeringer der var forkert. Den slags viser sig kun ved at se på siden.

`PublicLoginToggle` er nu splittet i to komponenter. Knappen bliver i hjørne-gruppen; `PublicLoginPanel` er en søskende direkte i `.cinema-public-hero` og får derfor igen sin bredde af hero-området. Åben/lukket-tilstanden er løftet op i `CinemaPublic`, da de to står hvert sit sted i træet.

Panelet placeres under gruppen frem for oven i den, fordi knappen bliver stående mens panelet er åbent — dels så gruppen ikke skifter bredde og rykker sprogvalget rundt, dels så knappen kan lukke panelet igen. Den markeres som aktiv imens.

Samtidig byttet om på rækkefølgen i gruppen: login-knappen står nu først og sprogvalget efter, som Jan bad om i samme melding.

Berørte filer: `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/pages/CinemaPublic.css`, `BUGS.md`, `version.json`.

## [0.76.0 build 0106] — 2026-08-09 — feature: sprogvalget står ved siden af login (FEATURES.md #99)

Feature #97 satte sprogvalget i modsatte hjørne af login-knappen på den offentlige BIO-side, og som et centreret element for sig selv i login-kortet. Begge steder stod det visuelt afkoblet fra det man faktisk er kommet for.

På BIO-siden ligger vælger og login-knap nu i én gruppe øverst til højre. Placeringen er flyttet fra de to elementer op på gruppen, så de ikke længere er absolut placeret hver for sig og kan komme til at overlappe hinanden ved en senere ændring.

I login-kortet står vælgeren nu på linje med logoet i toppen — samme relative plads som på BIO-siden, så den sidder samme sted uanset hvilken vej man kom ind i appen.

`.auth-brand`s `justify-content: center` er bevaret med vilje: `PendingApproval.jsx` deler klassen, og dér står logoet alene og fylder kortets bredde. På login-siden er `.auth-brand` nu et flex-item der hugger sit indhold, så centreringen er uden virkning — men fjernes den, rykker logoet på den anden side.

Berørte filer: `frontend/src/pages/Login.jsx`, `frontend/src/pages/Login.css`, `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/pages/CinemaPublic.css`, `FEATURES.md`, `version.json`.

## [0.75.0 build 0105] — 2026-08-09 — feature: sorterbare kolonner og lyd-type i print-listen (FEATURES.md #98)

Print-listens kolonneoverskrifter er nu klikbare — Serienr., Titel/Navn, År, Format, Lokation og en ny Lyd-type-kolonne. Første klik sorterer stigende, næste vender retningen.

Sorterings-nøglen er logisk frem for et API-feltnavn. De to tabeller sorteres af det samme klik, men hedder forskelligt i backenden: film har `title`, serier har `name`. Hver kolonne oversætter derfor sig selv pr. ressource, og en kolonne der ikke findes for den ene tabel falder tilbage til serienummeret, så listen bevarer en fast orden i stedet for at komme i vilkårlig rækkefølge.

Sæson-kolonnen er bevidst ikke sorterbar: tallet er beregnet ud fra `seasons[]` og findes ikke som sorterbart felt i backenden.

Pilen printes med — en udskrift skal kunne vise hvilken orden den blev lavet i — mens klik-markøren kun gælder på skærm. Pilen har fast bredde, så overskrifterne ikke rykker sig når sorteringen skifter kolonne; en tabel der hopper ved hvert klik er svær at aflæse.

En test tjekker hvert af print-listens kolonne-felter mod backendens faktiske sorterings-whitelist. `parse_sort_param` dropper ukendte felter stiltiende (så et gemt preset med et siden fjernet felt ikke brækker), hvilket betyder at en tastefejl her ville vise sig som "sorteringen gør ingenting" frem for som en fejl.

Berørte filer: `frontend/src/pages/PrintList.jsx`, `frontend/src/pages/PrintList.css`, `backend/tests/test_serial_sort_and_search.py`, `FEATURES.md`, `version.json`.

## [0.74.0 build 0104] — 2026-08-09 — feature: sprogvalg (DK/ENG) i login-boksen (FEATURES.md #97)

Feature #89 gemte sproget pr. bruger i databasen — Jans valg, så det følger med mellem telefon og PC. Konsekvensen, som blev flaget dengang, var at login-skærmen og en udelogget besøgende på `/bio` altid var på dansk: der er ingen bruger at læse præferencen fra på det tidspunkt. Det er nu lukket.

Valget på pre-auth-skærmene ligger i `localStorage` og er en *enheds*-præference, ikke en konkurrent til konto-indstillingen. Så snart man er logget ind, vinder kontoens eget sprog — så et login på en fremmed enhed, hvor nogen har valgt engelsk, aldrig ændrer ens egen konto.

Ved registrering følger valget derimod med som den nye kontos startsprog. Det er dét, der giver det tidlige valg reel effekt: vælger man ENG i boksen og opretter sig, er man på engelsk fra første indlogning i stedet for at skulle finde Indstillinger bagefter. `UserRegister.language` er valgfri, så ældre klienter og rene API-kald stadig virker og får kildesproget.

`auth_service.register` kopierer nu `DEFAULT_SETTINGS` frem for at referere det. Det er et modul-globalt dict, og et sprogvalg skrevet direkte ind i det ville have båret videre til hver eneste efterfølgende registrering — en test låser den fast.

Vælgeren er to knapper frem for en dropdown: med kun to sprog ville en dropdown kræve et klik for overhovedet at afsløre at valget findes. På den offentlige BIO-side står den i modsatte hjørne af login-knappen, så de to ikke konkurrerer om samme plads, og får hero-gradientens gennemsigtige behandling i stedet for appens almindelige flade.

Berørte filer: `backend/app/models/user.py`, `backend/app/services/auth_service.py`, `backend/tests/test_registration_language.py` (ny), `frontend/src/components/LanguagePicker.jsx` (ny), `frontend/src/components/LanguagePicker.css` (ny), `frontend/src/i18n/index.js`, `frontend/src/App.jsx`, `frontend/src/api/client.js`, `frontend/src/pages/Login.jsx`, `frontend/src/pages/Login.css`, `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/pages/CinemaPublic.css`, `ARCHITECTURE.md`, `FEATURES.md`, `version.json`.

## [0.73.0 build 0103] — 2026-08-09 — feature: serienummer uden #, serie-grupperet sortering og søgning på nummer (FEATURES.md #96)

Fire ting Jan bad om i samme omgang.

**`#` er væk fra visningen.** `M0042` frem for `M#0042`.

**Sorteringen på serienummer er nu sammensat af serie + nummer.** De tre serier (M/T/D) tælles hver for sig, så en sortering på nummeret alene blandede M1 og D1 sammen i listen. Standard-valget grupperer digitale først, som Jan bad om.

**Et andet valg vender grupperingen**, så den fysiske serie står først. Det krævede at `SORT_FIELDS` kan udvide ét valg til flere mongo-nøgler. Serie-nøglen har en *låst* retning og kun nummeret følger op/ned-knappen — vendte knappen også serien, ville et klik flytte hele den ene serie hen over den anden, hvilket er en anden sortering og ikke den omvendte.

**Søgefeltet slår nu serienumre op.** `M42` afgrænser til den fysiske serie, `D42` til den digitale, og et bart `42` finder begge. Foranstillede nuller og små bogstaver accepteres, så man kan søge på nummeret præcis som det står på skærmen. Et ukendt bogstav som `S1` falder tilbage til almindelig tekstsøgning frem for at matche ingenting — ellers kunne man ikke længere finde en titel der indeholder "S1".

Serienummeret er tilføjet som endnu et OR-alternativ i `build_text_query` frem for som en separat API-parameter: det er en ligeværdig måde at finde en titel på, ikke et særskilt felt, og skal virke i det samme søgefelt som "pacino".

Sorteringen bygger på at "Digital" står før "Fysisk" alfabetisk. Det er en egenskab ved etiketterne, ikke et tilfælde — og etiketterne *er* blevet omdøbt før (v0.22.0). `test_serial_series_sort_order_depends_on_label_ordering` låser den fast, så en omdøbning brækker en test frem for stille at vende listen om.

Berørte filer: `backend/app/repositories/text_search.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/app/services/movie_service.py`, `backend/app/services/tv_show_service.py`, `backend/tests/test_serial_sort_and_search.py` (ny), `frontend/src/utils/serialNumber.js`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `ARCHITECTURE.md`, `FEATURES.md`, `version.json`.

## [0.72.0 build 0102] — 2026-08-08 — feature: farvede tællere og "Log ud" helt til højre i app-hovedet (FEATURES.md #95)

To justeringer Jan bad om.

**"Log ud" står nu yderst til højre.** `.app-header-inner` bruger `justify-content: space-between`, hvilket virker så længe hovedet er én linje — men det ombryder på smallere skærme, og på den nye linje endte bruger-blokken midtstillet. `margin-left: auto` på `.header-user` skubber den ud til kanten uanset ombrydning.

**Optællingen har fået farve**, og er samtidig delt i to selvstændige mærkater frem for én sætning: film og TV-serier er to adskilte ressourcer, og hvert tal skal kunne aflæses for sig. Film får den bløde accent-flade som `.brand-mark` og `.role-badge` allerede bruger; TV-serier en neutral flade med kant, så de to er til at skelne på et øjekast i stedet for at være to ens klatter.

Rettet undervejs: optællingen forsvandt sammen med brugernavnet på telefon. Media query'en skjulte `.header-user span`, som rammer alle `span` i blokken — også tællerne. Nu skjules kun selve brugernavnet, og tællerne bliver stående i en lidt mindre udgave. De er hele pointen med feature #94 og fylder mindre end navnet gjorde.

Berørte filer: `frontend/src/App.jsx`, `frontend/src/App.css`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `FEATURES.md`, `version.json`.

## [0.71.1 build 0101] — 2026-08-08 — fix: TV-serier fra Plex blev sprunget over ved import (BUGS.md #52)

Jans fejlmelding: TV-serier importeret fra Plex dukkede ikke op under TV-serier.

Som ved BUGS.md #51 var første skridt at afgøre om placeringen var forkert. En rundtur-test — importér en Plex-serie, hent derefter `/api/tv-shows` — bestod: importen lagde serien korrekt i `tv_shows`. Så det var ikke dér, det gik galt.

Årsagen var samspillet mellem to features fra tidligere samme dag. Feature #92 gjorde `format` påkrævet på en biblioteks-post, og #91 udledte det af Plex' `videoResolution`. Kunne opløsningen ikke afgøres, blev elementet sprunget over og kun listet som "kunne ikke matches".

Det rammer TV-serier systematisk. En films opløsning står i det sektions-svar der alligevel hentes, så den er praktisk talt altid til stede. En series opløsning ligger derimod kun på episoderne og kræver et ekstra kald pr. serie — og enhver fejl dér, en langsom server, en serie uden hentede episoder, et uventet svar, kostede hele importen af den serie. Resultatet var en import der så ud til at virke, men hvor en hel kategori manglede.

Afvejningen er nu vendt om. Elementet importeres med `Digital-HD` som fallback og markeres `format_is_fallback`. Det er ikke et gæt på må og få: `movie_repository._FORMAT_LABEL_MIGRATIONS` bruger allerede præcis den fallback for gamle "Digital"-poster uden kvalitetstrin, og HD er langt den almindeligste. Et enkelt felt der måske skal rettes er bedre end en titel der aldrig når ind i portalen — især når formatet ikke indgår i nogen anden beslutning: serienummer-serien afgøres af `media_type`, ikke af `format`.

Forhåndsvisningen skriver "format ukendt i Plex — sat til Digital-HD" på de berørte, så de kan efterses bagefter.

Berørte filer: `backend/app/services/plex_service.py`, `backend/app/models/plex.py`, `backend/tests/test_plex.py`, `frontend/src/pages/Settings.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `BUGS.md`, `version.json`.

## [0.71.0 build 0100] — 2026-08-08 — feature: D#-serie til digitale udgaver (#93) + samlet optælling i app-hovedet (#94)

To ønsker fra Jan i samme omgang.

### Digitale udgaver får deres egen nummerserie (FEATURES.md #93)

Feature #92 lod digitale poster helt uden nummer. Jans justering: de skal også have et, med præfikset `D#`.

Der er nu tre serier der tælles hver for sig — fysiske film (`M#`), fysiske TV-serier (`T#`) og alle digitale udgaver under ét (`D#`). Den digitale er delt på tværs af film og serier, så et D#-nummer altid peger på præcis én ting. To adskilte D#-serier ville give to forskellige udgaver der begge hed D#0001, netop den tvetydighed M#/T#-opdelingen fjernede.

Fordi serien går på tværs af to collections, bor den i sit eget `digital_serial_repository` — det eneste sted der kan se begge. Entydighed på tværs af collections kan intet index udtrykke, så tildelingen springer optagne numre over, ligesom de fysiske serier gør.

Det unikke index er lagt om fra `serial_number` alene til `(serial_number, media_type)`: M#5 og D#5 er to forskellige udgaver og skal kunne findes side om side. `partialFilterExpression` frem for `sparse`, fordi et sammensat sparse-index indekserer et dokument så snart ét af felterne findes — to nummerløse poster med samme medietype ville så kollidere på `(null, "Fysisk")`.

Et skift af medietype flytter nu posten mellem serierne i stedet for bare at fjerne nummeret.

Migreringen har to kriterier, begge valgt så den er idempotent og kan køre ved hver opstart: digitale poster uden nummer får et fra D#-rækken, og digitale poster hvis nummer kolliderer med en fysisk post omnummereres (det er poster fra før #92, hvis nummer stammer fra den fysiske serie). Efter første kørsel er ingen af kriterierne opfyldt længere.

Fundet undervejs, og en reel fejl: de fysiske tællere sprang numre over, fordi kollisions-tjekket så på *alle* poster i collectionen og ikke kun dem i samme serie. En digital post med nummer 1 fik dermed den næste fysiske til at blive nummer 2 — de to serier kunne påvirke hinanden selvom de er uafhængige.

### Samlet optælling i app-hovedet (FEATURES.md #94)

"142 film · 38 serier" ved siden af brugernavnet, synligt fra enhver side uden at navigere hen til statistikken (Jans valg blandt tre placeringer).

Film og TV-serier holdes adskilt — de er to bevidst adskilte ressourcer (CLAUDE.md), og et samlet tal ville skjule netop den opdeling resten af appen er bygget op om. Ønskelisten tælles for sig og indgår ikke i totalen; den er ikke noget man *har*.

`GET /api/library/counts` bruger tre `count_documents` pr. ressource frem for at hente dokumenterne: tallet skal kunne stå i hovedet ved hver sideindlæsning og må ikke koste mere end et par index-opslag. Åbent for alle logget-ind brugere inklusive guests, da det er ren læsning.

Tallet genhentes når biblioteket ændrer sig, så det ikke bliver stående til næste sideindlæsning. Fordelingen på fysisk/digital ligger i hover-teksten — hovedet skal ikke være et dashboard. På smalle skærme skjules optællingen sammen med brugernavnet, hvor pladsen allerede er knap.

Berørte filer: `backend/app/repositories/digital_serial_repository.py` (ny), `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/app/services/movie_service.py`, `backend/app/services/tv_show_service.py`, `backend/app/services/library_backup_service.py`, `backend/app/api/library_backup.py`, `backend/app/models/backup.py`, `backend/tests/test_serial_number_rules.py`, `backend/tests/test_library_counts.py` (ny), `frontend/src/utils/serialNumber.js`, `frontend/src/App.jsx`, `frontend/src/App.css`, `frontend/src/api/client.js`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/pages/PrintList.jsx`, `frontend/src/pages/Wishlist.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `ARCHITECTURE.md`, `FEATURES.md`, `version.json`.

## [0.69.1 build 0099] — 2026-08-08 — fix: en delvist hentet Plex-liste blev behandlet som hele biblioteket (BUGS.md #51)

Jans fejlmelding: film importeret fra Plex blev bagefter vist som "Ikke fundet i Plex". Selvmodsigende, da de netop var oprettet ud fra Plex' eget index.

Første skridt var at afgøre om match-logikken selv var forkert. En rundtur-test — importér fra et fake Plex-bibliotek, og slå derefter tilgængeligheden op — bestod i alle de normale tilfælde: både for elementer hvor Plex selv leverede et TMDb-id, og for dem importen fandt via TMDb-søgning. Matchningen var altså ikke problemet.

Fejlen lå et lag under. `_fetch_section_items` hentede en sektion sidevist og afbrød løkken ved enhver fejl undervejs — netværksfejl, ikke-200, ikke-JSON — for derefter at returnere den delvise liste. `fetch_library` behandlede den som hele biblioteket og rapporterede `ok: true`.

Et halvt hentet bibliotek er værre end ingen data, fordi det giver aktivt forkerte svar: film der ligger i Plex rapporteres som "ikke fundet", og intet sted forklarer hvorfor. Fejlede første side, så hele biblioteket tomt ud, og hver eneste film fik beskeden. Kun en WARNING i backend-loggen røbede det.

Nu returnerer `_fetch_section_items` `(elementer, fejl)`, og enhver ufuldstændig hentning fejler hele `fetch_library` med en læsbar besked. Derudover sammenlignes antallet af hentede elementer med `MediaContainer.totalSize`, som Plex oplyser på hver side — så en afkortning fanges også når hver enkelt forespørgsel svarede 200. Sidegrænsen (`MAX_PAGES`) behandles nu på samme måde; den gav før kun en advarsel.

Brugeren ser derfor "Plex-biblioteket kunne ikke hentes fuldstændigt" i stedet for et stille, forkert "ikke fundet i Plex" på alt.

Om det var præcis dette der ramte Jan, kan først afgøres mod hans egen server: fejlsøgnings-panelet under Indstillinger → Nøgler viser nu enten den nye fejlbesked (så var det dette) eller et match-antal (så ligger det i titel/år-sammenligningen mod hans data).

Berørte filer: `backend/app/integrations/plex_client.py`, `backend/tests/test_plex.py`, `BUGS.md`, `version.json`.

## [0.69.0 build 0098] — 2026-08-08 — feature: serienumre kun til fysiske udgaver, M#/T#-præfiks (FEATURES.md #92)

Jans krav: kun fysiske film og serier skal have serienummer, film skal have præfikset `M#` og serier `T#`, og de to skal tælles hver for sig.

Det sidste var allerede på plads — `movie_serial` og `tv_show_serial` har været adskilte tællere siden TV-serier blev en selvstændig ressource. Det nye er præfikset, der gør M#0001 og T#0001 til to synligt forskellige udgaver i stedet for to poster der begge hedder "#0001".

Den egentlige ændring er hvem der overhovedet får et nummer. Et serienummer svarer til en plads på en hylde, så en digital kopi får ingen — og forbruger dermed heller ikke et nummer, så serien ikke får huller af noget der aldrig har stået nogen steder.

For at gøre den beslutning entydig er **medietype og format nu påkrævet** ved oprettelse af en biblioteks-post. Det var Jans svar på hvad der skulle ske med de mange eksisterende poster uden medietype: gør det umuligt at oprette flere af dem. Ønskelisten er undtaget — man ejer ikke det man ønsker sig endnu, så der er hverken en fysisk udgave at beskrive eller et nummer at tildele.

Kravet håndhæves i backend (`MovieCreate`/`TvShowCreate`-validatorer), ikke kun i UI'et. CLAUDE.md regel 16 siger det direkte om den slags regler: en regel der kun findes i frontend er triviel at omgå og gælder ikke for andre klienter. Rediger-vinduets gem-knap er spærret med en forklarende besked, så kravet mødes før man trykker frem for at blive mødt af en 422.

Reglen håndhæves begge veje (Jans valg): skifter en fysisk udgave til digital, frigives dens nummer til genbrug; går den den anden vej, tildeles et nyt. Uden det ville reglen kun holde på oprettelses-tidspunktet, og der kunne ligge digitale poster med numre bagefter.

En engangs-migrering ved opstart fjerner serienumre fra eksisterende poster med medietype Digital (Jans valg: ryd op i det der allerede ligger). Poster helt **uden** medietype røres bevidst ikke — de er fra før reglen fandtes og kan lige så godt være fysiske udgaver hvor feltet aldrig blev udfyldt; at fjerne deres nummer ville slette noget der kan stå skrevet på et cover.

Konsekvens for Plex-importen: importerede poster er digitale og får derfor ingen numre. Kan Plex ikke oplyse en opløsning, kan det nu påkrævede format ikke udledes, og titlen rapporteres i stedet for at blive oprettet uden — samme princip som det entydige TMDb-match i feature #90.

To ting fundet undervejs: de tre `formatSerial`-kopier i Library/TvShows/PrintList var allerede begyndt at drive fra hinanden (kun PrintList håndterede et manglende nummer), og er nu samlet i `utils/serialNumber.js`. Og serienummer-badget var betinget af ønskeliste-flaget frem for af nummeret selv — hvilket ville have vist "M#NaN" på enhver digital biblioteks-post.

Testene: 239 oprettelses-payloads i suiten skulle klassificeres for at afspejle det nye krav, og tre tests af ønskeliste→bibliotek-flytning skulle have medietypen med, da flytningen ellers ikke længere tildeler et nummer. `test_serial_number_rules.py` (17 tests) dækker selve reglerne, begge retninger og migreringen.

Berørte filer: `backend/app/models/movie.py`, `backend/app/models/tv_show.py`, `backend/app/services/movie_service.py`, `backend/app/services/tv_show_service.py`, `backend/app/services/plex_service.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/tests/test_serial_number_rules.py` (ny) + 30 eksisterende testfiler, `frontend/src/utils/serialNumber.js` (ny), `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/pages/PrintList.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `ARCHITECTURE.md`, `FEATURES.md`, `version.json`.

## [0.68.0 build 0097] — 2026-08-08 — feature: Plex-import udfylder selv medietype og format (FEATURES.md #91)

Jans ønske: importerede film og serier skal selv få medietype "Digital", og formatet skal følge om de ligger i 4K, HD eller SD på Plex.

Værdierne fandtes allerede. `MovieFormat` fik i v0.22.0 splittet "digital" i kvalitetstrin (`Digital-UHD`/`Digital-HD`/`Digital-STD`), og `MediaType.DIGITAL` har været der hele tiden — så importerede poster bruger præcis samme vokabular som håndoprettede, ikke et parallelt sæt Plex-etiketter.

For film kostede det ingenting: opløsningen står allerede i `Media[].videoResolution` i det `/all`-svar feature #88 i forvejen henter. Formatet kan derfor vises i forhåndsvisningen uden et eneste ekstra kald.

For serier ligger opløsningen kun på episoderne. Sæson-opslaget fra feature #90 er derfor lagt om fra `/children` til `/allLeaves`, som returnerer alle seriens episoder med både `parentIndex` (sæsonnummeret) og deres egen `Media`. Samme antal kald som før, men nu med begge svar — i stedet for at skulle bruge to.

En serie med blandede opløsninger får den **hyppigste**, ikke den højeste. Ét enkelt 4K-afsnit ud af tres gør ikke serien til en UHD-udgave. Står to lige, vinder den højere kvalitet.

En ukendt eller manglende opløsning giver et tomt format frem for et gæt — men medietypen sættes stadig til Digital, da den følger af at ligge på en medieserver og ikke af opløsningen.

Gælder **kun** ved import. Eksisterende posters format røres ikke: har man en fysisk DVD der *også* ligger på Plex, ville en tilbagevirkende opdatering overskrive et format man selv har indtastet med noget forkert.

Berørte filer: `backend/app/integrations/plex_client.py`, `backend/app/services/plex_service.py`, `backend/app/models/plex.py`, `backend/tests/test_plex.py`, `frontend/src/pages/Settings.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `MOVIE_API_REFERENCE.md`, `FEATURES.md`, `version.json`.

## [0.67.0 build 0096] — 2026-08-08 — feature: importér eksisterende Plex-bibliotek ind i portalen (FEATURES.md #90)

Jans spørgsmål: kan vi få det Plex allerede har ind i portalen? Ja — og det meste af arbejdet var gjort i feature #88.

Importen genbruger #88's biblioteks-index, så der ikke laves nye Plex-kald ud over ét pr. importeret TV-serie. Matchningen af "har vi den allerede?" er den *omvendte* retning af badget, og løses af samme kode: `_library_as_index()` pakker vores egne dokumenter i nøjagtig samme index-form som Plex-indexet, så `_match` kan bruges begge veje. To separate implementeringer ville uundgåeligt drive fra hinanden, og så kunne badget og importen være uenige om hvad der er samme film.

Forhåndsvisning og udførelse er samme endpoint med forskellig `dry_run`, af samme grund: havde forhåndsvisningen sin egen gennemgang, kunne den vise noget andet end det der faktisk skete. `dry_run` er default `true` — en import kan oprette hundredvis af poster, og der er ingen fortryd-knap bagefter ud over at slette dem igen.

Plex-elementer uden TMDb-id (ældre agenter giver kun IMDb-id eller ingenting) slås op på TMDb via titel og importeres **kun** ved præcis ét resultat med samme normaliserede titel og samme år. Jans valg blandt tre forelagte muligheder: hellere rapportere titlen som umatchet, end lade et gæt blive til data der ser lige så rigtig ud som resten af biblioteket. De umatchede listes i panelet, så de kan tilføjes manuelt.

TV-serier får de sæsoner der faktisk ligger i Plex markeret som ejede — ellers ville en importeret serie lande med alt markeret "ikke ejet" selvom den står på serveren. Det kræver `/library/metadata/{ratingKey}/children`, som `/all` ikke leverer, men kun for serier der rent faktisk importeres.

Alt importeret får taget `Plex-import` (kan ændres eller tømmes i panelet), så resultatet kan filtreres frem i biblioteket og rulles tilbage hvis det ikke blev som forventet.

Batch-forudsætningerne tjekkes før løkken (CLAUDE.md regel 16): både manglende Plex-konfiguration og manglende TMDb-token ville få hvert eneste element til at fejle af samme grund — en oplysning man skal have én gang, ikke hundrede. Et TMDb-rate-limit stopper hele importen med det samme frem for at hamre en allerede-throttlet API; det allerede oprettede springes over næste gang, så importen bare kan køres igen.

Rettet under udvikling: panelets resultat-blok forsvandt mens importen kørte, fordi render-betingelsen kun dækkede `preview` og `done`. Man stod dermed uden feedback under et kald der kan tage minutter for et stort bibliotek.

Dokumentation: MOVIE_API_REFERENCE.md har fået den konkrete fremgangsmåde til at finde sit Plex-token (web-UI'ets "Get Info → View XML", samt `Preferences.xml` på serveren) — Jans spørgsmål samme dag, hvor der før kun stod en henvisning til Plex' egen vejledning.

Berørte filer: `backend/app/models/plex.py`, `backend/app/integrations/plex_client.py`, `backend/app/services/plex_service.py`, `backend/app/api/plex.py`, `backend/tests/test_plex.py`, `frontend/src/api/client.js`, `frontend/src/pages/Settings.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `ARCHITECTURE.md`, `MOVIE_API_REFERENCE.md`, `FEATURES.md`, `version.json`.

## [0.66.0 build 0095] — 2026-08-08 — feature: resten af brugerfladen oversat, #89 færdig (FEATURES.md #89, del 3-4/4)

Sidste del af sprogvalget: TV-serier, Indstillinger (den største enkeltfil, ~1.800 linjer), Statistik, Print, Voldby BIO — både den indloggede fane og den offentlige `/bio` — samt visnings-ønske-boksen, biograf-showcasen og scanneren. I alt 472 nøgler i hvert af de to kataloger; hele brugerfladen er dækket, og featuren er markeret `done`.

Tre mønstre gik igen nok til at være værd at skrive ned (nu i TECH_REFERENCE.md):

**Modul-konstanter må ikke indeholde færdig tekst.** `SORT_OPTIONS`, `VISIBLE_FIELD_OPTIONS`, `CARD_SIZE_OPTIONS`, `PHOTOS` og `settingsTabs()` evalueres alle ved import — længe før nogen oversætter findes. De bærer nu `labelKey`/`altKey`, og nøglen slås op ved render. Det samme gælder `TmdbSyncSection`s fire tekst-props, som blev til `*Key`-props.

**Rene funktioner tager `t`/`locale` som argument** frem for at kalde hooks. `formatRuntime` (Statistik) og `cinemaFormat.js`' fire dato-funktioner er ikke komponenter og må derfor ikke kalde `useT()`/`useLocale()`. `cinemaFormat`s locale-parameter defaulter til dansk, netop fordi den offentlige `/bio` kalder dem uden en indlogget bruger.

**Datoer går gennem `useLocale()`.** Otte steder havde hardkodet `toLocaleDateString("da-DK")`. `formatTime` sætter desuden `hour12: false` eksplicit: `en-GB` giver AM/PM på nogle platforme, og hele appen — inklusive `DateTime24Input` — regner med 24-timers ur.

Den offentlige `/bio` er nu wrappet i provideren når der *er* en indlogget bruger. En udelogget besøgende har stadig ingen præference at læse og får dansk, men husets egne brugere får deres eget sprog på den delte adresse. Login-skærmen forbliver dansk — der er intet at læse fra på det tidspunkt.

`index.html` stod med `lang="en"` på en app der udelukkende var dansk. Den er rettet til `da` og opdateres nu til det viste sprog fra `I18nProvider` — skærmlæsere vælger stemme og udtale ud fra den, og browserens oversættelses-tilbud retter sig efter den.

Katalogerne er verificeret: samme 472 nøgler i begge sprog, samme `{pladsholdere}` pr. nøgle i begge, og ingen ubrugte nøgler (seks spekulative blev fjernet igen, heriblandt `error.*` til den bevidst uoversatte `ErrorBoundary`).

Berørte filer: `frontend/src/pages/TvShows.jsx`, `frontend/src/pages/Settings.jsx`, `frontend/src/pages/Statistics.jsx`, `frontend/src/pages/PrintList.jsx`, `frontend/src/pages/Cinema.jsx`, `frontend/src/pages/CinemaPublic.jsx`, `frontend/src/components/CinemaShowcase.jsx`, `frontend/src/components/ScreeningRequestButton.jsx`, `frontend/src/scanner/BarcodeScanner.jsx`, `frontend/src/utils/cinemaFormat.js`, `frontend/src/App.jsx`, `frontend/src/i18n/I18nProvider.jsx`, `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `frontend/index.html`, `ARCHITECTURE.md`, `TECH_REFERENCE.md`, `FEATURES.md`, `version.json`.

## [0.66.0 build 0094] — 2026-08-08 — feature: Film-siden og scan/tilføj-panelet oversat (FEATURES.md #89, del 2/4)

Filmbiblioteket, dets detalje-/redigeringsvindue, samlings-sektionen, Plex-badget og hele scan/søg-panelet kører nu gennem oversætteren. Omkring 180 strenge.

To ting krævede mere end en tekst-udskiftning:

`SORT_OPTIONS` og `VISIBLE_FIELD_OPTIONS` er modul-konstanter, der evalueres én gang ved import — længe før nogen oversætter findes. De bærer derfor `labelKey` i stedet for en færdig `label`, og nøglen slås først op ved render. Felt-nøglerne ligger i et fælles `field.*`-navnerum, fordi Film- og TV-siden viser præcis de samme feltnavne; ellers ville "Medietype" skulle vedligeholdes to steder og kunne nå at drive fra hinanden.

Datoformatering brugte hardkodet `toLocaleDateString("da-DK")`. Den læser nu locale fra sproget via en ny `useLocale()`. Engelsk mapper til `en-GB`, ikke `en-US`: en dansk bruger der slår over på engelsk forventer stadig dag-før-måned, ikke amerikansk datoformat.

`i18n/index.jsx` er delt i `index.js` (hooks, konstanter, oversætter — ingen JSX) og `I18nProvider.jsx` (kun komponenten). En fil der blander komponenter og ikke-komponenter kan Vites fast refresh ikke opdatere uden at genindlæse hele siden; samme grund som `usePlexAvailability.js` blev skilt ud i feature #88.

Berørte filer: `frontend/src/i18n/index.js` (omdøbt fra index.jsx), `frontend/src/i18n/I18nProvider.jsx` (ny), `frontend/src/i18n/da.json`, `frontend/src/i18n/en.json`, `frontend/src/App.jsx`, `frontend/src/pages/Library.jsx`, `frontend/src/components/MovieLookupForm.jsx`, `frontend/src/components/PlexAvailability.jsx`, `version.json`.

## [0.66.0 build 0093] — 2026-08-08 — feature: i18n-motor + sprogvalg, første sider oversat (FEATURES.md #89, del 1/4)

Første del af sprogvalget: motoren, indstillingen og de skærme der ikke kræver de tre store sider. Resten af brugerfladen følger i de næste commits — featuren står som `in-progress` indtil alt er dækket.

`src/i18n/` er ~60 linjer egen kode frem for react-i18next (Jans valg blandt tre forelagte muligheder). To sprog, ingen lazy-loading af sprogfiler og kun "én/flere"-flertal retfærdiggør ikke 40 kB ekstra i en bundle der allerede advarer om sin størrelse. Nøglerne er flade og punktum-adskilte (`"app.nav.movies"`), ikke indlejrede objekter — så en nøgle man har foran sig i JSX kan søges direkte i sprogfilen som præcis den streng.

Dansk er kildesproget og dermed også fallback: en nøgle der endnu ikke er oversat viser dansk tekst i stedet for en rå nøgle midt i brugerfladen. Findes nøglen slet ikke i noget katalog, vises nøglen selv — grimt med vilje, så en manglende oversættelse er til at få øje på frem for at gemme sig som tom tekst.

Sproget gemmes i `UserSettings.language` (`da`/`en`, valideret i backend), ikke i browseren. Jans valg: det skal følge med mellem iPhone og PC frem for at skulle vælges forfra på hver enhed. Konsekvensen er at de to skærme uden en indlogget bruger — login og den offentlige `/bio` — bliver på dansk; der er ingen bruger at læse sproget fra på det tidspunkt.

`ErrorBoundary` er bevidst ikke oversat. Den ligger uden om `I18nProvider` i main.jsx — den skal netop kunne fange en fejl i selve App/provideren — så der er hverken en context at læse sproget fra eller nogen garanti for at brugerens indstillinger nåede at blive hentet. En hardkodet dansk besked er ærligere end at gætte sproget i det ene tilfælde hvor alt andet er gået galt.

Oversat i denne omgang: app-header/navigation, login, "afventer godkendelse", ønskeliste-fanerne og paginering. Sprogvælgeren ligger under Indstillinger → Konto ved siden af kortstørrelse, da begge er personlige præferencer og ikke system-indstillinger.

Berørte filer: `frontend/src/i18n/index.jsx` (ny), `frontend/src/i18n/da.json` (ny), `frontend/src/i18n/en.json` (ny), `frontend/src/App.jsx`, `frontend/src/pages/Login.jsx`, `frontend/src/pages/PendingApproval.jsx`, `frontend/src/pages/Wishlist.jsx`, `frontend/src/pages/Settings.jsx`, `frontend/src/components/Pagination.jsx`, `frontend/src/components/ErrorBoundary.jsx`, `backend/app/models/user.py`, `backend/tests/test_auth.py`, `FEATURES.md`, `version.json`.

## [0.65.0 build 0092] — 2026-08-08 — feature: portalen kontrollerer selv Plex, badge på kortene (FEATURES.md #88)

Feature #45's "Tjek Plex"-knap er væk. Den sad i detaljevinduet, skulle trykkes pr. film, og svarede kun på den ene film man stod i. Jans ønske: portalen skal selv vide det, og det skal være et badge man kan tilvælge under "Vis felter".

Det er ikke bare en flytning af knappen. #45 slog op via `/search?query=<titel>` — ét HTTP-kald pr. film. Et badge på hvert kort ville med den fremgangsmåde koste 50 Plex-kald pr. biblioteksside. `plex_client` henter derfor nu hele Plex-bibliotekets index i ét hug (`/` for server-info, `/library/sections`, og `/library/sections/{key}/all?includeGuids=1` sidevist pr. sektion), og `plex_service` cacher det i hukommelsen (`PLEX_CACHE_TTL_SECONDS`, default 300) og matcher vores egne dokumenter lokalt. Én asyncio-lås om hentningen, så to faner der åbnes samtidig ikke starter hver sit fulde hent.

Matchningen sker i faldende sikkerhed, og hvilken regel der ramte følger med i svarets `matched_by`: TMDb-id → normaliseret titel+år (±1 år, da Plex ofte følger den lokale udgivelse hvor TMDb bruger premieren) → normaliseret titel alene, men kun når den er entydig i Plex. To film der begge hedder "Batman" giver bevidst intet match frem for et tilfældigt af dem — et forkert badge er værre end intet badge. Film og TV-serier matches aldrig på tværs af hinanden.

GUID-læsningen håndterer nu både nyere agenters `Guid`-liste (`tmdb://603`) og ældre agenters enkelte `guid`-streng (`com.plexapp.agents.imdb://tt0133093`). #45 læste kun den første, hvilket betød at et helt bibliotek på en legacy-agent faldt tilbage på titel-matchning uden at det var synligt nogen steder.

Fejlsøgnings-panelet (Indstillinger → Nøgler, admin) er der netop for den slags. "Hvorfor har mine film ikke badges?" har fem forskellige svar — forbindelsen, token'et, en sektion der ikke blev fundet, en agent uden TMDb-id'er, eller titler der bare ikke matcher — og panelet skiller dem ad: server-navn/-version, sektions-tabel med guid-dækning pr. sektion, hvor mange af *vores* film/serier der matchede og hvordan, samt en stikprøve af de umatchede. `GET /api/plex/diagnostics` henter altid friskt uden om cachen, så en netop rettet URL/token afprøves med det samme.

Cachen ryddes automatisk når en admin ændrer en `plex_*`-indstilling. Uden det ville en rettet URL se ud til ikke at virke indtil TTL'en løb ud, hvilket er præcis det forkerte signal at give i det øjeblik.

To nye, valgfri indstillinger: `PLEX_CACHE_TTL_SECONDS` (default 300, `0` slår cachen fra) og `PLEX_VERIFY_SSL` (default `true`; sæt `false` ved `https://` mod en rå LAN-IP, da Plex' certifikater udstedes til `*.plex.direct`). Hvad der skal være på plads i selve Plex — token med biblioteksadgang, netværksadgang til port 32400, og helst "Plex Movie"/"Plex TV Series"-agenterne for TMDb-id'er — er dokumenteret i MOVIE_API_REFERENCE.md. Der skrives aldrig til Plex; integrationen er udelukkende læsende.

Badget er fra som standard (`VisibleFields.plex`), da det kun giver mening for den der faktisk har en Plex-server. "Afspil i Plex"-linket i detaljevinduet vises derimod uanset badge-indstillingen — status er alligevel hentet, og linket er det man reelt skal bruge derinde.

Sidegevinst: TV-kortets sæson-badge havde en hardkodet `bottom: 34px` — netop "ét badge højt". Et tredje badge ville skulle kende de to andres højde for ikke at lande oven i dem. Alle tre (Plex/Sæsoner/Set) sidder nu i en `.movie-badge-stack`, som løser rækkefølgen uden faste tal.

Berørte filer: `backend/app/integrations/plex_client.py`, `backend/app/services/plex_service.py`, `backend/app/models/plex.py`, `backend/app/api/plex.py` (ny), `backend/app/api/movies.py`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/models/user.py`, `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/app/services/system_settings_service.py`, `backend/tests/test_plex.py`, `backend/.env.example`, `frontend/src/components/PlexAvailability.jsx` (ny), `frontend/src/components/usePlexAvailability.js` (ny), `frontend/src/api/client.js`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/Library.css`, `frontend/src/pages/TvShows.jsx`, `frontend/src/pages/TvShows.css`, `frontend/src/pages/Settings.jsx`, `frontend/src/pages/Settings.css`, `ARCHITECTURE.md`, `MOVIE_API_REFERENCE.md`, `FEATURES.md`, `version.json`.

## [0.64.2 build 0091] — 2026-08-08 — fix: sæson-vælgeren talte om "ejerskab" på ønskelisten (BUGS.md #50)

Scanner man en TV-serie ind på ønskelisten, stod der "Vælg hvilke sæsoner du **ejer**" og "de markeres automatisk som **ejet**" — om noget man per definition ikke ejer endnu. Samme fejl i grupperings-grenen ("markeres som ejet på den eksisterende serie", "allerede ejet") og i begge knapper, som talte om "serie" hvor det var et ønske.

`MovieLookupForm` deles af bibliotekets og ønskelistens tilføj-panel og får allerede en `wishlist`-prop; sæson-panelets seks tekster var bare hardkodet til bibliotek-tilfældet. De blev skrevet i feature #53/#54, hvor ønskelisten slet ikke kunne indeholde TV-serier — det blev først muligt at nå hertil med BUGS.md #47 tidligere i dag, og fejlen fulgte med som en direkte konsekvens.

Teksterne følger nu `wishlist`: "ejer"/"ejet" → "ønsker dig"/"med i ønsket", og "serie" → "ønske" i knapperne ("Tilføj sæson(er) til eksisterende ønske", "Opret som nyt separat ønske i stedet").

Feltnavnet `seasons[].owned` er bevidst uændret. Det betyder i begge tilfælde "denne udgave dækker sæsonen", og en omdøbning ville kræve datamigrering uden at gøre koden klarere. Kun det brugeren læser er ændret — ingen ændring af data eller adfærd.

Berørte filer: `frontend/src/components/MovieLookupForm.jsx`, `BUGS.md`, `version.json`.

## [0.64.1 build 0090] — 2026-08-08 — fix: print satte ikke film og TV-serier på hver sin side (BUGS.md #49)

Hensigten var der allerede: `.print-section-break { break-before: page; }` sad på "TV-serier"-overskriften. Den havde bare aldrig nogen effekt, fordi `.app` er en `display: flex`-column og `.app-main` dermed et flex-item — browsere fragmenterer ikke pålideligt inde i flex-layout, så et sideskift længere nede i træet ignoreres. Reglen sad desuden på en `<h2>` midt i et fælles fragment frem for på et selvstændigt blok-element.

`@media print` sætter nu `.app`/`.app-main`/`.print-page` til `display: block`, så kæden ned til sideskiftet er almindelig blok-layout. Film og TV-serier pakkes hver i sin `<section className="print-section">`, og sideskiftet flyttes til `.print-page-break` på TV-sektionen. Er film-listen tom (fx efter en søgning der kun rammer serier), sættes sideskiftet ikke — ellers ville udskriften starte med en blank side.

Både `break-before: page` og det forældede `page-break-before: always` sættes. Safari er browseren på den iPhone appen primært bruges fra, og honorerer fortsat de gamle egenskaber mere pålideligt end de moderne.

Samtidig to ting der først mærkes når en liste fylder mere end én side: kolonne-overskrifterne gentages nu øverst på hver side (`thead { display: table-header-group }`), og en enkelt række knækkes ikke længere midt over ved et sideskift.

Ikke verificeret på papir/PDF her — ændringen er ren print-CSS, som ikke kan efterprøves fra terminalen. Jan bedes tjekke med browserens print-forhåndsvisning.

Berørte filer: `frontend/src/pages/PrintList.jsx`, `frontend/src/pages/PrintList.css`, `BUGS.md`, `version.json`.

## [0.64.0 build 0089] — 2026-08-08 — feature: kompakt redigerings-/detaljevindue (FEATURES.md #87)

Film- og TV-vinduet var en lodret stak af ti enkeltfelter, hvor de fleste kun rummede en dropdown eller et tal — meget scroll for meget lidt indhold. Korte felter parres nu to og to i en `.modal-field-row` (CSS grid): Serienummer+Set-status, Lokation+Ejer, Format+Medietype, Din rating+Registreret af.

De felter der reelt bruger bredden — Tags med sin chip-liste, Lyd-type-chips og Din note — står fortsat alene og er flyttet ned under parrene, så det korte og faste samles øverst og det lange ligger samlet nedenunder. "Registreret af" var før en løs `<p class="muted">`-linje midt i stakken; den er nu et rigtigt felt med label, hvilket både giver rating en sidemakker og gør vinduet mere ensartet.

Ændringen er lavet i *begge* grene af vinduet — redigerings-udgaven og guest-rollens read-only-udgave. De to render den samme felt-liste hver for sig, så en ændring kun ét sted ville have ladet dem drive fra hinanden.

Under 560px falder rækkerne tilbage til én kolonne: to kolonner på en telefon ville presse dropdowns og datofelter sammen, og appens primære brug er netop en installeret iPhone-PWA. `align-items: start` sikrer at et felt med hjælpetekst under sig (serienummerets "bytter automatisk plads"-note) ikke strækker sin sidemakker.

Berørte filer: `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/pages/Library.css`, `FEATURES.md`, `version.json`.

## [0.63.0 build 0088] — 2026-08-08 — feature: nulstil + tydelig markering af Sortér/Filtrér/Vis felter (FEATURES.md #86)

Jans problem: "det er svært at se om der er tilvalgt noget på de tre funktioner". Man skulle åbne hvert panel for at finde ud af om noget var valgt — kun "Filtrér" viste et tal, og selv det var forkert.

De tre værktøjslinje-knapper i film- og TV-sektionen markeres nu når deres panel afviger fra standard: accent-farvet knap (`.btn-modified`) plus `(N)` for antal aktive filtre og `●` for ændret sortering/felt-visning. Både farve og tekst, så markeringen ikke afhænger af at kunne skelne farver, og `title`-teksten forklarer hvad markeringen betyder.

Hvert panel har fået sin egen nulstillings-knap i en fast knap-række nederst — "Nulstil sortering", "Ryd filtre", "Nulstil viste felter". De står der altid og er *deaktiveret* når der ikke er noget at nulstille, i stedet for at dukke op og forsvinde: en knap der kun er synlig når den kan bruges, hjælper kun den der allerede ved at den findes. Sortering og felt-visning er persisterede bruger-indstillinger, så nulstilling gemmes med samme `persistSettings`-vej som en almindelig ændring (og fejler den, vises fejlen — BUGS.md #45's mønster).

Standardværdierne ligger nu ét sted pr. side (`DEFAULT_SORT_LEVELS`/`DEFAULT_VISIBLE_FIELDS`), som både `visibleFieldsFromSettings`, markeringen og nulstillingen læser fra. Før var defaults spredt som `?? true`/`?? false`-fallbacks inde i én funktion, hvilket ville lade en "nulstil"-knap og en "er den ændret?"-test drive fra hinanden ved næste ændring.

Sidegevinst: film-sidens filter-tæller talte ikke person-filteret (feature #41) med, selvom `hasActiveFilters` gjorde. Et rent skuespiller-/instruktør-filter viste derfor "Filtrér (0)". Tælleren er nu den samme værdi som afgør om der overhovedet er filtre aktive.

Berørte filer: `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/pages/Library.css`, `FEATURES.md`, `version.json`.

## [0.62.1 build 0087] — 2026-08-08 — fix: fritekst-søgningen ramte ikke skuespiller/instruktør/genre (BUGS.md #48)

Man kunne kun afgrænse på en person ved at åbne en films detaljevindue og trykke på et navn (feature #41's `?cast=`/`?director=`). Skrev man navnet i søgefeltet, fandt det ingenting — `?q=` gik gennem et Mongo-`$text`-index der kun dækkede `title`+`overview` (film) og `name`+`overview` (TV). Søgefeltets egen placeholder ("Søg på titel, skuespiller, genre...") og CLAUDE.md regel 7 har hele tiden lovet mere end implementeringen leverede.

`$text` er erstattet af et felt-eksplicit regex-match i ny `repositories/text_search.py`, delt af begge repositories. Søgeteksten splittes i ord; hvert ord skal matche mindst ét felt (film: titel, overview, cast, director, genres — TV: name, overview, cast, creators, genres), og alle ord skal matche. Det gør "pacino heat" til en søgning der finder Heat selvom navn og titel står i hver sit felt, mens "pacino" alene finder alt med ham. Regex-metategn escapes, så en søgning på "(2019)" behandles som tekst.

Sidegevinst: `$text` matcher kun hele ord, hvilket er direkte upraktisk i et felt der søger for hvert tastetryk — "Paci" gav nul resultater indtil "Pacino" stod færdigt. Delstrengs-matchet indsnævrer nu mens man skriver.

Trade-off'et er bevidst: et regex-scan er langsommere end et text-index og har ingen relevans-rangering. Biblioteket er en privat samling i hundred-/tusindtals-størrelsen, og resultaterne vises i brugerens egen valgte sortering — ikke efter score — så ingen af delene mærkes her. De nu ubrugte text-indexes droppes ved opstart (`drop_legacy_text_index`) frem for at ligge og koste skrivetid ved hver dokument-opdatering.

Søgningen var **helt utestet** før nu, og kunne ikke testes: mongomock implementerer ikke `$text` (`NotImplementedError`), så ingen test i suiten rammer `?q=` overhovedet — samme klasse blind vinkel som BUGS.md #31. Regex-varianten er testbar, og ny `test_search.py` dækker 13 tilfælde: cast, instruktør, genre, titel/overview-regression, case-insensitivitet, delstrenge, flere ord på tværs af felter, intet-match, regex-metategn, kombination med tag-filter, TV-cast, og at en tom søgning ikke filtrerer noget fra. Hele suiten: 437 passed.

Berørte filer: `backend/app/repositories/text_search.py` (ny), `backend/app/repositories/movie_repository.py`, `backend/app/repositories/tv_show_repository.py`, `backend/tests/test_search.py` (ny), `ARCHITECTURE.md`, `BUGS.md`, `version.json`.

## [0.62.0 build 0086] — 2026-08-08 — test: #85's testfil, udeladt ved en fejl i build 0085

`backend/tests/test_screening_requests.py` blev ikke staget i b0085 (`git add`-mønsteret dækkede `backend/app`, ikke `backend/tests`), så feature #85's 7 regressionstests lå kun lokalt. Ingen kode- eller adfærdsændring — filen er præcis den der blev kørt grøn før b0085.

## [0.62.0 build 0085] — 2026-08-08 — feature: besked + ønsket tidspunkt på en visnings-anmodning (FEATURES.md #85)

"🎬 Ønsk visning i Voldby BIO" sendte før anmodningen i det øjeblik man trykkede. Nu åbner knappen en lille boks med et fritekst-felt ("Gerne en fredag aften") og en valgfri dato/tid-vælger. Begge felter er valgfri: åbn boksen, tryk "Send ønske", og resultatet er bit for bit det samme dokument som før — `message`/`preferred_at` udelades helt af payloaden når de er tomme.

Begge felter gemmes på ønskerens egen entry i `requested_by[]`, ikke på anmodningen som helhed. Flere personer deler ét anmodnings-dokument pr. titel (feature #62), og de kan hver især have deres egen begrundelse og deres eget forslag — ét fælles felt ville lade den næste ønsker overskrive den forriges. `RequestedBy` fik derfor `message`/`preferred_at` med `None` som default, så dokumenter fra før #85 læses uden migration. Whitespace-only besked normaliseres til `None` i servicen, så hverken API'et eller admin-panelet skal skelne mellem to slags "tom" (CLAUDE.md regel 16).

Dedup'en i `add_requester` er bevidst uændret: den er stadig kun på `username`, så et gentaget ønske for samme titel hverken tilføjer en ekstra entry eller overskriver den første besked. UI'et har heller ingen vej dertil — knappen står som "✓ Ønsket" bagefter, nu med ens egen besked/tidspunkt vist under sig, så et ønske ikke bare bliver til et anonymt flueben. Egen entry findes på brugernavn (nyt `username`-prop), aldrig ved at gætte på listens rækkefølge.

Admins "Anmodninger"-panel viser hver ønskers besked og foreslåede tidspunkt på sin egen linje — kun for dem der faktisk skrev noget, så en anmodning uden beskeder ser ud som før. "Planlæg"-feltet forudfyldes med det tidligste foreslåede tidspunkt der stadig ligger i fremtiden (forslag i fortiden springes over, så en gammel anmodning ikke forudfylder en dato der er overstået), med en linje der siger at det bare er et forslag. Admin retter frit inden "Bekræft" — forslaget er aldrig en binding.

`DateTime24Input` er flyttet fra `Cinema.jsx` til `components/DateTime24Input.jsx`, da både ønskeren og admin nu vælger tidspunkter. Samme widget begge steder betyder samme 24-timers visning (BUGS.md #38) og samme "YYYY-MM-DDTHH:MM"-strengformat, så et forslag falder direkte ned i planlægnings-feltet uden konvertering. Ønske-boksen er sin egen modal oven på film-/serie-vinduet: `modal-footer` er en smal knap-række uden plads til en formular, og et klik i boksen stopper propagation, så det ikke bobler op og lukker det underliggende vindue.

Guest-rollen er uændret omfattet — visnings-ønsket er stadig deres ene tilladte skrivehandling, besked inklusive. ARCHITECTURE.md's guest-afsnit sagde fejlagtigt at `POST /api/screening-requests` var `require_not_guest`-beskyttet (det har været en bevidst undtagelse siden 2026-08-03); den passage er rettet til at beskrive koden som den faktisk er.

7 nye tests i `test_screening_requests.py` (besked+tidspunkt gemmes, pre-#85-payload uændret, whitespace→None, gentaget ønske bevarer første besked, hver ønsker sin egen besked, >500 tegn afvist, guest må sende besked). Hele suiten: 424 passed.

Berørte filer: `backend/app/models/screening.py`, `backend/app/services/screening_service.py`, `backend/app/repositories/screening_request_repository.py`, `backend/app/api/screening_requests.py`, `backend/tests/test_screening_requests.py`, `frontend/src/components/ScreeningRequestButton.jsx` + `.css`, `frontend/src/components/DateTime24Input.jsx` (ny), `frontend/src/pages/Cinema.jsx` + `.css`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/api/client.js`, `ARCHITECTURE.md`, `FEATURES.md`, `version.json`.

## [0.61.1 build 0084] — 2026-08-08 — fix: TV-serier forsvandt når de blev tilføjet i "Ønsker" (BUGS.md #47)

Jan rapporterede at en TV-serie tilføjet i ønske-sektionen — scannet eller indtastet — forsvandt i databasen. Serien blev rent faktisk gemt korrekt: `MovieLookupForm` søger bevidst i både TMDb's film- og TV-database (jf. BUGS.md #20), og en valgt TV-kandidat oprettes i `tv_shows` med `is_wishlist: true`. Fejlen lå udelukkende i visningen: `App.jsx` renderede kun `<Library wishlist />` for "Ønsker"-fanen, så TV-ønsket var usynligt både der (kun film) og under "TV-serier" (som filtrerer `is_wishlist != true` fra). `TvShows.jsx` havde allerede fuld `wishlist`-understøttelse — overskriften "TV-ønsker", skjult serienummer, "Ingen TV-ønsker endnu" — men blev aldrig renderet med prop'en.

Ny side `frontend/src/pages/Wishlist.jsx` med underfanerne Film / TV-serier, der renderer henholdsvis `<Library wishlist />` og `<TvShows wishlist />`. Samme opdeling som bibliotekets egne faner, frem for én blandet liste — film og TV-serier er to bevidst adskilte ressourcer (CLAUDE.md), og en fælles liste ville skulle blande to forskellige datamodeller og to sæt kort-felter.

Samme fejlklasse ramte hovedfanerne i mildere form: scanner man en TV-serie mens man står i filmbiblioteket, gemmes den under "TV-serier" uden nogen besked om hvor den blev af. `MovieLookupForm` melder nu tilbage *hvilken* type der blev gemt (`onSaved("movie" | "tv")`), og `Library`/`TvShows` viser en besked med genvej ("Det du gemte er en TV-serie — den ligger under TV-ønsker") når resultatet hører hjemme i den anden liste. Genvejen er en valgfri `onGoToTvShows`/`onGoToMovies`-prop, så `Wishlist` skifter underfane og `App.jsx` skifter hovedfane med samme komponent. Bevidst en besked frem for et automatisk fane-skift: skiftet ville rive brugeren ud af add-panelet midt i en stak scanninger.

En tredje variant af samme klasse er lukket i samme ombæring: sæson-grupperingen (feature #53) tilbød `matches[0]` fra dublet-tjekket uanset om posten var et ønske eller en bibliotekspost. Scannede man en serie man havde ønsket sig, mens man stod i TV-biblioteket, blev sæsonerne markeret som ejet på *ønsket* — som stadig ikke vises i biblioteket. Der grupperes nu kun ind i en eksisterende post af samme slags som den man er ved at oprette; findes kun den anden slags, oprettes en ny post, og dublet-banneret fortæller uændret at den anden findes.

Ingen backend- eller datamodel-ændringer — eksisterende, hidtil usynlige TV-ønsker dukker op af sig selv, da de hele tiden har ligget korrekt i `tv_shows`.

Berørte filer: `frontend/src/pages/Wishlist.jsx` (ny), `frontend/src/App.jsx`, `frontend/src/pages/Library.jsx`, `frontend/src/pages/TvShows.jsx`, `frontend/src/components/MovieLookupForm.jsx`, `BUGS.md`, `version.json`.

## [0.61.0 build 0083] — 2026-08-05 — feature: Voldby BIO som appens offentlige forside (FEATURES.md #84)

En ikke-indlogget besøgende på `/` møder nu biograf-siden — program, "Om Voldby BIO" og login/opret-badgen — i stedet for en bar login-boks. Det delte `/bio`-link og site-roden er dermed ét og samme udstillingsvindue, i stedet for to forskellige indgange hvor den ene kun viste et loginfelt.

Badgen tilpasser sig hvem der kigger: er man allerede logget ind, viser den "Åbn biblioteket →" (en `<a>` ind i appen) frem for "Log ind" — før i tiden fik en indlogget bruger på `/bio` tilbudt at logge ind igen. `user` sendes med ned til `CinemaPublic`, men siden renderer uændret med det samme uden at afvente session-tjekket; badgen opgraderer bare sig selv når `api.me()` er kommet tilbage, så det offentlige link aldrig blokerer på et auth-opslag. Den fulde login-side er flyttet til `/login` frem for at blive slettet, så den hverken bliver død kode eller efterlader appen uden en direkte login-URL.

Live-verificeret med Playwright i alle fire tilstande: udlogget `/` (landing vises, ingen bar login-boks), `/login` (fuld login-side virker stadig), indlogget `/` (appen, landet på Voldby BIO-fanen) og indlogget `/bio` ("Åbn biblioteket" vist, "Log ind" skjult, og knappen fører ind i appen).

## [0.60.0 build 0082] — 2026-08-05 — feature: "Opret bruger" i login-badgen på /bio (FEATURES.md #83)

`PublicLoginToggle` i `CinemaPublic.jsx` har fået samme to-tilstands-mønster som appens egen `Login.jsx`: badgen åbner stadig i log ind-tilstand, men et "Ingen konto? **Opret bruger**"-skift nederst i boksen veksler til registrering (og tilbage igen). En besøgende der har fået biograf-linket delt kan dermed oprette sin konto direkte fra `/bio` i stedet for først at skulle finde frem til appens forside. `autoComplete` skifter korrekt mellem `current-password`/`new-password`, og `minLength={8}` håndhæves i registreringstilstand som på forsiden.

Nye konti er uændret underlagt feature #66's admin-godkendelse — begge tilstande navigerer til `/` bagefter, hvor `App.jsx` så viser enten appen (log ind) eller "afventer godkendelse"-siden (ny konto). Derfor bevidst samme redirect i begge tilfælde frem for en særskilt kvitteringsbesked i badgen. Live-verificeret med Playwright: skift til registreringstilstand, oprettelse af en konto der ikke er systemets første lander korrekt på godkendelses-siden, og en for kort adgangskode afvises uden at forlade `/bio`.

## [0.59.1 build 0081] — 2026-08-05 — fix: 7 fund fra to-fase-gennemgangen (BUGS.md #40-#46)

Rettelser af alle syv fund fra kodekvalitets-gennemgangen samme dag. To af dem var kritiske.

**#40 — permanent admin-lockout (kritisk).** `auth_service.update_user_role`s sidste-admin-guard talte via den status-blinde `count_by_role`, som tæller ethvert dokument med `role: "admin"` uanset om kontoen kan logge ind. Feature #80 indførte `disabled`-status og den korrekt filtrerende `count_active_admins`, men opdaterede kun de nye stier (deaktivér/slet) — rolle-nedgraderingen blev tilbage på den gamle tælling. Ét admin-dokument der ikke kan logge ind var derfor nok til at guarden troede der var en reserve, så den sidste *brugbare* admin kunne nedgraderes; derefter kunne ingen tilgå admin-endpoints, og `register`s bootstrap kræver at `users` er helt tom, så adgangen kunne kun genskabes ved manuel database-indgriben. Reproduceret i gennemgangen: HTTP 200, aktive admins 1→0, efterfølgende `GET /api/users` → 403 for alle. Delvis regression af BUGS.md #4. `count_by_role` er fjernet helt, ikke bare taget ud af brug.

**#41 — tom restore-payload slettede hele databasen (kritisk).** Alle collection-felter på `SystemBackup` har `default_factory=list`, så en afkortet, beskadiget eller forkert valgt fil passerede validering med tomme lister — og da restore er delete-alt-så-indsæt, blev `movies`, `tv_shows`, `deleted_*`, `tags`, `users` og `counters` tømt permanent, med 200 OK og nul-tællere som kvittering. Ny `_assert_restorable` kører før den første sletning og afviser (HTTP 400 via ny `InvalidBackupError`) enhver payload uden mindst én aktiv admin — invariantet dækker både den helt tomme fil og en `users`-liste med kun inaktive konti. Et tomt *bibliotek* er stadig lovligt at gendanne.

**#42** — `create_screening` oprettede visningen før den validerede `request_id`, så en forældet anmodnings-id gav 404 *efter* at visningen allerede lå i Voldby BIO-programmet, og et nyt forsøg lavede en dublet (samme klasse som #28). Validering flyttet foran indsættelsen. **#43** — sletning af en film/serie ryddede ikke dens visninger og anmodninger op; de blev liggende og renderede som titelløse spøgelses-kort, også på den offentlige `/bio`-side. Nye `delete_for_title` i begge biograf-repositories kaldes nu fra begge slette-stier, svarende til den oprydning `reset_library` allerede lavede. **#44** — find-så-insert i `request_screening` kunne duplikere en ventende anmodning; nu et partielt unikt index (kun `status: "pending"`, så afvist historik stadig må gentages) plus `DuplicateKeyError`-håndtering. **#45** — fejlede gem af visningsindstillinger (sorteringsniveauer, navngivne presets, sidestørrelse) blev slugt af `.catch(() => {})`, så et "gemt" preset kunne forsvinde ved næste genindlæsning; begge sider viser nu fejlen. **#46** — `GET /api/movies/stats` og `/deleted` håndhæver nu guest-begrænsningen server-side, ikke kun ved at UI'et skjuler fanen.

18 nye regressionstests (`backend/tests/test_review_findings.py`), én pr. scenarie fra gennemgangens probe-tests. Fuld suite: 417 passerer.

## [0.59.0 build 0080] — 2026-08-04 — feature: login lander på Voldby BIO + login på public bio-side (FEATURES.md #82)

`App.jsx`s standard-fane er ændret fra "library" til "cinema" — gælder både et frisk login og en genindlæst side med en allerede gyldig session-cookie, da begge ender i samme kodesti. Den offentlige, ikke-autentificerede `/bio`-side (feature #70) har desuden fået en ny `PublicLoginToggle`-komponent: en "Log ind"-knap i hero-headeren der åbner en let inline login-formular (kun login, intet register-flow — den fulde tilmelding sker stadig via appens normale "/" -side). Et vellykket login kalder `window.location.assign("/")` (en rigtig navigation, ikke et internt state-skift — appen har ingen router og bruger allerede en ren pathname-check for `/bio`), som lader `App.jsx` tage over med den nu autentificerede bruger, og lander samme sted som al anden login: Voldby BIO. Live-verificeret med Playwright (frisk login, genindlæst session, forkert/korrekt login fra `/bio`, samt mobilviewport for at bekræfte login-panelet ikke overlapper indhold).

## [0.58.0 build 0079] — 2026-08-04 — feature: redigerbart titel-gæt ved scan (FEATURES.md #81)

"Søg manuelt"-feltet i scan-panelet (`MovieLookupForm.jsx`) forudfyldes nu automatisk med stregkode-opslagets `guessed_title` efter hvert scan/manuelt stregkode-opslag — uanset om det gav TMDb-kandidater eller ej. Giver TMDb nul kandidater, vises en tydelig banner der forklarer at kilden kan have leveret let forkert/ufuldstændig tekst, og peger på feltet nedenfor. Brugeren kan rette teksten direkte (fx indsætte et manglende bogstav) og trykke "Søg" for at prøve igen — genbruger det eksisterende manuelle søge-flow i stedet for ny UI. Komplementær til BUGS.md #39's automatiske støj-oprydning: dækker de tilfælde (ægte tredjeparts-datakorruption, fx et enkelt manglende bogstav fra EAN-Search.org) som ingen automatisk regel kan gætte sig til at rette. Live-verificeret med Playwright (forudfyldning, banner, korrigeret søgning finder det rigtige resultat).

## [0.57.2 build 0078] — 2026-08-04 — fix: stregkode-titel-støj gav 0 TMDb-kandidater trods vellykket opslag (BUGS.md #39)

Jan rapporterede konstante "ikke fundet"-fejl ved scanning, selvom samme titel slog op uden problemer direkte hos EAN-Search.org. Dyb analyse af produktions-logs viste at selve barcode→titel-opslaget havde 100% succesrate, men 75% af de fundne titel-gæt gav **nul** TMDb-kandidater fordi teksten indeholdt distributør-præfikser og afsluttende disk-/sæson-indeks-numre som TMDb's rene nøgleords-søgning ikke kunne matche igennem (fx "Simply HE The Americans - 6" → 0 kandidater).

To rettelser: `text_cleanup.clean_bracketed_title` fjerner nu en afsluttende `" - <tal>"`/`" – <tal>"` (bevidst afgrænset mod ægte titler som "Blade Runner 2049"/"Kill Bill - Vol. 1"), og en ny `scan_service._search_tmdb_with_fallback` prøver progressivt at droppe op til 3 indledende ord og søge igen hvis den fulde titel gav nul kandidater. Ét specifikt tilfælde ("rmageddon" uden det første "A") blev verificeret som ægte datakorruption hos EAN-Search.org selv, ikke rettbar automatisk — se FEATURES.md #81 for det komplementære UX-fix (redigerbart titel-gæt). Filer: `backend/app/integrations/text_cleanup.py`, `backend/app/services/scan_service.py`, `backend/tests/test_text_cleanup.py`, `backend/tests/test_scan.py`.

## [0.57.1 build 0077] — 2026-08-04 — fix: 24-timers ur i Voldby BIO-planlægning (BUGS.md #38)

Voldby BIOs planlægnings-tidspunkt-felt (`<input type="datetime-local">`, 3 steder i `Cinema.jsx`) viste AM/PM i stedet for 24-timers ur ved indtastning — en browser/OS-locale-afhængig gengivelse af den native picker, som HTML ikke har nogen attribut til at tvinge til 24-timers format. Erstattet alle tre med en ny `DateTime24Input`-komponent (dato-felt + to hånd-skrevne time/minut-dropdowns, 00-23/00-59) — da vi selv skriver etiketterne, er visningen 24-timers uanset locale. Samme værdiformat bevaret, ingen backend-ændring.

## [0.57.0 build 0076] — 2026-08-04 — feature: deaktivér/genaktivér + slet bruger (#80)

Indstillinger → Brugere kan nu **deaktivere** en aktiv bruger (ny `disabled`-status, blokerer login/API præcis som `pending`/`rejected`, men med en tydelig anden fejlbesked så det ikke forveksles med en afvist registrering) og senere **genaktivere** dem — samt **slette** en bruger permanent (ingen soft-delete/arkiv; `registered_by`/`owner`/audit-log gemmer kun brugernavnet som tekst, så intet forældreløses).

Lockout-beskyttelse (CLAUDE.md regel 16) på begge handlinger: kan ikke deaktivere/slette sin egen konto (skal bruge en anden admin-konto), og kan ikke deaktivere/slette den sidste tilbageværende *aktive* admin (`user_repository.count_active_admins`, adskilt fra den eksisterende rolle-nedgraderings-beskyttelse som talte alle admin-roller uanset status). `PATCH /api/users/{id}/status` udvidet med en eksplicit overgangstabel (`auth_service._VALID_STATUS_TRANSITIONS`) i stedet for den tidligere "kun pending"-begrænsning — samme sikkerhed, bredere anvendelse. Ny `DELETE /api/users/{id}`-endpoint. Begge handlinger audit-logges.

## [0.56.0 build 0075] — 2026-08-04 — feature: scan → rediger-boks (#79), Indstillinger-undermenu (#78), stregkode-kilde-statistik + primær-kilde-valg (#77)

**Scan → rediger-boks (#79)**: efter valg af en TMDb-kandidat under scan/søgning springes der nu til den samme rige rediger-boks som ved redigering af et eksisterende bibliotekskort (`MovieDetailModal`/`TvShowDetailModal`, genbrugt as-is via nye `export`s), i stedet for det tidligere begrænsede inline-felt-sæt (kun tags/format/lyd/medietype/lokation/ejer). Intet gemmes i databasen før brugeren selv trykker "Opret" i boksen — to nye read-only preview-endpoints (`GET /api/movies/tmdb-preview/{id}`, `GET /api/tv-shows/tmdb-full-preview/{id}`) henter fulde TMDb-detaljer uden at oprette noget. Begge rediger-bokse gjort tolerante for et objekt uden `.id` ("kladde"-tilstand): Gem-knappen kalder opret i stedet for opdatér, Slet/Flyt/Plex/Kollektion-sektionerne skjules, og sæson-valget for nye TV-serier sker stadig i det eksisterende trin før boksen åbnes.

**Indstillinger-undermenu (#78)**: de 14 sektioner er nu opdelt i 6 kategoriserede faner (Brugere, Konto, Bibliotek, Backup & gendannelse, Eksterne API-nøgler, Drift) i stedet for én lang scroll. **"Brugere" står først** og er default-fanen, jf. Jans bekræftelse. Hver sektions egen rolle-gating er bevaret uændret som et ekstra sikkerhedslag.

**Stregkode-kilde-statistik + primær-kilde-valg (#77)**: Statistik-siden viser nu en ny "Stregkode-kilde"-sektion (film+TV) over hvilken af de fire kilder der oftest resolver et scan — kun film/serier tilføjet via et ægte scan tæller med, et nyt `barcode_source`-felt sat ved oprettelse. Ny admin-indstilling "Primær stregkode-kilde" i System-indstillinger lader Jan vælge hvilken kilde der prøves *først* ved scan (resten følger som fallback i deres normale rækkefølge) — `scan_service._lookup_title` omskrevet til at slå kilder op via modul-reference (ikke en fastfrosset funktionsreference — samme fejlklasse som allerede rettet i `system_settings_service` under #75).

## [0.55.1 build 0074] — 2026-08-04 — fix: Audit-log fik rigtig paginering (10/side) + tydelig dato+tid

Jan bad om at Audit-log-sektionen (feature #65) skulle vise 10 elementer pr. side i stedet for den akkumulerende "Vis flere (X/Y)"-knap (som lastede 50 ad gangen), og have dato og tid tydeligt med. `AuditLogSection` bruger nu rigtig side-for-side paginering (Forrige/Næste + "Side X af Y"), `AUDIT_PAGE_SIZE` sat til 10, og hver linje viser nu dato og klokketid som to separate, tydelige dele i stedet for én sammensat `toLocaleString`-streng. Ingen backend-ændring — `GET /api/audit-log`s eksisterende `?skip=&limit=` dækkede allerede dette.

## [0.55.0 build 0073] — 2026-08-04 — feature: EAN-Search.org-fallback (#76) + "Test forbindelse" (#75) + fjernet dødt UPC-felt + fix (BUGS.md #37)

Jan flaggede at hans UPCDatabase-nøgle "gemtes gentagne gange med samme dårlige resultat" og at der generelt mangler gennemsigtighed i hvad der virker. Undersøgelse via produktions-database viste at nøglen aldrig var gemt under det rigtige felt — den var højst sandsynligt gentagne gange indtastet i **"UPC API-nøgle"** i stedet for **"UPCDatabase-token"**. Videre undersøgelse afslørede at "UPC API-nøgle" reelt **aldrig blev brugt af nogen aktiv integration** (UPCitemdb's gratis trial-tier kræver ingen nøgle) — feltet er fjernet helt efter Jans bekræftelse.

For at løse gennemsigtigheds-problemet varigt: ny **"Test forbindelse"**-knap ved hver af de fem resterende eksterne nøgler (TMDb, Discogs, UPCDatabase, EAN-Search, OMDb) i Indstillinger → System-indstillinger. Laver et rigtigt, minimalt testkald mod den aktuelt aktive nøgle og viser om den faktisk virker — ny `POST /api/settings/system/test/{key}`-endpoint (admin-only), hver integrations-klient ejer sin egen `test_connection()`.

Samtidig tilføjet **EAN-Search.org** som fjerde og sidste stregkode-opslags-fallback (efter UPCitemdb, Discogs, UPCDatabase.org) — Jans egen betalte konto, købt i håb om bedre dansk/nordisk EAN-dækning.

**BUGS.md #37** (fundet under arbejdet): `upcdatabase_client.py` behandlede et ugyldigt token identisk med et ægte "intet match" (begge giver HTTP 200 med `success: false`) — kun et ekstra `error.apikey`-felt i svaret skelner dem. Rettet, og samme skelnen bygget ind i den nye `ean_search_client.py` fra starten.

## [0.54.2 build 0072] — 2026-08-03 — fix: "Opdatér fra GitHub" viste fejl selv når intet var galt (BUGS.md #36)

Jan ramte en alarmerende "Kunne ikke bekræfte at opdateringen er fuldført endnu"-besked ved et klik hvor produktionen allerede var opdateret. Rodårsag: `deploy.sh` kørte altid hele pipelinen uanset om `git pull` fandt noget nyt, og frontend'ens eneste succes-kriterie var at `/api/health`s build-nummer ændrede sig — hvilket det aldrig gør når der intet nyt er at hente, så pollingen ramte garanteret timeout.

`deploy.sh` sammenligner nu commit-hash før/efter `git pull` og springer pip/npm/restart helt over hvis identisk (undgår unødig nedetid), og skriver udfaldet til en ny `.deploy-status`-fil. Ny `GET /api/system/deploy/status`-endpoint (admin-only) læser den. `Settings.jsx`s deploy-sektion viser nu straks en tydelig "Allerede opdateret"-besked i stedet for at vente to minutter på en fejlbanner. **Kræver at den opdaterede `deploy.sh` manuelt kopieres til `/opt/moviedb-deploy.sh` i produktion** — afventer Jans bekræftelse.

## [0.54.1 build 0071] — 2026-08-03 — fix (afventer endelig bekræftelse): ægte rodårsag til sort skærm på iOS fundet og rettet (BUGS.md #35)

Jan testede build 0069's fix live og bekræftede at problemet var uændret — den første teori (WebKit-compositing-lag) var forkert og rettede aldrig den faktiske fejl. Ny undersøgelse fandt den ægte rodårsag ved at læse `@zxing/browser`s (v0.2.1) kildekode direkte: `BarcodeScanner.jsx`s unmount-cleanup kaldte `readerRef.current?.stopContinuousDecode()` — en metode der **slet ikke findes** i denne version af biblioteket. Den valgfri-kædning beskyttede kun mod `readerRef.current` selv værende null, ikke mod at kalde en ikke-eksisterende metode — så linjen kastede en `TypeError` ved hver eneste afmontering af scanneren, herunder præcis når "Gem" lukker tilføj-panelet. Uden nogen error boundary i appen fik denne ufangede fejl hele siden til at gå blank, uden vej tilbage undtagen manuel reload.

Rettet ved roden: `BarcodeScanner.jsx` bruger nu en `controlsRef` (den reelle `IScannerControls` fra `decodeFromVideoDevice()`) og kalder `controlsRef.current?.stop()` i stedet for den opdigtede metode. Tilføjet en ny `ErrorBoundary`-komponent omkring hele appen (`main.jsx`) som sikkerhedsnet mod fremtidige ufangede render-fejl. **Reproduceret og verificeret denne gang** (ikke kun teori) — Playwright med en simuleret kamera-enhed genskabte præcis krasch-sekvensen: den gamle kode kastede den eksakte fejl hver gang, den nye kode kaster intet. Afventer stadig Jans endelige bekræftelse på en rigtig iPhone.

## [0.54.0 build 0070] — 2026-08-03 — feature: TLS-certifikat-styring i Indstillinger (#73)

Ny admin-only "TLS-certifikat"-sektion på Indstillinger-siden til at forny produktionens `movie.ll.lan`-certifikat (se BUGS.md #23/DEPLOYMENT.md) uden manuel SSH-adgang. To metoder: (1) generér en ECDSA P-256-nøgle + CSR til ekstern signering (fx Jans interne AD CS) og indsæt det signerede certifikat bagefter, eller (2) importér en færdig PKCS12 (.pfx/.p12 med cert+nøgle). Begge veje verificerer at certifikatets offentlige nøgle matcher den ventende private nøgle før noget lægges klar ("staged"). En separat "Installér nu"-knap (kræver eget password, samme mønster som #67's database-reset) udløser den faktiske installation.

Genbruger det ikke-sudo-trigger-mønster fra OTA-deploy (feature #20/BUGS.md #18): `moviedb-backend` kan hverken sudo'e eller skrive til `/etc/caddy/certs/`, så den lægger cert+nøgle i en staging-mappe indenfor egne `ReadWritePaths` og rører en trigger-fil — en ny, separat, root-ejet systemd path-unit (`scripts/moviedb-cert-install.{path,service}` + `scripts/cert-install.sh`, mirrorer `moviedb-deploy-restart.*`) reagerer på den, tager en `.bak`-backup af det eksisterende certifikat, installerer det nye med korrekt ejerskab/rettigheder, validerer Caddy-config og genindlæser først ved success. Disse nye systemd-units er **klar i repoet men endnu ikke installeret på produktionsserveren** — kræver Jans eksplicitte godkendelse før SSH-udførelse (se DEPLOYMENT.md).

Backend: `backend/app/models/cert.py`, `backend/app/services/cert_service.py` (ny, bruger `cryptography`-biblioteket til CSR/X.509/PKCS12 — ingen `openssl`-subprocess), 5 nye endpoints under `/api/system/cert*` (`app/api/system.py`), 4 nye fejltyper (`app/core/errors.py`), nye settings-felter (`app/core/config.py`), `cryptography>=42.0` tilføjet til `requirements.txt`. Frontend: `TlsCertSection` i `Settings.jsx`, 5 nye `client.js`-funktioner. 13 nye backend-tests (`test_tls_cert.py`), fuld live-verifikation af hele UI-flowet (CSR-generering, fuldførelse, PKCS12-import, forkert/korrekt password ved installation) mod en rigtig kørende backend/frontend.

## [0.53.5 build 0069] — 2026-08-03 — fix (afventer bekræftelse): sort skærm på iOS ved gem (BUGS.md #35)

Jan rapporterede at skærmen bliver helt sort på en iOS-enhed ved oprettelse af en film og tryk på Gem. Mistanke om et kendt WebKit-kompatibilitetsproblem: `BarcodeScanner.jsx` stoppede tidligere kun selve stregkode-afkodningen (zxing-bibliotekets `controls.stop()`/`stopContinuousDecode()`), men overlod `<video>`-elementets `MediaStream`/hardware-compositing-lag til browseren — kan på visse WebKit-versioner efterlade et fastfrosset/sort lag der breder sig til hele siden, ikke kun kamera-boksen, når komponenten afmonteres/genrenderes (fx når "Gem" lukker tilføj-panelet).

Ny `releaseCamera()`-hjælpefunktion stopper nu eksplicit alle `MediaStream`-tracks, nulstiller `video.srcObject` og kalder `video.load()` — både når en stregkode findes, og ved afmontering. **Kan ikke reproduceres/verificeres fra udviklingsmiljøet** (kræver en fysisk iOS-enhed) — status forbliver "afventer bekræftelse" i BUGS.md #35 indtil Jan har testet på sin iPhone efter deploy.

## [0.53.4 build 0068] — 2026-08-03 — fix: tydeligere logging af stregkode-opslag (BUGS.md #34)

Jan rapporterede at alle 10-15 nyligt scannede stregkoder fejlede opslag. Produktions-log-undersøgelse afslørede at UPCDatabase.org (feature #69) aldrig blev kaldt — `UPCDATABASE_TOKEN` var kun sat i udviklerens lokale `.env`, aldrig deployet til produktion (`.env` er git-ignoreret, deployes ikke via `git pull`). Samtidig var "intet match"-udfald slet ikke logget eksplicit i nogen af de tre kilder, kun selve HTTP-kaldet.

Tilføjet eksplicit logging (`logger.info`/`logger.warning`) i `upc_client`, `discogs_client`, `upcdatabase_client` for "intet match"/"intet token", samt en opsummerende advarsel i `scan_service.lookup_by_barcode` når alle tre kilder er udtømt uden gæt. Selve nøgle-manglen kræver at Jan selv indsætter den via Indstillinger → System-indstillinger (admin-override, ingen genstart nødvendig).

## [0.53.3 build 0067] — 2026-08-03 — fix: Voldby BIO-side polish + guest-rolle-justeringer (feature #70/#71/#72)

**Voldby BIO offentlig side**: dato+tid-badge flyttet fra et overlay nederst på plakaten til et normalt element ovenover (Jans ønske: "dato skal stå over film"). Hero-banneret har fået en farverig gradient-baggrund (`--accent`/`--accent-strong`) og en større, federe overskrift — var for fladt/farveløst før.

**Guest-rolle rettelser og udvidelse**:
- **Bugfix**: `AccountSection` viste altid "Standard" for en guest-bruger (samme binære `admin ? "Admin" : "Standard"`-mønster jeg allerede havde rettet i `UsersSection`, men overså her) — viser nu korrekt "Guest".
- Indstillinger skjuler nu også "Serienummer-opsætning" og "Slettede film" for guest (rører kun film-/TV-data en guest ikke må redigere alligevel).
- **Udvidet**: guest må nu sende en "🎬 Ønsk visning i Voldby BIO"-anmodning for en titel i biblioteket — det ene skrive-endpoint der er tilladt for den ellers read-only rolle (Jans eksplicitte valg 2026-08-03). `POST /api/screening-requests` bruger igen almindelig `get_current_user` i stedet for `require_not_guest`; detaljevinduets read-only footer viser nu kun denne ene knap for guest.

Backend-test opdateret (guest kan nu anmode, ikke længere blokeret). Live-verificeret.

## [0.53.2 build 0066] — 2026-08-03 — fix: Voldby BIO offentlig side — sideom-side-gitter + sektionsrækkefølge (feature #70/#71)

Endnu en runde Jan-feedback på den offentlige `/bio`-side: "Om Voldby BIO" flyttet tilbage øverst (over programmet igen), og programmets datogruppering fjernet — med typisk én visning pr. dag gav det en lang, næsten tom kolonne af enkeltstående kort. Alle kommende visninger vises nu i ét fladt side-om-side gitter (samme `movie-grid`-poster-stil som resten af appen), hver med en dato+tid-badge nederst på plakaten i stedet for en fælles dags-overskrift.

## [0.53.1 build 0065] — 2026-08-03 — fix: Voldby BIO offentlig side prioriterer programmet (feature #70/#71)

Jans feedback efter at have set den offentlige `/bio`-side: for lidt fyldt ud, og "hvad går i bio" skulle frem. Omstruktureret: en stor, tydelig "🎬 Voldby BIO"-hero-overskrift øverst (i stedet for en lille header-bjælke), programmet ("Hvad går i bio") flyttet op som første sektion, showcase-sektionen (billeder/specs) flyttet ned under en ny "Om Voldby BIO"-overskrift.

## [0.53.0 build 0064] — 2026-08-03 — Automatisk "Tilføjet af {bruger}"-tag (feature #18)

Enhver ny film/TV-serie får nu automatisk et "Tilføjet af {brugernavn}"-tag ved oprettelse — uanset om det sker via stregkode-scan, manuel TMDb-søgning eller ren manuel indtastning, da alle tre funnel gennem samme `create_movie`/`create_tv_show`-kald. Ny delt `tag_service.added_by_tag(username)` sikrer at ordlyden ikke kan gå ud af trit mellem film og TV-serier. Udvidet til også at gælde TV-serier (ikke kun film som FEATURES.md oprindeligt sagde), for konsistens med hvordan de to ressourcer ellers deler tag-mekanismen.

Tagget går gennem samme normaliserings-/dedup-pipeline som brugerens egne tags (`tag_service.resolve_tags`) — vises i tag-autocomplete, er filtrerbart via `?tags=` ligesom alle andre tags, og er ikke specielt beskyttet (kan fjernes igen manuelt som ethvert andet tag). Tilføjes kun ved oprettelse, ikke ved efterfølgende redigering.

7 nye backend-tests + 9 eksisterende opdateret til at forvente det nye tag. Live-verificeret: tagget vises korrekt på filmkortet.

## [0.52.0 build 0063] — 2026-08-03 — Ny "guest"-rolle: read-only adgang (feature #72)

Ny tredje rolle `guest` (udover `admin`/`standard`) — kan browse/søge film-/TV-biblioteket og den offentlige Voldby BIO-side, og ændre egen adgangskode/view-indstillinger, men intet andet. Håndhævet i **backend** (ikke kun UI, jf. CLAUDE.md regel 16): ny `Depends(require_not_guest)` i `app/api/deps.py`, sat på alle skrive-endpoints for film/TV-serier (opret/redigér/slet, sæson-/episode-markering) og `POST /api/screening-requests`.

Frontend: Ønsker-/Print-/Statistik-fanerne samt "+ Tilføj film/serie"-panelerne er skjult for guest. Film-/TV-seriens redigeringsvindue viser samme information som normalt, men som en ren visnings-udgave — ingen input-felter, intet Gem/Slet, ingen "Ønsk visning i Voldby BIO"-knap, sæson-/episode-markeringer vist som deaktiverede afkrydsningsfelter. Admin tildeler rollen fra en ny rolle-dropdown (Admin/Standard/Guest) i Brugere-listen på Indstillinger, i stedet for den tidligere binære "Gør til/fjern admin"-knap.

10 nye backend-tests. Live-verificeret med Playwright: guest ser kun de 4 tilladte faner, redigeringsvinduet er fuldt skrivebeskyttet, og et direkte API-kald for at oprette en film afvises med 403.

## [0.51.0 build 0062] — 2026-08-03 — Voldby BIO: offentlig side + showcase-sektion (feature #70/#71)

Ny offentlig, login-fri side på `/bio` — en direkte, delbar URL med kun programmet (hvad går i bio, hvornår) og en ny showcase-sektion (billeder af biografrummet + lyd-/billed-specs), ingen anmodnings-/planlægnings-værktøjer. `GET /api/screenings` kræver ikke længere login (POST/PATCH/DELETE er uændret admin-only) — kun læsning blev åbnet.

Ingen router-bibliotek tilføjet: `/bio` tjekkes som et rent `window.location.pathname`-opslag i `App.jsx`, før login-tjekket overhovedet kører — eneste offentlige rute i en ellers fane-baseret app. Caddys eksisterende `try_files {path} /index.html` (se DEPLOYMENT.md) og Vites dev-server serverer allerede `index.html` for enhver ukendt sti, så et delt link virker uden yderligere server-opsætning.

Ny delt `CinemaShowcase`-komponent (billeder + specs) bruges både på den offentlige side og den eksisterende indloggede Voldby BIO-fane, som også har fået en "🔗 Del link"-knap der kopierer `/bio`-URL'en. Delt `cinemaFormat.js` (dato-/tids-formattering) udtrukket, så de to sider ikke kan gå ud af trit.

Backend-tests opdateret/udvidet (offentligt GET, skriv forbliver auth-krævende). Live-verificeret med Playwright: helt frisk, ikke-logget-ind browser-kontekst kan se programmet på `/bio` uden cookies, admin-værktøjer er ikke synlige, og "Del link"-knappen kopierer den korrekte URL.

## [0.50.0 build 0061] — 2026-08-03 — Paginering af biblioteksvisning (feature #15)

`/api/movies` og `/api/tv-shows` GET returnerede tidligere en rå liste, stille begrænset til 500 dokumenter uden nogen måde at se eller nå noget derudover — samlinger med mere end 500 film/serier ville simpelthen miste resten af visningen. Begge repositories har nu rigtig `skip`/`limit` + en delt `count_many` (samme filter-opbygning som `find_many`, kan aldrig gå ud af trit), og response-formen er ændret til `{items: [...], total: N}`.

`?page=`+`?page_size=` (begge skal angives sammen) giver en rigtig, afgrænset side; udelades de (Print-siden, Voldby BIO's søgning), hentes alt uden loft — det tidligere 500-loft er dermed fjernet permanent for alle forbrugere af endpointet, ikke kun de nye paginerede.

Nyt delt `Pagination`-komponent (Forrige/Næste + sideindikator + "pr. side"-vælger) i både Film- og TV-serie-fanen. Antal pr. side er en ny persisteret bruger-indstilling (`page_size`, delt mellem faner, samme mønster som `card_size`, feature #59) — huskes på tværs af sessioner. Skift af filter/søgning/sortering springer automatisk tilbage til side 1.

13 nye backend-tests. 26 eksisterende tests opdateret til det nye `{items, total}`-svar (inkl. et par steder der brugte `len(response.json())` — ville have talt ordbogens 2 nøgler i stedet for det faktiske antal film, uden at fejle synligt). Live-verificeret med Playwright: 30 film, sideskift, og at valgt sidestørrelse overlever en genindlæsning.

## [0.49.0 build 0060] — 2026-08-03 — "Nulstil database"-knap på Indstillinger (feature #67)

Ny admin-only "Nulstil database"-sektion på Indstillinger: tømmer film-/TV-biblioteket tilbage til tom tilstand — `movies`, `tv_shows`, `deleted_movies`, `deleted_tv_shows`, `tags`, `counters` (serienumre starter forfra ved næste oprettelse) samt Voldby BIO's `screenings`/`screening_requests` (ellers ville de pege på film/serier der ikke længere findes, Jans bekræftede valg 2026-08-03). Rører **ikke** brugerkonti eller system-indstillinger.

Bekræftes med admins egen adgangskode (nyt `auth_service.verify_current_password`, samme tjek som `change_password`) i stedet for blot en tekst-bekræftelsesfrase som backup/restore (#60/#61) — en reset er endnu mere uigenkaldelig, da der ikke er nogen backup-fil at fortryde med medmindre admin selv har taget en først. Ny `POST /api/system/reset`, ny `system_backup_service.reset_library`. Handlingen audit-logges (feature #65).

6 nye backend-tests. Live-verificeret med Playwright: forkert adgangskode afvises tydeligt, korrekt adgangskode tømmer biblioteket og viser en opsummering.

## [0.48.0 build 0059] — 2026-08-03 — Admin-godkendelse af ny bruger-registrering (feature #66)

Tilmelding var hidtil helt åben — enhver der kendte URL'en fik fuld adgang med det samme. Ny bruger får nu `status: pending` ved registrering (undtagen den allerførste bruger nogensinde, som stadig bootstrapper sig selv til `active` admin — ellers ville ingen kunne logge ind og godkende dem, jf. CLAUDE.md regel 16's lockout-princip). En `pending`-bruger kan logge ind og se sin egen status, men er blokeret fra alt andet (nyt 403 via `get_current_user`, som næsten alle endpoints allerede afhænger af); en `rejected`-bruger forbliver blokeret med en tydelig besked.

Admin godkender/afviser fra "Brugere"-listen på Indstillinger (nyt `PATCH /api/users/{id}/status`) — kun tilladt mens brugeren rent faktisk er `pending`, så et forkert klik ikke kan låse en allerede-aktiv bruger ude. Begge handlinger audit-logges (feature #65). Eksisterende brugere migreres automatisk til `status: active` ved opstart (samme mønster som `username_normalized`-migrationen).

12 nye backend-tests, heriblandt en eksplicit regressionstest for at den allerførste bruger altid bootstrapper til `active`. 5 eksisterende tests opdateret (de registrerede en "anden bruger" og forventede fuld adgang med det samme — skal nu godkendes af admin først, som er den korrekte nye adfærd). Live-verificeret med Playwright: fuldt flow fra registrering → "afventer godkendelse"-skærm → admin-godkendelse → adgang.

## [0.47.0 build 0058] — 2026-08-03 — Audit-log på Indstillinger-siden (feature #65)

Nyt admin-only "Audit-log"-afsnit på Indstillinger, med en løbende, pagineret (`?skip=&limit=`, nyeste først) log over sikkerheds-/data-relevante handlinger: rolle-ændringer, system-nøgle-opdateringer (kun feltnavne logges, aldrig værdier — CLAUDE.md regel 6), OTA-deploy, bibliotek-/system-backup og -gendannelse, samt biograf-planlægning/afvisning (Voldby BIO).

Ny `audit_log`-collection + `audit_log_repository.py`/`audit_log_service.py` (samme lag-struktur som resten af appen) og nyt `GET /api/audit-log` (admin-only, intet write-endpoint — entries skrives udelukkende som sideeffekt af de 8 instrumenterede handlinger i deres respektive routere). `audit_log_service.record()` er bevidst best-effort — samme filosofi som Plex/OMDb-integrationerne: en fejlet audit-log-skrivning må aldrig fejle den handling den logger, kun logges som en advarsel.

12 nye backend-tests (alle 8 handlinger + admin-gating + paginering + "aldrig kaster" for `record()`). Live-verificeret med Playwright at sektionen renderer korrekt i Indstillinger.

## [0.46.0 build 0057] — 2026-08-03 — Sticky gem/slet-knapper i redigeringsvindue (feature #68)

`.modal-card` scrollede tidligere som én samlet blok (`overflow-y: auto` på hele kortet) — det betød at `modal-footer`s "Gem ændringer"/"Slet"-knapper kun blev synlige efter at have scrollet forbi alle felterne i en lang film-/TV-serie-redigering. Ændret til en flex-kolonne hvor kun `.modal-body` scroller internt (`flex: 1; min-height: 0; overflow-y: auto`), mens `.modal-header` og `.modal-footer` (begge `flex-shrink: 0`) forbliver fast synlige i toppen/bunden af modalen uanset scroll-position. Gælder både `MovieDetailModal` og `TvShowDetailModal` (deler samme CSS-klasser i `Library.css`).

Live-verificeret med Playwright mod ægte backend (kort viewport der tvinger scroll): footer-knappernes bounding box er identisk før og efter scroll i begge modaler.

## [0.45.0 build 0056] — 2026-08-03 — PWA-installation på iPhone (feature #9)

`apple-touch-icon` pegede på `favicon.svg` — iOS Safari rasterizerer ikke SVG til hjemmeskærms-ikonet og faldt derfor stille tilbage til et skærmbillede af siden i stedet for et rigtigt ikon. Genereret et fuldt PNG-ikonsæt fra den eksisterende SVG-logo (`apple-touch-icon.png` 180×180, `pwa-192x192.png`, `pwa-512x512.png`, samt en maskable variant med ekstra padding til Android/Chromes cirkel-beskæring), lagt på mørk baggrund (`#0f0f0f`, matcher `theme_color`) da iOS' ikon ikke understøtter transparens. `index.html`s `apple-touch-icon`-link og `vite.config.js`s manifest-`icons`-liste opdateret til at bruge dem. Resten af PWA-grundlaget (`viewport`, `apple-mobile-web-app-capable`, service worker via `vite-plugin-pwa`, responsivt CSS) var allerede på plads.

## [0.44.0 build 0055] — 2026-08-03 — UPCDatabase.org som tredje stregkode-opslags-fallback (feature #69)

Efter at have bekræftet (BUGS.md #32) at 4 konkrete danske DVD-stregkoder manglede i både UPCitemdb og Discogs, er **UPCDatabase.org** tilføjet som et tredje, sidste fallback-forsøg i `scan_service._lookup_title` — gratis niveau, 100 opslag/dag. Ny `backend/app/integrations/upcdatabase_client.py` følger samme `lookup_title(barcode) -> str | None`-kontrakt og fejl-filosofi som UPCitemdb/Discogs (aldrig en kastet exception). I modsætning til Discogs er token her påkrævet for auth — et tomt `upcdatabase_token` springer opslaget helt over i stedet for at forsøge et kald der alligevel vil få 403.

Nøglen konfigureres som de øvrige eksterne API-nøgler (CLAUDE.md regel 6): `UPCDATABASE_TOKEN` i `.env`, eller admin-override via Indstillinger → System-indstillinger (nyt felt i `SystemSettingsStatus`/`SystemSettingsUpdate`, tilføjet til `OVERRIDABLE_KEYS`) — aldrig eksponeret til frontend, kun `configured`/`source`.

5 nye tests af `upcdatabase_client` + 1 ny scan-fallback-regressionstest + 1 ny system-settings-test. Fuld suite (276 tests) grøn.

## [0.43.0 build 0054] — 2026-08-03 — "Voldby BIO": visningsanmodninger, admin-planlægning og offentlig kalender (feature #62/#63/#64)

**Feature #62**: Ny "🎬 Ønsk visning i Voldby BIO"-knap i film-/TV-seriens detaljevindue. Nyt `screening_requests`-collection (ét dokument pr. titel, med en liste af hvem der har ønsket den — idempotent, ingen duplikater ved gentaget ønske). Nye `POST/GET /api/screening-requests`, `GET /api/screening-requests/mine`, `PATCH /api/screening-requests/{id}` (kun `declined`, admin-only).

**Feature #63**: Admin kan planlægge en anmodning (sætter dato/tid, markerer den `scheduled`) eller tilføje en visning direkte uden en forudgående anmodning (søger i det eksisterende bibliotek). Ny `screenings`-collection, fuldt adskilt fra anmodningerne (Jans valg af "Forslag 2", 2026-08-03) — titel/poster/plot/trailer hentes via reference til film-/TV-dokumentet ved visning, ikke duplikeret. Nye `GET/POST /api/screenings`, `PATCH/DELETE /api/screenings/{id}` (admin-only).

**Feature #64**: Ny "🎬 Voldby BIO"-fane, synlig for alle brugere — viser kommende planlagte visninger grupperet efter dato, i stil med en rigtig biograf-forside (poster, titel, genrer, plot, trailer-link, tidspunkt). Admin ser desuden anmodnings-kø og "tilføj direkte"-værktøjer øverst på samme side.

**BUGS.md #33** (fundet under live-verificering mod ægte MongoDB): `screening_service.update_screening` dumpede sin payload med `mode="json"`, hvilket serialiserede `scheduled_at` til en tekststreng før en rå `$set` — ødelagde feltets BSON-type, så en redigeret visning stille forsvandt fra "kommende visninger". Rettet ved at fjerne `mode="json"`. **OBS**: mongomock reproducerer ikke denne fejl-klasse (bekræftet ved manuel test) — kun den ægte MongoDB-verificering fangede den, jf. CLAUDE.md regel 16's runtime-kontekst-lektion. Samme mønster findes uafklaret i `movie_service`/`tv_show_service`s `watched_at`-felt (mindre akut, kun forkert sortering — egen fremtidig opgave med data-migration).

Live-verificeret (Playwright mod ægte MongoDB, ikke mongomock) — hele flowet: anmod → planlæg → vis på forsiden → redigér → fjern, samt admin-only-gating, på både desktop- og mobil-viewport. 20 nye backend-tests. Fuld suite (269 tests) + frontend-build grønt.

## [0.42.0 build 0053] — 2026-08-03 — Bibliotek-eksport/-gendannelse (feature #60) + fuld system-backup/restore (feature #61)

**Feature #60**: Ny "Bibliotek-eksport / -gendannelse"-sektion på Indstillinger (admin-only). "Eksportér bibliotek" henter en JSON-fil med alle film + TV-serier, ubegrænset (nye `movie_repository.find_all_raw`/`tv_show_repository.find_all_raw`, uden `find_many`s 500-dokument-cap). "Gendan" erstatter `movies`+`tv_shows`-collections wholesale med filens indhold — gated bag en bekræftelsesfrase i UI'et ("GENDAN") før knappen aktiveres. Ny `GET/POST /api/library/export`/`/import`.

**Feature #61**: Ny "Fuld system-backup"-sektion (admin-only). Dumper *alle* collections (film, TV-serier, slettede film/TV-serier, tags, brugere, tællere) som JSON. **Udelader bevidst `system_settings`** (Jans eksplicitte valg 2026-08-03) — et ægte fuldt backup ville kræve at sende de faktiske TMDb/UPC/Discogs/OMDb/Plex-nøgler til frontend, hvilket er i direkte konflikt med CLAUDE.md regel 6; en gendannelse er derfor ikke 100% komplet og kræver manuel genindtastning af nøglerne bagefter. Restore er ligeledes gated bag en bekræftelsesfrase ("GENDAN SYSTEM"). Ny `GET/POST /api/system/backup`/`/restore`.

Begge features deler en ny `app/core/mongo_json.py` — round-trippable JSON-kodning af rå MongoDB-dokumenter via en let udgave af MongoDB's egen Extended JSON-konvention (`{"$oid": ...}`/`{"$date": ...}`) i stedet for en heuristisk gætning af hvilke strenge der "ligner" datoer/ObjectIds.

Live-verificeret (Playwright) mod en isoleret throwaway-database (ikke produktions-/dev-data) — eksport, import, bekræftelsesfrase-gating, og at `system_settings` aldrig optræder i backup-responsen selv når en rigtig API-nøgle er sat. 15 nye backend-tests. Fuld suite (248 tests) + frontend-build grønt.

## [0.41.1 build 0052] — 2026-08-03 — Fix: sæson-badge sad fast forkert ved skift af kortstørrelse

- `.movie-seasons-badge` (`TvShows.css`) ændret fra centreret+fast-px-nudge (`left: 50%; transform: translateX(calc(-50% + 16px))`) til right-anchoret (`right: 8px`, samme mønster som `.movie-format-badge`/`.movie-watched-badge`) — den faste 16px-nudge var en konstant brøkdel af en *varierende* poster-bredde, så positionen så fin ud ved én kortstørrelse (feature #59) men skæv ved de andre. Stablet 26px over `.movie-watched-badge` (`bottom: 34px`) for at undgå overlap når begge badges vises samtidig. Live-verificeret (Playwright) ved alle tre kortstørrelser — ingen overlap, konsistent placering.

## [0.41.0 build 0051] — 2026-08-03 — Combobox for tags/lokation/ejer (feature #58) + valgbar kortstørrelse (feature #59)

**Feature #58**: Tags-, lokations- og ejer-felterne i tilføj-/redigeringsformularerne (scan/manuel-tilføj-panelet, film- og TV-seriens redigeringsvindue) viser nu eksisterende værdier der allerede er i brug, men tillader stadig fri indtastning af en ny værdi.
- Backend: nye `GET /api/owners`/`GET /api/locations` (nyt `attribute_service.py` + `attributes.py`-router), samlet på tværs af film og TV-serier — samme flade top-niveau-mønster som det eksisterende `/api/tags`. `movie_repository`/`tv_show_repository` fik hver et `distinct_owners`/`distinct_locations`.
- Frontend: ny genanvendelig `Combobox`-komponent (`components/Combobox.jsx`) — en selvbygget dropdown, **ikke** native `<datalist>`, da iOS Safaris `<datalist>`-understøttelse historisk er svag/inkonsistent og appens primære brug er en installeret iPhone-PWA. Lukker ved klik/tap udenfor (ikke `onBlur`, for at undgå at et tryk på et forslag konkurrerer med en blur-udløst lukning). Viser hele listen ved fokus (uanset feltets nuværende værdi) og filtrerer først når man rent faktisk taster.
- Tags genbruger den eksisterende tag-liste som klikbare forslags-chips ved siden af det fritekst-felt der allerede fandtes (chips var allerede hentet til redigeringsvinduerne, men aldrig faktisk vist der — nu bragt i brug).
- Live-verificeret i en rigtig kørende instans (Playwright mod dev-serveren) på både desktop- og mobil-viewport (390px), i tilføj- og redigeringsflowet, for både film og TV-serier.

**Feature #59**: Ny "Kortstørrelse"-sektion i Indstillinger (Lille/Mellem/Stor), én fælles indstilling for både Film- og TV-serie-fanen. Nyt `card_size`-felt på `UserSettings` (backend), ny `movie-grid--small/medium/large`-CSS-klasse (`Library.css`, genbruges af TV-serie-fanen). Live-verificeret: valget slår igennem på begge faner, overlever en fuld genindlæsning, og fungerer på mobil-viewport.

## [0.40.0 build 0050] — 2026-08-02 — Retter 8 fund fra to-fase-gennemgangen (BUGS.md #24-#31) + TMDb-synk for TV-serier (feature #57)

**Bugfixes:**
- **#24**: `TmdbRateLimitedError` manglede en `@app.exception_handler` og gav rå 500 på 4 endpoints ved TMDb rate-limit — tilføjet handler, mapper til 429.
- **#25**: Samtidige episode-afkrydsninger kunne miste hinandens skrivning (read-modify-write af hele episode-arrayet). `set_episode_watched` opdaterer nu kun det ene episode-felt atomisk via en indekseret felt-sti.
- **#26/#27**: `setSeasonOwned`/`setEpisodeWatched` i TV-detaljevinduet havde hverken fejlhåndtering eller kaldte `onChanged()` — tilføjet begge dele.
- **#28**: Feature #54's ny-serie-gem-flow kunne efterlade en halvfærdig oprettelse (dublet-risiko ved retry). `TvShowCreate` har fået et `owned_seasons`-felt, så sæson-markering nu sker i selve opret-kaldet i stedet for en efterfølgende POST-så-N-PATCH-løkke.
- **#29**: `remove()` i `Library.jsx`/`TvShows.jsx` manglede `catch` — fejlede sletning viste intet til brugeren. Tilføjet, samme mønster som `moveToLibrary()`.
- **#30**: Latent `KeyError`-risiko i `system_settings_service.update_settings` ved en fremtidig ude-af-sync nøgleliste — ændret til `.get(key, "")`.
- **#31**: Testsuiten afhang utilsigtet af udviklerens lokale `.env` (CWD-relativ indlæsning). Ny autouse-fixture i `conftest.py` pinner eksterne API-nøgler til faste testværdier — verificeret identisk resultat (233 passed) fra både `backend/` og repo-roden.

**Feature #57**: `tv_show_service.sync_all_from_tmdb` + `POST /api/tv-shows/sync-tmdb` (admin), ny "TMDb-synkronisering (TV-serier)"-sektion på Indstillinger-siden. Genbruger film-synkens batch-mønster (rate-limit-stop, token-tjek før løkken). Sæson-listen flettes med den eksisterende via `season_number`, så `seasons[].owned` og episoders `watched`-status bevares uændret mens sæson-metadata (episode_count/navn/air_date) opdateres — en ny sæson tilføjes uejet, en fjernet sæson droppes.

Alle rettelser har egne regressionstests (16 nye backend-tests i alt). Fuld backend-suite (233 tests) og frontend-build kørt igennem uden fejl efter hver ændring.

## [0.39.1 build 0049] — 2026-08-02 — Justering: sæson-badge-position på TV-kort (feature #55)

- `.movie-seasons-badge` (`TvShows.css`) flyttet fra centreret (`translateX(-50%)`) til 16px højre for centrum (`translateX(calc(-50% + 16px))`), efter visuel feedback fra Jan om at badgen sad forkert i forhold til rating-badgen i nederste venstre hjørne af posteren.

## [0.39.0 build 0048] — 2026-08-02 — Sæsonvalg ved oprettelse af ny serie, sæson-badge på TV-kort, TV-sektion på Print-siden (feature #54/#55/#56)

- **Feature #54**: nyt backend-endpoint `GET /api/tv-shows/tmdb-preview/{tmdb_id}` henter TMDb's sæsonliste (samme `Season`-form som `create_tv_show` allerede bruger) uden at gemme noget — bruges til at vise en sæson-vælger i tilføj-formularen for en HELT NY serie (ingen dublet), så brugeren kan afkrydse hvilke sæsoner udgaven indeholder *før* "Gem". De valgte sæsoner markeres automatisk som ejet (`setSeasonOwned`) lige efter oprettelsen, i samme handling. Sæson-vælgeren fra dublet-flowet (feature #53) er samtidig udvidet fra énkelt-valg til fler-valg (`selectedSeasonNumber` → `selectedSeasonNumbers[]`), så man kan tilføje flere sæsoner ad gangen (fx en "Sæson 4-6"-boks) i begge flows.
- **Feature #55**: TV-seriekort (`TvShows.jsx`/`.css`) viser nu en badge ("2/6 sæsoner") med antal ejede sæsoner ud af seriens samlede antal, i samme visuelle stil som serienummer-/format-badgen — erstatter den tidligere rene tekstlinje der kun viste det samlede antal.
- **Feature #56**: `PrintList.jsx` henter nu både film og TV-serier (`api.listTvShows`) og viser en selvstændig TV-serie-tabel (Serienr./Navn/År/Sæsoner/Format/Lokation) efter filmtabellen, med sideskift ved print (`.print-section-break`). Samme fritekst-søgning filtrerer begge tabeller.
- Nyt test i `test_tv_shows.py` for `tmdb-preview`-endpointet (verificerer at intet persisteres). Alle 22 TV-serie-tests + frontend-build kørt igennem uden fejl.

## [0.38.0 build 0047] — 2026-08-02 — Sæson-gruppering ved scan af TV-serier (feature #53)

- `MovieLookupForm.jsx`: når en valgt TV-serie-kandidat allerede findes i biblioteket (`checkTvDuplicate`), hentes den fulde eksisterende post (`api.getTvShow`) og et nyt "Føj til eksisterende serie i stedet"-panel vises — en sæson-vælger (chips, ✓ markerer allerede-ejede sæsoner) der kalder den allerede eksisterende `PATCH /api/tv-shows/{id}/seasons/{n}` (`setSeasonOwned`) direkte på den fundne serie, i stedet for at oprette en ny duplikeret `TvShow`-post. Løser Jans eksempel: scanner man "The Americans Season 2" efter allerede at have "The Americans" i biblioteket, markeres sæson 2 som ejet på den eksisterende serie i stedet for at oprette en ny "The Americans"-post.
- Ingen backend-ændringer nødvendige — genbruger udelukkende eksisterende endpoints (`GET /api/tv-shows/{id}`, `PATCH .../seasons/{n}`) fra feature #47/#48.
- Den almindelige "Gem"-knap findes stadig som bevidst fallback (omdøbt til "Opret som ny separat serie" når en gruppering er mulig) — til reelt tilsigtede duplikater (fx to fysiske kopier af samme sæson).
- Design bekræftet eksplicit af Jan før implementering (2026-08-02): genbrug af TV-seriens allerede eksisterende `seasons[]`-underarray som "gruppen", fremfor en ny separat gruppe-/franchise-model.

## [0.37.0 build 0046] — 2026-08-02 — UI-konsolidering del 1+2: separat Scan-fane fjernet, TV-serier får fuld sort/preset/vis-felter-paritet (feature #51/#52), fix (BUGS.md #22)

- **Feature #51**: separat "Scan"-fane fjernet fra hovedmenuen (`App.jsx`) og `ScanMovie.jsx` slettet. `MovieLookupForm` (scan + manuel TMDb-søgning) er nu integreret direkte i hver bibliotek-fane via et "+ Tilføj film"/"+ Tilføj serie"-panel (`Library.jsx`s panel var allerede der for ønskelisten — gjort ubetinget synligt også for hovedbiblioteket; `TvShows.jsx` havde allerede sit "Tilføj serie"-panel).
- **Feature #52**: `TvShows.jsx`s værktøjslinje omskrevet til fuld paritet med `Library.jsx`: fler-niveau sortering (op til 3 niveauer, feature #17/#27), navngivne/gemte "visninger" der husker søgetekst+filtre+sortering (feature #44), og et nyt "Vis felter"-panel (år/tags/format/lyd-type/medietype/rating) — alle bagt af nye, TV-separate indstillingsfelter (`tv_sort_levels`/`tv_sort_presets`/`tv_visible_fields`) på `UserSettings`, persisteret via samme `PATCH /api/users/me/settings`-endpoint (allerede dotted-path-atomisk, ingen backend-ændring nødvendig ud over modellen). `api.listTvShows` opgraderet til at acceptere fler-niveau sort-arrays (samme form som `api.listMovies`).
- **BUGS.md #22** (opdaget undervejs, rettet i samme commit da den delte model lige alligevel blev udvidet): `VisibleFields`-modellen manglede `media_type`-feltet som frontend allerede sendte/læste — "Medietype"-togglen i filmbibliotekets "Vis felter"-panel virkede derfor kun for den aktuelle session og nulstilledes ved genindlæsning. Tilføjet til modellen og til `DEFAULT_SETTINGS` (både film og TV).
- Backend-tests: alle 218 eksisterende tests kører uændret igennem (ingen ny backend-logik i denne commit ud over model-/default-udvidelsen).

## [0.36.1 build 0045] — 2026-08-02 — Fix: login fra mobil fejlede pga. autokapitalisering (BUGS.md #21)

- `Login.jsx`: brugernavn-feltet fik `autoCapitalize="off" autoCorrect="off" spellCheck={false}` — iOS Safari (og det installerede PWA-ikon) autokapitaliserede ellers første bogstav i feltet, så "jgl" blev til "Jgl" mens brugeren skrev, hvilket gav en ægte men forvirrende 401 mod det eksakt versalfølsomme login-opslag.
- Login/registrering gjort versal-ufølsomt generelt (ud over selve UI-rettelsen): nyt `username_normalized`-felt på brugere, samme normalisér-til-sammenligning/bevar-original-visning-mønster som `tag_service`. Unikheds-indekset flyttet fra `username` til `username_normalized`, med automatisk migration af eksisterende brugere ved opstart.
- Diagnosticeret live mod produktions-`journalctl`: ægte 401-svar fra to andre LAN-IP'er end PC'ens bekræftede at anmodningen nåede serveren og blev korrekt afvist ud fra det den modtog — udelukkede dermed net/certifikat-problemer og pegede direkte på et klient-side tekst-mangling-problem.
- Nye tests i `test_auth.py` (3): login med anden versal end registreret, registrering afviser versal-variant af eksisterende brugernavn, migration af gammel bruger uden `username_normalized`.

## [0.36.0 build 0044] — 2026-08-02 — TV-serier: frontend + scan-routing + branding (feature #47/#48/#49/#50)

Fuldfører TV-serie-understøttelsen (backend var feature #47/#48/#49's forrige to commits) — nu synlig og brugbar i UI'et.

- Ny `frontend/src/pages/TvShows.jsx`: "TV-serier"-fane, søgning/tag/format/lyd/medietype/set-status-filtrering, ét-niveaus sortering (bevidst uden den fulde fler-niveau-sortering/preset-maskine fra film — se "ikke porteret" nedenfor), detaljevindue med tags/format/lokation/ejer/personlig rating/note/set-status samt en sæson-liste (`SeasonRow`) med "ejer"-checkbox pr. sæson og udvidelig episode-liste med "set"-checkbox pr. episode.
- `MovieLookupForm.jsx` udvidet: manuel søgning kalder nu både `/api/movies/tmdb-search` og `/api/tv-shows/tmdb-search` parallelt (samme mønster som stregkode-scannet allerede fik i forrige commit); hver kandidat har et "Film"/"TV-serie"-badge; dublet-tjek og gem-handling routes til den rigtige ressource ud fra kandidatens `media_kind`. Genbruges uændret af både "Scan"-siden og ønskelistens tilføj-panel — nu for begge typer.
- **Live-verificeret mod rigtig lokal MongoDB + rigtig TMDb** (ikke kun mocked tests): oprettede den ægte "Breaking Bad" via `tmdb_id`, bekræftede korrekt sæson-liste (inkl. "Specials"-sæson 0), markerede sæson 1 ejet (udløste et ægte lazy TMDb-kald, fik 7 rigtige episodetitler inkl. "Pilot"), markerede episode 1 set, bekræftede kun episode 1 (ikke 2-7) blev påvirket. Ryddet op efter test.
- **Ikke porteret til TV i denne omgang** (bevidst afgrænset scope): fler-niveau sortering/gemte visninger (#17/#27/#44), skuespiller/instruktør-browsing (#41), franchise-gruppering (#42), Plex-integration (#45), statistik-siden (#43). Kun film har disse indtil videre.
- **Branding** (feature #50): app-titel "Filmbibliotek" → "Film & TV-bibliotek" (header, login-skærm, PWA-manifest, `<title>`), "Bibliotek"-fanen omdøbt til "Film", "Scan film" → "Scan" (dækker nu begge typer). `CLAUDE.md`s projektbeskrivelse, arkitektur-diagram og projektstruktur-liste opdateret til at nævne TV-serier som egen ressource.
- Ingen nye backend-tests i denne commit (frontend-only + live-manuel backend-verifikation) — de 215 eksisterende backend-tests fra de to forrige TV-commits dækker uændret.

## [0.35.1 build 0043] — 2026-08-02 — Stregkode-scan søger nu både film og TV, backend (feature #49)

- `scan_service.lookup_by_barcode` søger nu `tmdb_client.search_movies` **og** `search_tv` for det gættede produktnavn, i stedet for kun film. Kandidater fra begge lister samles i ét svar (film først, derefter TV), hver tagget med nyt `media_kind: "movie"|"tv"`-felt på `MovieCandidate`.
- `GET /api/tv-shows/tmdb-search` sætter nu korrekt `media_kind="tv"` (fanget under implementeringen — ville ellers stille og roligt have arvet "movie"-default'en fra den delte `MovieCandidate`-model).
- Direkte adressering af BUGS.md #20's konkrete eksempel: et scannet TV-boxset ("The Americans") vil nu faktisk dukke op som en valgbar kandidat, tagget som TV-serie, i stedet for at give "intet match".
- Eksisterende scan-lookup-tests opdateret til eksplicit at mocke `search_tv` (var utilsigtet afhængige af en rigtig `TMDB_API_TOKEN` i lokal `.env` for stiltiende at lykkes mod den ægte API — ikke hermetisk). Ny test verificerer sammenfletningen af film- og TV-kandidater.
- **Kun backend** — frontend bruger endnu ikke `media_kind` til at route gem-handlingen til det rigtige bibliotek. Det følger i næste commit sammen med TV-serier-fanen.

## [0.35.0 build 0042] — 2026-08-02 — TV-serier: ny selvstændig ressource, backend (feature #47/#48)

Jan bad om fuld TV-serie-understøttelse (2026-08-02): egen ressource (ikke bare et filter på filmbiblioteket), med dyb sæson/episode-sporing. Dette er backend-delen — frontend, stregkode-scan-integration og branding følger i separate commits.

- Ny `/api/tv-shows`-ressource: egen `tv_shows`-collection, egen `deleted_tv_shows`-log, egen fortløbende `serial_number`-tæller (adskilt fra filmenes). Samme CRUD-/søgnings-/filter-/sorterings-/dublet-advarsels-/soft-delete-mønster som film, genbruger `MovieFormat`/`AudioType`/`MediaType`-enums.
- Nye `tmdb_client.search_tv`/`get_tv_show_details`/`get_season_details` — TV har en helt anden TMDb-respons-form end film (`name`/`first_air_date`/`created_by`/`seasons`/`status`, intet `belongs_to_collection`-ækvivalent).
- **Sæson-ejerskab + episode-set-status** (feature #48): `PATCH /api/tv-shows/{id}/seasons/{n}` sætter `owned`, og henter/cacher lazily sæsonens fulde episode-liste fra TMDb *første* gang den markeres ejet (ikke alle sæsoner på én gang ved oprettelse — kunne være dyrt for serier med mange sæsoner). `PATCH .../seasons/{n}/episodes/{m}` sætter `watched`+dato pr. episode. Begge er atomiske positional-`$`-opdateringer af én sæsons episode-liste ad gangen — bevidst IKKE MongoDB `arrayFilters` (uverificeret mongomock-understøttelse, se BUGS.md-lignende forsigtighed i movie_repository).
- To niveauer af "set"-status: et top-niveau `watched` på selve serien (identisk med film) + separat pr.-episode `watched` — ikke automatisk koblet sammen.
- Faktisk IMDb-rating (feature #46) og skriv-kun API-nøgle-mønsteret genbruges uændret.
- `TmdbNotFoundError`/`DuplicateBarcodeError`-beskeder generaliseret (var hardkodet til "movie") til at dække begge ressourcer.
- 21 nye tests i `test_tv_shows.py`: CRUD, uafhængig serienummer-tæller, dublet-tjek, søgning/filter/sortering, personlig rating/note, set-status, lazy sæson-fetch (inkl. at gentagne owned-toggles ikke genhenter), episode-watched, tmdb-search, auth-gating.

## [0.34.1 build 0041] — 2026-08-02 — Fix: bedre titel-oprensning før TMDb-søgning (BUGS.md #20)

- `text_cleanup.clean_bracketed_title` strippede kun *indrammede* suffixer ("(DVD)", "[Blu-ray]") — udvidet til også at fjerne almindelig fritekst-boilerplate ("Special Edition", "Complete Series/Collection/Trilogy", "Season(s) N-M", regionskoder, bare "DVD"/"Blu-ray"/"VHS"/"UHD" uden parentes), som ellers kunne få en ægte films TMDb-søgning til at give 0 resultater.
- Undersøgt live mod produktion (`journalctl` + direkte `tmdb_client.search_movies`-test): stregkoden `5039036089630` er en TV-serie-boks ("The Americans") — matcher aldrig en film-søgning, uanset oprensning, da appen bevidst kun søger TMDb's film-database. Ikke en fejl i sig selv, men afslørede den reelle oprensnings-svaghed ovenfor.
- Nye tests i `test_text_cleanup.py` (7 — ingen fandtes for denne funktion før).

## [0.34.0 build 0040] — 2026-08-02 — Faktisk IMDb-rating i stedet for TMDb's (feature #46)

- Ny `app/integrations/omdb_client.py`: henter den reelle IMDb-rating via OMDb (`GET ?i=<imdb_id>&apikey=`), nøglet på TMDb's `imdb_id` (nu også eksponeret direkte i `tmdb_client.get_movie_details`'s returdict). Fejler aldrig synligt — manglende nøgle/imdb_id/match/fejl giver alle `None`.
- Ny `movie_service._resolve_rating()`: bruges ved både oprettelse (`create_movie`) og synkronisering (`sync_all_from_tmdb`) — foretrækker IMDb's rating, falder tilbage til TMDb's `vote_average` hvis OMDb ikke er konfigureret eller intet har at byde på. Fuldt bagudkompatibelt: uden en OMDb-nøgle sat er adfærden identisk med før.
- `system_settings`-mekanismen (feature #36) udvidet med `omdb_api_key` — samme skriv-kun mønster som TMDb/UPC/Discogs/Plex-token. Ny `ApiKeyRow` i Settings.jsx.
- `ARCHITECTURE.md`/`MOVIE_API_REFERENCE.md` opdateret — det tidligere eksplicit dokumenterede fravalg af OMDb (FEATURES.md #13) er nu omgjort på Jans ønske.
- Nye tests i `test_omdb.py` (8): guard clauses uden nøgle/imdb_id, `_resolve_rating` foretrækker/falder tilbage, fuld oprettelse/synkronisering bruger IMDb-rating når tilgængelig. Plus 1 ny test i `test_system_settings.py`.

## [0.33.1 build 0039] — 2026-08-02 — Fix: kamera-scan fandt ofte intet match (BUGS.md #19)

- `BarcodeScanner.jsx`: `BrowserMultiFormatReader` begrænses nu eksplicit til `EAN_13`/`UPC_A` via `DecodeHintType.POSSIBLE_FORMATS`, i stedet for at forsøge alle stregkode-symbologier zxing understøtter på hver frame. Uden begrænsningen kunne scanneren på et cover med flere stregkoder/meget grafik låse fast på støj og stille returnere et forkert tal for en anden symbologi — hvilket fejlagtigt fremstod som "intet match", selvom brugerens øjne/manuel indtastning af samme tal virkede fint. `@zxing/library` tilføjet som direkte dependency (var kun transitiv peer-dependency).
- Ny `scan_service._alternate_upc_ean_form()`: prøver automatisk UPC-A (12 cifre) ↔ EAN-13 (13 cifre, foranstillet 0) hvis første opslag ikke giver match — dækker tilfælde hvor en lookup-tjeneste kun har koden indekseret under den ene form. Samt `.strip()` af scan-input.
- `MOVIE_API_REFERENCE.md` opdateret — den tidligere dokumenterede antagelse om format-håndtering var reelt aldrig implementeret.
- Nye tests i `test_scan.py` (7): format-konvertering begge veje, ingen konvertering for ægte 13-cifrede EAN'er, fallback finder match, stadig intet match efter fallback, whitespace trimmes.

## [0.33.0 build 0038] — 2026-08-01 — Plex-integration (feature #45)

- Nyt `app/integrations/plex_client.py`: slår en film op mod brugerens egen Plex-server via `/identity` (machineIdentifier) + `/search?query=` (kandidater). Matcher først på TMDb-id via kandidaternes `Guid[].id`, ellers på præcist titel+år. Fejler aldrig synligt — manglende konfiguration/utilgængelig server/intet match giver alle `{"available": false}`.
- Nyt `plex_service.check_availability` + `GET /api/movies/{movie_id}/plex` (`{available, play_url}`), kaldt on-demand fra detaljevinduet (ikke automatisk pr. kort i biblioteket).
- `system_settings`-mekanismen (feature #36) udvidet med `plex_token` (samme skriv-kun mønster som TMDb/UPC/Discogs) og `plex_server_url` — den ene bevidste undtagelse, da en LAN-adresse ikke er en hemmelighed, og derfor returneres med sin faktiske værdi. Ny `PlainSettingRow`-komponent i Settings.jsx til dette.
- Matching-logikken udtrukket til en ren `plex_client._match_movie()`-funktion (samme mønster som `tmdb_client._director()`), så den er direkte testbar uden HTTP-mocking.
- **Ikke live-verificeret** mod en rigtig Plex-server (ingen adgang under udvikling) — Plex's GUID-format kan variere afhængig af metadata-agent-version; verificér title+år-fallback'et virker som forventet ved første rigtige brug, se MOVIE_API_REFERENCE.md.
- CLAUDE.md regel 6 udvidet til at nævne Plex. Nye tests i `test_plex.py` (9) + `test_system_settings.py` (2 nye): matching-logik, service-lag, admin-only endpoint degraderer pænt uden konfiguration.

## [0.32.0 build 0037] — 2026-08-01 — Gemte fulde filter-sæt / "visninger" (feature #44)

- `SortPreset` (`models/user.py`) udvidet med valgfrie `query`/`tags`/`formats`/`audio_types`/`media_types`/`watched` ud over det oprindelige `levels` — en gemt visning fanger nu hele toolbar-tilstanden, ikke kun sorteringen. Alle nye felter er defaulterede, så presets gemt før denne feature fortsat validerer og anvender blot ingen ekstra filtrering.
- Ingen ændring i backend-service/repository-laget — `sort_presets` var allerede en generisk, hel-array `$set` via `PATCH /api/users/me/settings`.
- `Library.jsx`: "Gem nuværende visning"/"Vælg gemt visning" gemmer og genanvender nu søgetekst, tag/format/lyd/medietype-filtre og set-status sammen med sorteringen.
- To eksisterende tests i `test_auth.py` opdateret til den nu-rigere preset-form (defaulterede felter i response). To nye regressionstests: fuld filter-tilstand round-tripper, gammel sort-only preset defaulter gracefuldt.

## [0.31.0 build 0036] — 2026-08-01 — Statistik-side (feature #43)

- Ny `GET /api/movies/stats` (`movie_repository.find_all_library_movies` + `movie_service.get_collection_stats`): antal film, samlet spilletid, set/ikke-set, genre-/årti-/format-fordeling og top 10 instruktører/skuespillere. Ønskeliste ekskluderet. Beregnet i Python (`Counter`) over ét uncapped `find()`, ikke en Mongo aggregation-pipeline — matcher kodebasens stil og undgår uverificerede pipeline-stadier i mongomock.
- Ny "Statistik"-fane/side (`Statistics.jsx`): opsummeringskort (antal, spilletid, set/ikke-set) + bar-liste-sektioner for genre/årti/format/instruktører/skuespillere, uden ny chart-afhængighed (rene CSS-bredde-bars).
- Nye tests i `test_stats.py`: tomt bibliotek, ønskeliste ekskluderet, spilletid/set-status, genre/format-fordeling, årti-gruppering, top instruktører/skuespillere, film uden år/spilletid bryder ikke beregningen.

## [0.30.0 build 0035] — 2026-08-01 — Set/franchise-gruppering (feature #42)

- Nye `collection_id`/`collection_name` (TMDb's `belongs_to_collection`) — TMDb-sourced, ikke klient-sættelig (samme mønster som `rating`), hentet ved oprettelse og opdateret ved synkronisering.
- Ny `tmdb_client.get_collection()` mod TMDb's `/collection/{id}` — fuld liste af en samlings film.
- Ny `GET /api/movies/collections/{collection_id}`: krydsreferer TMDb's samlingsliste mod egne film via ét batch-opslag (`movie_repository.find_by_tmdb_ids`, `$in`) i stedet for ét pr. del — hver del markeret `owned`/`owned_movie_id`/`owned_is_wishlist`.
- `Library.jsx`: "Del af samlingen: X (ejer N af M) ▾" i detaljevinduet, udvides til en liste med ejer-status pr. del og en "+ Tilføj"-knap for manglende (opretter direkte via `tmdb_id`, samme minimalistiske ét-klik-mønster som "Flyt til bibliotek").
- Nye tests i `test_collections.py`: uden samling, gemmer samlingsdata, ejer/mangler/ønskeliste-markering, synkronisering opdaterer samlingsfelter.

## [0.29.0 build 0034] — 2026-08-01 — Skuespiller/instruktør-browsing (feature #41)

- Nyt `director`-felt (TMDb's `credits.crew`, første `job == "Director"`-kredit, `tmdb_client._director`) — hentet ved oprettelse og opdateret ved TMDb-synkronisering, ligesom `cast`. Sættelig manuelt for film oprettet uden `tmdb_id`.
- `GET /api/movies` understøtter nu `?cast=`/`?director=` (præcist felt-match, egne indexes) — filtrerer biblioteket til andre film i samlingen med samme person.
- `Library.jsx`: skuespiller- og instruktør-navne i detaljevinduet er nu klikbare — lukker vinduet og filtrerer biblioteket, vist som en fjernbar "Viser film med ..."-banner over resultaterne.
- Nye tests i `test_person_browsing.py`: `_director`-ekstraktion (fundet/ikke fundet), manuel sætning, filtrering på cast/director.
- Eksisterende TMDb-relaterede test-fixtures (`test_movies.py`, `test_scan.py`, `test_tmdb_sync.py`, `test_duplicate_check.py`) opdateret med `director`-nøglen, som resten af feltlisten allerede krævede eksplicit (bracket-access, ikke `.get()`).

## [0.28.0 build 0033] — 2026-08-01 — "Set"-status + set-dato (feature #40)

- `Movie`/`MovieUpdate`: nye `watched` (bool) og `watched_at` (dato) felter. Filtrerbar (`?watched=true|false`) og sorterbar (`watched_at`) i biblioteket.
- `movie_repository.find_many`: samme "manglende felt ≠ False"-fælde som `is_wishlist` (CLAUDE.md regel 16) — fanget af egen regressionstest før merge. `watched=false`-filteret bruger derfor `{"$ne": True}`, ikke en direkte `False`-lighedstest, så film oprettet før denne feature (uden feltet overhovedet) korrekt tælles som "ikke set".
- `Library.jsx`: ny "Set-status"-filtergruppe (Set/Ikke set chips), ny "✓ Set"-badge på filmkort (poster, nederst til højre — samme mønster som rating-badgen), og et checkbox+dato-felt i detaljevinduet. Set-dato defaulter til i dag når man markerer som set, men kan ændres frit (til at eftertaste ældre film).
- Nye tests i `test_watched_status.py`: default, sæt/fjern, filtrering (inkl. regression for tomheds-fælden), sortering.

## [0.27.0 build 0032] — 2026-08-01 — Personlig rating + note pr. film (feature #39)

- `Movie`/`MovieUpdate`: nye `personal_rating` (1-10, valideret) og `personal_note` (fritekst) — adskilt fra TMDb's offentlige `rating`. `null` rydder feltet (ingen sparse-index-hensyn her, i modsætning til `barcode`/`serial_number`).
- `personal_rating` tilføjet til `movie_repository.SORT_FIELDS` + eget index — sorterbar i biblioteksvisningen ("Din rating").
- `Library.jsx`s detaljevindue: nyt "Din rating"-tal-felt (1-10) og "Din note"-tekstfelt, vist i modal-headeren når sat ("Din: 8/10").
- Nye tests i `test_personal_rating.py`: default-værdi, sæt/ryd, range-validering (422 uden for 1-10), sortering.

## [0.26.0 build 0031] — 2026-08-01 — Dublet-advarsel ved oprettelse (feature #38)

- Ny `GET /api/movies/check-duplicate?tmdb_id=` (`movie_repository.find_by_tmdb_id`, `movie_service.check_tmdb_duplicates`) — returnerer alle eksisterende film (bibliotek og/eller ønskeliste) med samme `tmdb_id`. Registreret før `/{movie_id}`, som de andre specifikke rute-litteraler.
- `MovieLookupForm.jsx`: kaldes automatisk når en TMDb-kandidat vælges. Viser en blød advarsel ("findes allerede i biblioteket (#12)" / "på ønskelisten") uden at blokere gem — flere fysiske kopier er en legitim use case.
- Nye tests i `test_duplicate_check.py`: intet match, match i bibliotek, match i ønskeliste, og at oprettelse af en reel dublet ikke blokeres.

## [0.25.0 build 0030] — 2026-08-01 — Manuel indtastning af stregkode (feature #37)

- `MovieLookupForm.jsx`: nyt tekstfelt + "Slå op"-knap under kamera-scanneren i både "Scan film" og ønskelistens "+ Tilføj ønske"-panel. Kalder samme `handleDetected`-flow (→ `/api/scan/lookup`) som en kamera-scan — ingen backend-ændring nødvendig, stregkoden var allerede bare en streng.

## [0.24.0 build 0029] — 2026-08-01 — Admin-konfigurerbare API-nøgler i Indstillinger (feature #36)

- Ny "System-indstillinger"-sektion (admin-only) på Indstillinger-siden: TMDb API-token, UPC API-nøgle og Discogs-token kan nu sættes/opdateres direkte i UI'et, uden SSH/redeploy.
- Nyt `system_settings_repository`/`system_settings_service`: overstyringer gemmes i en ny `system_settings`-collection (singleton-dokument, `$set`/`$unset` — aldrig read-modify-write) og skrives med det samme ind i den globale `settings`-singleton i hukommelsen, så `tmdb_client`/`discogs_client` osv. bruger den nye værdi uden genstart. `.env` forbliver bootstrap-fallback; et tomt felt rydder overstyringen og falder tilbage til den (ny `ENV_DEFAULT_API_KEYS`-snapshot i `core/config.py`, taget ved opstart før noget kan overskrive den).
- Nye `GET`/`PATCH /api/settings/system` (begge admin-only). **Skriv-kun**: response indeholder kun `configured`/`source` (`env`/`custom`/`unset`) pr. nøgle — aldrig den faktiske værdi, hverken ved læsning eller lige efter en `PATCH` — for at overholde CLAUDE.md regel 6 (udvidet til at dække den nye overstyrings-mekanisme).
- Frontend: tre uafhængige felter (ét pr. nøgle) med status-label og en "Ryd"-knap når en brugerdefineret værdi er sat. Inputs er altid tomme ved indlæsning (viser aldrig en tidligere-gemt værdi).
- Nye tests i `test_system_settings.py`: admin-gating, status uden lækage af værdien, sæt/ryd/uberørte felter, persistens på tværs af requests. Live-verificeret mod en rigtig lokal MongoDB (ikke kun mongomock) via direkte HTTP-kald — bekræftet at værdien aldrig optræder i noget response, at kilden korrekt skifter env → custom → env, og at admin-gating giver 403 for en standard-bruger.
- `ARCHITECTURE.md`, `CLAUDE.md` (regel 6), `FEATURES.md` opdateret.

## [0.23.1 build 0028] — 2026-08-01 — Fix: "Opdatér fra GitHub" fejlede med 500 i produktion (BUGS.md #18)

- Rodårsag var todelt og skjult under udviklingen fordi den manuelle verifikation kørte som et almindeligt SSH-shell i stedet for gennem den faktiske sandboxede `moviedb-backend`-systemd-service: (1) `ProtectSystem=strict` gjorde det meste af filsystemet read-only, men `ReadWritePaths` dækkede kun `backend/`, ikke deploy-loggen, resten af git-repoet eller `npm run build`'s brug af `/tmp`; (2) `NoNewPrivileges=true` gør `sudo` permanent ubrugeligt for servicen og alle dens child-processer — deploy-scriptets `sudo systemctl restart/reload` kunne aldrig lykkes, uanset sudoers-opsætning.
- `moviedb-backend.service`: `ReadWritePaths` udvidet til `/opt/moviedb /opt/moviedb-deploy.log`, ny `PrivateTmp=true` (giver servicen sit eget skrivbare `/tmp` — en hærdningsforbedring i sig selv).
- `scripts/deploy.sh`: `sudo systemctl ...`-kaldene fjernet. Scriptet rører nu i stedet en trigger-fil (`.deploy-restart-trigger` i repo-roden, git-ignoreret), som to nye systemd-units — `scripts/moviedb-deploy-restart.path` (watcher) og `scripts/moviedb-deploy-restart.service` (root, oneshot: genstarter `moviedb-backend` + genindlæser `caddy`) — reagerer på. Ingen `sudo`/setuid involveret, så `NoNewPrivileges=true` kan bevares fuldt ud.
- Den nu overflødige (og aldrig-funktionsdygtige) snævre sudoers-regel `/etc/sudoers.d/jgl-deploy-ota` er fjernet fra serveren.
- Live-verificeret ved at køre hele kæden inde i den faktiske sandboxede mount-namespace via `nsenter` på den kørende proces' PID (ikke et almindeligt shell) — bekræftet reel genstart af `moviedb-backend` (nyt `ActiveEnterTimestamp`) og `Result=success` på restart-servicen.
- `CLAUDE.md` regel 16 udvidet med et nyt punkt: test skal foregå i den faktiske runtime-kontekst (sandkasse/service-isolation), ikke kun logikken i et privilegeret shell. `DEPLOYMENT.md`, `ARCHITECTURE.md`, `BUGS.md`, `.gitignore` opdateret.

## [0.23.0 build 0027] — 2026-08-01 — OTA-feature live-verificeret på produktionsserveren (dokumentation, ingen versionsbump)

- Server-side opsætning fuldført: `/opt/moviedb-deploy.sh` installeret (executable, ejet af `jgl`), gammel bred `jgl ALL=(ALL) NOPASSWD:ALL`-sudoers-regel fjernet og erstattet af snæver `/etc/sudoers.d/jgl-deploy-ota` (kun `systemctl restart moviedb-backend` + `systemctl reload caddy`) — bekræftet med `sudo -n` at hverken mere eller mindre end de to kommandoer er tilladt uden password.
- `deploy_service.trigger_deploy()` kørt direkte på serveren: fuldt deploy-forløb (`git pull` → `pip install` → genstart backend → `npm run build` → genindlæs caddy) gennemført uden fejl på ~15 sek., begge services `active` bagefter, `/api/health` svarede korrekt før/under/efter.
- `FEATURES.md` #20 opdateret `in-progress` → `done`. `DEPLOYMENT.md` opdateret til at afspejle den endelige (snævre) sudoers-opsætning og live-verifikationen.
- Selve knappen i browseren (admin-login → klik → polling) er endnu ikke afprøvet af Jan — funktionaliteten bag den er nu verificeret direkte.

## [0.23.0 build 0027] — 2026-08-01 — OTA-opdatering fra GitHub (feature #20)

- Ny `POST /api/system/deploy` (**admin-only**, `app/api/system.py`) starter et detached baggrunds-subprocess (`deploy_service.trigger_deploy`) der kører et deploy-script og returnerer med det samme (202) uden at vente på det er færdigt.
- Nyt `scripts/deploy.sh` (repo-reference): `git pull` + `pip install` + `npm install && npm run build` + genstart `moviedb-backend`/genindlæs `caddy`. Den faktiske eksekverbare kopi ligger **uden for** git-working-tree'en på serveren (`/opt/moviedb-deploy.sh`) med vilje — ellers ville `git pull` kunne overskrive scriptet mens bash er midt i at læse/eksekvere det.
- Scriptet kører som den almindelige service-bruger uden sudo for `git`/`npm`/`pip`; kun de to præcise `systemctl restart moviedb-backend`/`systemctl reload caddy`-kommandoer er givet en **snæver** navngivet NOPASSWD-sudo-regel — ikke bred adgang. Se DEPLOYMENT.md for opsætning (inkl. erstatning af den brede opsætnings-tids-sudoers-regel).
- Ny `DeployScriptNotFoundError` → 500 hvis scriptet mangler/ikke er sat op endnu, i stedet for en uhåndteret `FileNotFoundError`.
- Nyt `Settings.jsx`-afsnit "Opdatér fra GitHub" (admin-only): udløser opdateringen og poller `/api/health`s `build`-felt indtil den nye version er oppe (typisk under et minut), med tydelig fejl-/timeout-besked hvis noget går galt.
- Nye tests i `test_deploy.py`: admin-gating, korrekt Popen-kald (detached), 500 ved manglende script.
- `ARCHITECTURE.md`, `DEPLOYMENT.md`, `.env.example` opdateret. `FEATURES.md` #20 markeret `in-progress` → afventer server-side opsætning og live-verifikation før `done`.

## [0.22.1 build 0026] — 2026-08-01 — Opfølgende kode-gennemgang af sessionens hurtigt-byggede features

Jan bad tidligere i sessionen om en dyb to-fase gennemgang; den blev udskudt af en lang stribe nye funktionsønsker og gennemføres nu, med fokus på det der blev bygget hurtigt undervejs (ønske→bibliotek-flytning, TMDb-synkronisering, IMDb/trailer-links, medietype, label-migreringer, sortering).

- **Fase 1 (fund)**: `tmdb_client.get_movie_details` manglede eksplicit 429-håndtering (modsat `search_movies`); `sync_all_from_tmdb` tjekkede hverken manglende `TMDB_API_TOKEN` eller rate-limit før/under løkken, så begge situationer ville rapportere *hver film* som en uafhængig fejl i stedet for én klar årsag; `_trailer_url` brugte `video["key"]` uden at tjekke om feltet var sat.
- **Fase 2 (rettelser + systemisk lektion)**: Ny `TmdbRateLimitedError`, eksplicit 429-håndtering i `get_movie_details`. `sync_all_from_tmdb` tjekker nu API-nøglen først og stopper batchen med det samme ved rate-limit (nyt `stopped_early`-felt på `TmdbSyncResult`) i stedet for at blive ved med at forsøge resten. `_trailer_url` springer video-entries uden `key` over. `Settings.jsx`s TMDb-sync-sektion viser nu en klar besked ved `stopped_early` i stedet for en lang liste af "mislykkede" film.
- **CLAUDE.md regel 16** udvidet med to nye lektioner: "samtidige delvise opdateringer" (generaliseret fra BUGS.md #13's fix) og "bulk-operationer mod eksterne API'er" (fra denne gennemgangs fund) — begge skal Claude anvende proaktivt fremover, ikke kun når Jan beder om en gennemgang.
- `BUGS.md` #15, #16, #17 registreret og fikset. Nye tests i `test_tmdb_client.py`, `test_tmdb_sync.py`.

## [0.22.0 build 0025] — 2026-08-01 — Medietype-felt, kortere format/lyd-labels, udvidet sortering

- Nyt `MediaType`-felt (`Fysisk`/`Digital`) på `Movie`/`MovieCreate`/`MovieUpdate` — filtrerbart (`?media_types=`), sorterbart, redigerbart, og vises på filmkort via "Vis felter" som de andre attributter. Nyt indeks på `media_type`.
- `MovieFormat` og `AudioType` fik kortere labels (Jans ønske): `format` VHS/DVD/**BD**/**UHD**/**Digital-UHD**/**Digital-HD**/**Digital-STD** (digital er nu opdelt i kvalitetsniveauer i stedet for ét fladt "Digital"); `audio_types` Stereo/Mono/**DD**/**DD5.1**/**DD7.1**/DTS/**DTS-HD-M**/**Atmos**/**D-true-HD**.
- Nye `movie_repository._migrate_format_labels`/`_migrate_audio_type_labels` kører automatisk ved opstart (`ensure_indexes`) og omskriver *eksisterende* dokumenters gamle, længere labels til de nye — ellers ville de ikke længere validere ved næste redigering. Det gamle "Digital"-format har intet kvalitetsniveau og defaulter til "Digital-HD" ved migrering (tjek/ret manuelt om en anden kvalitet er korrekt). Live-verificeret mod Jans rigtige database — alle eksisterende film blev korrekt omskrevet, ingen data tabt.
- **BUGS.md #14**: sorterings-dropdownens "Tilføjet" var i virkeligheden bundet til `serial_number` (ikke den faktiske oprettelsesdato), og der var ingen eksplicit "sorter efter serienummer"-mulighed. `created_at` er nu whitelistet som sin egen sorterings-mulighed ("Tilføjet"), adskilt fra `serial_number` ("Serienummer") — de kan afvige efter en manuel serienummer-ombytning. Sortering udvidet med `runtime`, `location`, `owner`, `registered_by` ("alle felter", som Jan bad om).
- `ARCHITECTURE.md`, `FEATURES.md` #35 og `BUGS.md` #14 opdateret. Nye/opdaterede tests i `test_movies.py`, `test_label_migrations.py` (ny).

## [0.21.0 build 0024] — 2026-08-01 — TMDb-synkronisering + IMDb/trailer-links

- `tmdb_client.get_movie_details` slår nu `credits`, `videos` og `external_ids` op i **ét** samlet TMDb-kald (`append_to_response=credits,videos,external_ids`) i stedet for to separate kald (detail + credits) — færre HTTP-requests, og giver samtidig adgang til IMDb-id og trailere.
- Nye felter `imdb_url` (bygget fra `external_ids.imdb_id`) og `trailer_url` (første officielle YouTube-"Trailer" fra `videos.results`, `null` hvis ingen) på `Movie`/`MovieCreate`/`MovieUpdate`. Filmens detaljevindue viser nu IMDb-/Trailer-/TMDb-links når de findes.
- Ny `POST /api/movies/sync-tmdb` (admin, registreret før `/{movie_id}`): genindlæser TMDb-metadata (titel/år/poster/plot/genrer/cast/rating/spilletid/imdb/trailer) for alle film med et `tmdb_id`, uden at røre brugerens egne felter. Fejler ét films opslag, fortsætter resten af kørslen (talt i `failed`/`failed_titles`). Ny "TMDb-synkronisering"-sektion på Indstillinger-siden.
- Live-verificeret mod de rigtige TMDb/MongoDB (The Matrix → korrekt IMDb-/trailer-link).
- Nye tests: `test_tmdb_client.py` (_imdb_url/_trailer_url enheds-tests), `test_tmdb_sync.py` (bevarer brugerfelter, springer manuelt oprettede film over, fortsætter forbi enkelt-film-fejl, kræver admin).
- `ARCHITECTURE.md` opdateret. `FEATURES.md` #33, #34 tilføjet, markeret done.

## [0.20.0 build 0023] — 2026-08-01 — "Flyt til bibliotek"-knap på ønskeliste-film

- `MovieUpdate` fik `is_wishlist: bool | None`. `movie_service.update_movie` opdager overgangen: `is_wishlist: true → false` tildeler et nyt `serial_number` via `next_serial_number` (ubegrænset, som ved oprettelse — ikke gated af `_assert_can_edit_serial_number`, da det er en førstegangs-tildeling, ikke en ændring). `is_wishlist: false → true` fjerner nummeret igen (nyt `movie_repository.clear_serial_number`, `$unset` — samme "udelad frem for null"-mønster som `barcode`/BUGS.md #1/#10) og *er* gated af samme adgangsregel som at redigere et eksisterende serienummer.
- Filmens detaljevindue i `Library.jsx` har nu en "Flyt til bibliotek"-knap, vist når filmen er en ønske-post.
- Nye tests i `test_wishlist.py`: flytning tildeler et nyt serienummer og flytter filmen mellem de to lister; flytning er ikke begrænset til registranten; den omvendte retning (bibliotek → ønske) fjerner nummeret korrekt. Live-verificeret mod den rigtige database.
- `ARCHITECTURE.md` opdateret. `FEATURES.md` #32 tilføjet, markeret done.

## [0.19.0 build 0022] — 2026-08-01 — Ønskelisten bruger nu samme scan/søge-metode som "Scan film"

- Jan påpegede at ønskelisten kun kunne udfyldes via en afkrydsningsboks gemt inde i "Scan film"-siden — ikke "samme metode og data opslag" direkte i ønske-sektionen selv.
- Udtrukket hele scan-/manuel TMDb-søgning-/bekræft-og-gem-flowet fra `pages/ScanMovie.jsx` til en ny delt komponent `frontend/src/components/MovieLookupForm.jsx` (props: `user`, `wishlist`, `onSaved`) — samme barcode-scanner, samme UPC/Discogs/TMDb-opslag, samme bekræftelsesformular.
- `pages/ScanMovie.jsx` er nu en tynd wrapper der renderer `<MovieLookupForm user={user} />` (biblioteks-tilstand, uændret opførsel/UI).
- `pages/Library.jsx` fik et nyt "+ Tilføj ønske ▾"-panel i toolbaren (kun vist når `wishlist`-prop er sat) der renderer `<MovieLookupForm user={user} wishlist onSaved={...} />` — samme metode/data-opslag direkte i ønske-sektionen, ingen omvej via Scan film-fanen. Fjernet den tidligere afkrydsningsboks fra `ScanMovie`/`MovieLookupForm` (mode sættes nu af den side der bruger komponenten, ikke en runtime-toggle). Lokation/ejer-felter skjules i ønskeliste-tilstand (giver ikke mening for noget du endnu ikke ejer).
- `ScanMovie.css` omdøbt/flyttet til `components/MovieLookupForm.css`.
- `ARCHITECTURE.md`, `FEATURES.md` #28 opdateret.

## [0.18.1 build 0021] — 2026-08-01 — Fix: gemte sorterings-presets kunne forsvinde igen (race condition)

- `auth_service.update_settings` gjorde læs-hele-settings → flet ét felt → overskriv-hele-settings. `Library.jsx` sender flere `PATCH /api/users/me/settings`-kald i hurtig rækkefølge uden nogen kø (fx sorterings-niveau-justering straks efterfulgt af "Gem som preset") — to overlappende kald kunne race, så det ene kalds skrivning (bygget på en forældet læsning) tavst overskrev det andets, og et lige-gemt preset forsvandt fra databasen (så det ikke kunne vælges igen efter siden blev genindlæst/fanen genbesøgt). Rapporteret af Jan.
- `auth_service.update_settings`/`user_repository.update_settings` opdaterer nu kun de faktisk sendte nøgler via punktum-sti `$set` (fx `{"settings.sort_presets": [...]}`) — atomisk pr. felt, ingen læs-flet-overskriv af hele underdokumentet længere, så to samtidige kald der rører forskellige nøgler aldrig kan miste hinandens skrivning uanset rækkefølge.
- Ny regressionstest `test_settings_updates_do_not_clobber_unrelated_keys`.
- `BUGS.md` #13 registreret og fikset.

## [0.18.0 build 0020] — 2026-08-01 — Ønskeliste

- `Movie`/`MovieCreate` (`models/movie.py`) fik `is_wishlist: bool = False`. `Movie.serial_number` er nu `int | None` — ønskeliste-poster udelader feltet helt fra dokumentet (samme "udelad frem for null"-mønster som `barcode`, BUGS.md #1/#10), og `movie_service.create_movie` springer `next_serial_number()` helt over for dem.
- **Vigtig migration**: `serial_number`-indexet var unikt men ikke sparse før denne version — det ville kollidere hvis to dokumenter mangler feltet. Opdaget under implementeringen da backend nægtede at starte mod Jans rigtige database (`IndexKeySpecsConflict`, da Mongo ikke tillader at redefinere et eksisterende navngivet index med andre indstillinger). `movie_repository.ensure_indexes` migrerer nu selv: dropper det gamle ikke-sparse index og genopretter det sparse, uden manuel indgriben. Live-verificeret mod den rigtige database (to ønskeliste-film oprettet uden kollision, ryddet op igen bagefter).
- `movie_repository.find_many` filtrerer nu på `is_wishlist` — `{"$ne": True}` for hovedbiblioteket (ikke en `False`-lighedstest), så alle film oprettet før denne version (som slet ikke har feltet) fortsat vises korrekt der; kun eksplicit `is_wishlist: true` filtrerer til ønskelisten. Ny index på `is_wishlist`.
- Nyt `?wishlist=true` query-param på `GET /api/movies`.
- `Library.jsx` genbruges for begge visninger via en ny `wishlist`-prop (skjuler serienummer-badge/-felt, ændrer overskrift og tom-tilstand-tekst). Ny "Ønsker"-fane i `App.jsx`.
- `ScanMovie.jsx` fik et "Tilføj til ønskeliste i stedet for biblioteket"-afkrydsningsfelt i gem-formularen.
- Nye tests i `test_wishlist.py`: ønskeliste-film har intet serienummer, bibliotek/ønskeliste-visninger er adskilte, flere ønskeliste-film kan oprettes uden kollision.
- `ARCHITECTURE.md` opdateret (REST-kontrakt, MongoDB-skema, ny note om ønskeliste og index-migrationen). `FEATURES.md` #28 markeret done.

## [0.17.0 build 0019] — 2026-08-01 — Fler-niveau sortering + gemte sorterings-presets

- **Breaking (internt) API-kontrakt-ændring**: `GET /api/movies`s `?sort=`/`?direction=` (to separate, single-felt, `Literal`-valideret) er erstattet af ét `?sort=` med op til 3 kommaseparerede `felt:retning`-tokens (fx `format:asc,audio_types:asc,title:desc`). Ukendt felt/retning droppes/defaulter i stedet for at give 422 — se `movie_service.parse_sort_param` (ny) og `ARCHITECTURE.md`.
- `movie_repository.find_many` bruger nu et compound Mongo-sort (`cursor.sort([...])`) i stedet for ét felt. `SORT_FIELDS`-whitelisten udvidet med `format`, `audio_types`.
- `UserSettings`/`UserSettingsUpdate` (`models/user.py`) har nye felter `sort_levels` (aktive niveauer) og `sort_presets` (navngivne, gemte kombinationer af niveauer) — nye `SortLevel`/`SortPreset`-modeller. Gamle `sort_field`/`sort_direction` bevares i skemaet for bagudkompatibilitet, men skrives ikke længere af nye klienter.
- `Library.jsx`s sorterings-panel (fra v0.12.0's klik-til-vis) udvidet til op til 3 niveauer (tilføj/fjern/vælg felt/vend retning pr. niveau), plus en "Presets"-dropdown til hurtigt at genanvende en gemt kombination, et navn-felt + "Gem som preset"-knap, og en liste over gemte presets med sletteknap.
- `api/client.js`s `listMovies` accepterer nu `sort` som enten en klar streng eller en `[{field, direction}]`-liste (bygger selv query-strengen). `PrintList.jsx` opdateret til den nye kontrakt.
- Eksisterende sorterings-tests i `test_movies.py` opdateret til ny kontrakt + ny `test_multi_level_sort_falls_through_to_second_field`. Nye `test_sort_parsing.py` (enheds-tests af `parse_sort_param`) og `test_auth.py::test_multi_level_sort_and_presets_roundtrip`.
- `ARCHITECTURE.md`, `FEATURES.md` #17/#27 markeret done.

## [0.16.0 build 0018] — 2026-08-01 — Discogs som fallback ved stregkode-opslag

- Undersøgt FEATURES.md #30 / brugerens rapport om at "stregkode-scanning ikke virker": ikke en fejl i koden — UPCitemdb's trial-tier svarer korrekt (live-verificeret), men er stærkt USA-detail-centreret og misser ofte europæiske EAN-13 stregkoder på film, hvilket viste sig som "intet match" i UI'et.
- Ny `backend/app/integrations/discogs_client.py`: `lookup_title(barcode)` mod Discogs' `database/search?barcode=`, samme "aldrig kast en exception"-kontrakt som `upc_client`. Live-verificeret mod den rigtige API. Virker uden token (25 req/min) eller med et valgfrit `DISCOGS_TOKEN` (60 req/min).
- `scan_service.lookup_by_barcode` prøver nu Discogs som fallback når UPCitemdb ikke finder noget, før der falses tilbage til "intet gæt" (→ frontend beder om manuel søgning).
- Udtrukket delt `clean_bracketed_title`-helper (`integrations/text_cleanup.py`) fra `upc_client`, genbruges af `discogs_client`. Discogs-titler renses desuden for det ledende "Artist - "-præfiks (`_strip_artist_prefix`) som Discogs sætter på stort set alle udgivelser.
- Nye tests: `test_discogs_client.py` (title-cleaning, tomt resultat, netværksfejl → `None`), `test_scan.py::test_scan_lookup_falls_back_to_discogs_when_upc_has_no_match`.
- `MOVIE_API_REFERENCE.md`, `ARCHITECTURE.md`, `.env.example` opdateret. `FEATURES.md` #30 markeret done.

## [0.15.0 build 0017] — 2026-08-01 — Soft-delete af film + slettet-liste

- Ny collection `deleted_movies` (`movie_repository.archive_deleted`/`list_deleted`, index på `deleted_at`).
- `movie_service.delete_movie` logger nu filmen (serienr, titel, år, format, tidspunkt, hvem) i `deleted_movies` *før* den fjernes fra `movies` — i stedet for bare at forsvinde. Serienummeret er automatisk frit til genbrug bagefter (det unikke index kender kun til film der stadig findes i `movies`).
- Ny `GET /api/movies/deleted` (registreret før `/{movie_id}`), nyt `DeletedMovie`-model.
- `DELETE /api/movies/{id}`-handleren henter nu `current_user` for at kunne logge hvem der slettede.
- Ny sektion "Slettede film" på Indstillinger-siden, viser serienr./titel/år/hvornår/hvem.
- Nye regressionstests i `test_deleted_movies.py`: sletning logges korrekt, et frigjort serienummer kan genbruges af en ny film, sletning af ukendt film giver stadig 404.
- `ARCHITECTURE.md` opdateret (REST-kontrakt, MongoDB-collections). `FEATURES.md` #29 markeret done.

## [0.14.0 build 0016] — 2026-08-01 — Print-venlig liste-side

- Ny frontend-side `frontend/src/pages/PrintList.jsx` + `PrintList.css`, ny fane "Print" i navigationen.
- Henter alle film via det eksisterende `GET /api/movies` (sorteret på `serial_number` stigende), viser dem i en kompakt tabel (Serienr./Titel/År/Format/Lokation), én film pr. linje. Simpel fritekst-søgning for at afgrænse listen før udskrift.
- `@media print`-regler skjuler navigation/knapper/footer og lader kun tabellen fylde siden ved faktisk udskrivning (`window.print()`).
- Ingen backend-ændringer — genbruger eksisterende `/api/movies`-kontrakt. `FEATURES.md` #31 markeret done.

## [0.13.0 build 0015] — 2026-08-01 — Lokation/ejer/registrant + adgangsstyring på serienummer

- `Movie`/`MovieCreate`/`MovieUpdate` (`models/movie.py`) udvidet med `location` (fritekst), `owner` (brugernavn) og `registered_by` (brugernavn, kun læsbar — sættes aldrig af klienten).
- `POST /api/movies` sætter nu `registered_by` til den indloggede bruger (fra JWT-cookien, ikke fra request-body) og lader `owner` defaulte til samme hvis ikke angivet. `movies.py`s `create_movie`/`update_movie`-handlers henter nu `current_user` via `Depends(get_current_user)` og videresender til service-laget.
- Ny `movie_service._assert_can_edit_serial_number`: `PATCH /api/movies/{id}` afviser (403 `NotAuthorizedError`) ændring af `serial_number` medmindre requesten kommer fra en admin eller fra den bruger der står i filmens `registered_by` — håndhævet i backend, ikke kun ved at deaktivere feltet i UI'et (jf. CLAUDE.md regel 16).
- `ScanMovie.jsx`: nye felter "Lokation" og "Ejer" (ejer forudfyldes med den indloggede brugers navn, men kan ændres) i gem-formularen.
- `Library.jsx`s `MovieDetailModal`: nye redigerbare felter Lokation/Ejer, en read-only "Registreret af"-linje, og serienummer-feltet deaktiveres (med forklarende tekst) hvis den nuværende bruger hverken er admin eller filmens registrant.
- Nye regressionstests i `test_movie_permissions.py`: registrant/ejer-defaults, standard-bruger kan ændre serienummer på egne registrerede film men ikke andres, admin kan altid.
- `ARCHITECTURE.md` opdateret (REST-kontrakt, MongoDB-skema, ny note om registrant/ejer/lokation). `FEATURES.md` #25, #26 markeret done.

## [0.12.0 build 0014] — 2026-08-01 — Versionsvisning, runtime-tag, klik-til-vis sortering/filtre

- Tilføjet `backend/app/core/version_info.py`: læser `version.json` (repo-roden) én gang ved opstart. `GET /api/health` returnerer nu også `version`/`build`. Ny test `test_health.py`.
- `frontend/src/App.jsx`: henter `/api/health` ved opstart og viser version+build i en ny footer nederst på siden (feature #22).
- TMDb-integrationen henter nu også `runtime` (minutter) fra `/movie/{id}` og gemmer det på filmen (`tmdb_client.py`, `movie_service.py`, `models/movie.py`). Manuel oprettelse/redigering kan også sætte `runtime` direkte.
- Filmkort i biblioteket kan nu vise en "Spilletid"-værdi (`X min`) via "Vis felter" (feature #23). De viste felter (år/format/lyd/spilletid) er samlet i et nyt 2-kolonne grid (`.movie-meta-grid`) i stedet for én lang kolonne, så kortene fylder mindre i højden.
- Sorterings-kontrollen og tag/format/lyd-filterpanelet i biblioteksvisningen er nu klik-til-vis (`Sortér ▾` / `Filtrér ▾`-knapper), samme mønster som det eksisterende "Vis felter ▾" (feature #24). Filtrér-knappen viser et antal når der er aktive filtre.
- `UserSettings.visible_fields` og `DEFAULT_SETTINGS` udvidet med `runtime`.
- `ARCHITECTURE.md`, `FEATURES.md` opdateret (#22, #23, #24 markeret done).

## [0.11.1 build 0013] — 2026-08-01 — Fase 2: fejlret alle 10 fund fra kode-gennemgangen

Retter BUGS.md #3-12 (registreret i fase 1 af kode-gennemgangen 2026-08-01, se CLAUDE.md regel 16). Kort per fund — fuld beskrivelse/løsning i BUGS.md:

- **#3+#4 (auth_service.py)**: `PATCH /api/users/{id}/role` tjekker nu om brugeren findes (404 i stedet for 500-crash) og afviser at fjerne den sidste admin (ny `LastAdminError` → 409, håndhævet i backend).
- **#5 (Settings.jsx)**: `UsersSection.toggleRole` viser nu en fejlbesked i stedet for at fejle lydløst.
- **#6 (ScanMovie.jsx)**: `saveMovie()` viser nu den faktiske backend-fejl (fx dublet-stregkode-409) i stedet for kun en generisk besked.
- **#7 (tag_service.py)**: `resolve_tags` fanger nu `DuplicateKeyError` fra et race-condition-scenarie ved et helt nyt tag og genindlæser i stedet for at crashe.
- **#8+#9 (tmdb_client.py)**: `_rating()` bruger nu `is not None` (bevarer en ægte `0.0`); ny fælles `_raise_for_status()` mapper alle uventede TMDb-fejlstatusser til `TmdbUnavailableError` (502) i stedet for rå 500'ere.
- **#10 (movie_service.py)**: `create_movie` trimmer og udelader nu blanke/whitespace-only stregkoder helt, samme behandling som `null`.
- **#11 (config.py/main.py)**: ny `Settings.using_insecure_jwt_secret`-property; lifespan logger en tydelig advarsel ved opstart hvis den usikre default-JWT-hemmelighed stadig er i brug.
- **#12 (models/user.py)**: ny validator afviser adgangskoder over bcrypts reelle 72-byte-grænse eksplicit, i stedet for at lade dem blive tavst afkortet.

Ny fælles metode-regel (CLAUDE.md #16) anvendt gennemgående: null-tjek før brug, specifikke fejlbeskeder til brugeren, lockout-beskyttelse i backend, `is not None` for eksterne API-tal, hele klassen af "tomhed"-repræsentationer rettet, sikkerhedskonfiguration advarer ved opstart.

Testdækket: 9 nye regressionstests (`test_roles.py` ×4, `test_movies.py` ×2, `test_tmdb_client.py` ×3 — ny fil). 66/66 grønne. Live-verificeret mod ægte MongoDB (blank-barcode, password-længde, JWT-advarsel fraværende med Jans rigtige `.env`).

## [0.11.0 build 0012] — 2026-08-01 — Telefon-adgang over LAN (HTTPS) + mobilvenligt design

- `frontend/vite.config.js`: dev-serveren binder nu til `0.0.0.0` (`server.host: true`) og kører HTTPS med et selvsigneret cert fra `frontend/.cert/` (git-ignoreret, genereres lokalt med `openssl` — se TECH_REFERENCE.md). HTTPS er et hårdt krav fra browseren for at `getUserMedia` (kamera-scanning) må bruges fra andet end `localhost`.
- Ny indgående firewall-regel (`Movie Database dev (Vite 5173)`, privat netværksprofil) så enheder på samme LAN kan nå dev-serveren. Backend (`:8000`) eksponeres ikke selv — Vite's proxy videresender `/api` server-side, usynligt for telefonen.
- Mobilvenligt responsivt design: `index.css` (input `font-size: 16px` for at undgå iOS Safaris auto-zoom-på-fokus, `overflow-x: hidden`), `App.css` (header/navigation stables og bliver scrollbar under 640px, brugernavn skjules på smalle skærme), `Library.css` (værktøjslinje/filter-paneler stabler, film-detalje-modalen bliver fuldskærmsagtig og bund-forankret på mobil, grid-kolonner tilpasses), `ScanMovie.css` (kandidat-grid og handlingsknapper tilpasses).
- Build verificeret (`npm run build`), HTTPS dev-server smoke-testet lokalt og via LAN-IP.

## [0.10.0 build 0011] — 2026-08-01 — Bruger-roller (admin/standard), adgangskode-ændring

- `models/user.py`: ny `UserRole` enum (`admin`/`standard`), `User.role`. Nye modeller `PasswordChange`, `UserRoleUpdate`.
- **Bootstrap**: det allerførste registrerede bruger bliver automatisk `admin` (`user_repository.count(db) == 0` på registreringstidspunktet); alle efterfølgende registreringer bliver `standard`. Ingen separat seed-konto med kendt/lækbar adgangskode.
- Ny `app/api/deps.py::require_admin`-dependency (403 `NotAuthorizedError` for ikke-admin). `PATCH /api/settings/serial-number` kræver nu admin — `GET` er fortsat åben for alle logget-ind brugere.
- Nye endpoints: `POST /api/users/me/password` (skift egen adgangskode), `GET /api/users` (liste alle, admin), `PATCH /api/users/{id}/role` (forfremme/degradere, admin).
- **Migreret eksisterende data**: den ægte "jan"-konto (oprettet før roller fandtes) fik sat `role: "admin"` direkte i databasen, da den reelt er den eneste/første bruger af appen.
- Frontend: `Settings.jsx` har fået en adgangskode-skift-formular (alle brugere) og en "Brugere"-sektion (kun admin: liste + forfrem/degradér). Serienummer-opsætningen vises stadig for alle (læsning), men felterne er disabled og gem-knappen skjult for ikke-admins.
- Pytest-suite: ny `tests/test_roles.py` (bootstrap, admin-gating på skriv/læs, adgangskode-skift, bruger-liste/rolle-ændring, 403 for standard-brugere). 57/57 grønne. Live-verificeret mod ægte MongoDB.

## [0.9.0 build 0010] — 2026-08-01 — Serienummer-generator-opsætning (afløser dele af v0.8.0)

- **Redesign efter feedback**: Settings-siden viste i v0.8.0 en liste over alle film med redigérbart serienummer. Det er nu flyttet til filmens redigeringsvindue i biblioteket (hvor det hører hjemme sammen med tags/format/audio_types) — Settings-siden har i stedet fået en "Serienummer-opsætning"-formular til selve generatoren.
- Counter-dokumentet (`counters._id: "movie_serial"`) har fået et nyt skema: `next_value` (hvilket nummer næste film får), `increment` (spring for fremtidige tildelinger), `padding_width` (kun visning). Migreres automatisk fra det gamle skema (`{"value": N}`) ved første tilgang — ingen manuel migrering nødvendig.
- Nye endpoints `GET`/`PATCH /api/settings/serial-number`. `start_number` er en "flyt næste-nummer-markøren hertil"-handling (ikke en formel-oprindelse) — sætter du den til 500, får den næste tilføjede film nummer 500 præcis. `increment` ændrer kun springet for fremtidige tildelinger fra det nuværende punkt.
- `movie_repository.next_serial_number` er nu kollisions-sikker efter reconfigurering: rammer det beregnede nummer en allerede-brugt værdi (fx efter at have flyttet `start_number` tilbage i et brugt interval), rykker den videre til første ledige nummer i stedet for at fejle med en duplicate-key-fejl.
- `padding_width` bruges i frontend til at zero-padde serienummer-badges (fx "00007") — rent visuelt, påvirker ikke det lagrede tal eller sorteringen.
- Pytest-suite: ny `tests/test_settings.py` (default-opsætning, ændring af start/increment, kollisions-omgåelse efter reconfigurering, validering, auth-krav). 48/48 grønne. Live-verificeret mod ægte MongoDB, inkl. den automatiske skema-migrering af det eksisterende counter-dokument.

## [0.8.0 build 0009] — 2026-08-01 — Settings-side: redigérbart serienummer

- `MovieUpdate` accepterer nu `serial_number` (positivt heltal). `movie_service._reassign_serial_number` bytter automatisk plads med en evt. film der allerede har det ønskede nummer — via et sentinel-mellemtrin (`-1`), da MongoDB's unique index på `serial_number` ellers ville afvise et direkte byt (intet indbygget atomisk "swap to unique values" uden transaktioner).
- Nye repository-funktioner `find_by_serial_number` og `set_serial_number` i `movie_repository.py`.
- Ny frontend-side `pages/Settings.jsx` (+ `Settings.css`), tilgået via en ny "Indstillinger"-fane i hovednavigationen. Viser konto-info (brugernavn) og en liste over alle film med redigérbart serienummer pr. række.
- Pytest-suite udvidet med swap-scenariet, "sæt til ubrugt nummer" og validering af ikke-positive værdier (422). 41/41 grønne. Live-verificeret mod ægte MongoDB (byt bekræftet i begge retninger).

## [0.7.0 build 0008] — 2026-08-01 — Brugerlogin + server-side view-indstillinger

- Nye backend-moduler: `core/security.py` (bcrypt password-hash, JWT via `pyjwt`), `models/user.py`, `repositories/user_repository.py`, `services/auth_service.py`, `api/auth.py` (`POST /api/auth/register|login|logout`), `api/users.py` (`GET /api/users/me`, `PATCH /api/users/me/settings`), `api/deps.py::get_current_user`.
- **Ét fælles filmbibliotek** for alle brugere — kun view-/filterindstillinger (`sort_field`, `sort_direction`, `visible_fields`) er personlige, gemt i `users.settings` i stedet for browserens `localStorage`.
- `movies`/`tags`/`scan`-routerne kræver nu login (router-level `dependencies=[Depends(get_current_user)]`) — 401 uden gyldig session. Session er en JWT i en httpOnly cookie (`access_token`, `samesite=lax`), ikke en Bearer-header.
- Åben tilmelding: alle kan oprette en konto via `POST /api/auth/register` (brugernavn 3-32 tegn, adgangskode min. 8 tegn, bcrypt-hashet). Der er ikke lagt et admin-lag ind til at begrænse hvem der kan registrere sig.
- Frontend: ny `pages/Login.jsx` (login/opret-konto), `App.jsx` gater nu hele appen bag `GET /api/users/me` og har fået en "Log ud"-knap. `Library.jsx`'s sortering/synlige-felter er flyttet fra `localStorage` til `api.updateMySettings()`.
- Nye JWT/cookie-relaterede indstillinger i `.env.example`: `JWT_SECRET_KEY` (skal genereres unikt pr. miljø), `COOKIE_SECURE` (sæt til `true` bag HTTPS i produktion).
- Pytest-suite udvidet med `tests/test_auth.py` (register/login/logout/settings/gating). `tests/conftest.py`'s `client`-fixture logger nu automatisk en test-bruger ind via en rigtig `/api/auth/register`-kald (httpx's cookie-jar håndterer resten), så alle eksisterende movie-/tag-/scan-tests fortsat virker uændret. 38/38 grønne. Live-verificeret mod ægte MongoDB (register → beskyttet endpoint → settings-update → logout → 401).

## [0.6.1 build 0007] — 2026-08-01 — Fix: serienummer/format-badge skjult bag poster

- `frontend/src/pages/Library.css`: `.movie-serial` og `.movie-format-badge` har fået `z-index: 2` — de blev malet under poster-billedet efter `.movie-poster` fik `position: relative` i v0.6.0 (nødvendig for rating-badgen). Se BUGS.md #2.

## [0.6.0 build 0006] — 2026-07-31 — Rating, sortering og konfigurerbar kort-visning

- `backend/app/integrations/tmdb_client.py`: `search_movies()` og `get_movie_details()` returnerer nu også `rating` (TMDb `vote_average`, rundet til 1 decimal — **ikke** den faktiske IMDb-rating, se MOVIE_API_REFERENCE.md).
- `Movie` og `MovieCandidate` har fået feltet `rating`. Kun sat automatisk via `tmdb_id`-oprettelse — ikke en del af `MovieCreate`/`MovieUpdate` (samme princip som `overview`/`genres`/`cast` for TMDb-stien).
- `GET /api/movies` har nye query-params `?sort=` (`title`\|`year`\|`serial_number`\|`rating`) og `?direction=` (`asc`\|`desc`). Sortérbare felter er whitelistet i `movie_repository.SORT_FIELDS` — ugyldige værdier afvises med 422 (`Literal`-typer på query-parametrene).
- Nye indexes på `year` og `rating` i `movies`-collectionen.
- Frontend: `Library.jsx` har fået en sortér-kontrol (felt + stigende/faldende) og en "Vis felter"-indstillingspanel (afkrydsning af År/Tags/Format/Lyd-type/Rating pr. filmkort), gemt i `localStorage` så valget huskes. Rating vises som badge på filmkort, i scan-kandidatlisten og i detalje-modalen.
- Pytest-suite udvidet med sortering (titel/år/serienr./rating, begge retninger) og ugyldig sort/direction-validering. 28/28 grønne. Live-verificeret mod ægte MongoDB + TMDb.

## [0.5.0 build 0005] — 2026-07-31 — Moderne redesign + film-detaljer/redigering

- `frontend/src/index.css`: nyt design-system — CSS custom properties for farver/radius/skygge, lys + mørk tilstand (inkl. `data-theme`-override), fjernet Vite-template-resterne (centreret `#root`, 56px-overskrifter, lilla accent).
- `frontend/src/App.jsx` + `App.css`: nyt app-shell med sticky header, brand-mærke, segmenteret fane-navigation. Delte UI-primitiver (`.btn`, `.card`, `.chip`, `.banner`) tilføjet til genbrug på tværs af sider.
- Ny genanvendelig komponent `frontend/src/components/Chip.jsx` til til/fra-valg (bruges til tag-/format-/lyd-type-filtre og -valg begge steder).
- `pages/Library.jsx` (+ `Library.css`) genskrevet: poster-grid med serienummer- og format-badges, filter-panel med chips for tags/format/lyd-type (hentet fra `/api/tags` og `/api/movies/attribute-options`), loading-skeletons, tomme/fejl-tilstande.
- **Ny**: klik på et filmkort åbner en detalje-modal (poster, plot, cast, genre) med redigering af tags/format/audio_types samt slet-knap — implementerer FEATURES.md #7 og #8 mod de eksisterende `PATCH`/`DELETE`-endpoints.
- `pages/ScanMovie.jsx` (+ `ScanMovie.css`) genskrevet: kandidat-valg er nu adskilt fra gem-trinnet — efter valg af TMDb-kandidat vises et review-skema hvor tags/format/lyd-type vælges *før* filmen gemmes (tidligere gemte "Bekræft" med det samme, uden mulighed for attributter).
- `scanner/BarcodeScanner.jsx` (+ `BarcodeScanner.css`): visuel "viewfinder" med hjørne-markører og scan-linje-animation i stedet for et nøgent `<video>`-element.
- `api/client.js`: `listMovies` understøtter nu `format`/`audioTypes`; ny `attributeOptions()`.
- Ingen backend-ændringer i denne commit — kun frontend. Build verificeret (`npm run build`), dev-server smoke-testet.

## [0.4.0 build 0004] — 2026-07-31 — Strukturerede attributter + auto-serienummer

- `backend/app/models/movie.py`: nye enums `MovieFormat` (VHS/DVD/Blu-ray/4K Ultra HD/Digital, étvalg) og `AudioType` (Stereo/Mono/Dolby Digital/Dolby Digital 5.1/Dolby Digital 7.1/DTS/DTS-HD Master Audio/Dolby Atmos/Dolby TrueHD, flervalg). Ugyldige værdier afvises med 422. `Movie` har nu `serial_number` (immutable, server-tildelt).
- `backend/app/repositories/movie_repository.py`: `next_serial_number()` — atomisk `$inc` mod en ny `counters`-collection (race-sikkert ved samtidige oprettelser). Nye indexes på `format`, `audio_types`, unique index på `serial_number`.
- `backend/app/services/movie_service.py`: `create_movie` tildeler serienummer og gemmer `format`/`audio_types`; `list_movies` og `update_movie` understøtter dem.
- `GET /api/movies` har nye query-params `?format=` og `?audio_types=` (kommasepareret, `$in`-match — "mindst én af"). Nyt endpoint `GET /api/movies/attribute-options` leverer de gyldige værdier til frontend-dropdowns.
- **Bugfix (se BUGS.md #1)**: film oprettet uden stregkode fik eksplicit `barcode: null` gemt i dokumentet, hvilket kolliderede med den sparse unique-index efter den *anden* stregkodeløse film (sparse index ekskluderer kun manglende felter, ikke `null`-værdier). Opdaget live mod ægte MongoDB — mongomock-testsuiten fangede det ikke. Rettet ved at udelade `barcode`-nøglen helt når den ikke er angivet; eksisterende data migreret.
- Pytest-suite udvidet med serienummer-, attribut-validering-, attribut-filtrering- og barcode-regressionstests. 22/22 grønne.
- `ARCHITECTURE.md` opdateret: endpoint-kontrakt, MongoDB-skema (`counters`-collection, nye indexes).

## [0.3.0 build 0003] — 2026-07-31 — Stregkode-scan → UPC-opslag → TMDb-match

- Tilføjet `backend/app/integrations/tmdb_client.py`: `search_movies()` (letvægts-kandidater til søgning) og `get_movie_details()` (fuld metadata + credits ved gem). Kaster `TmdbNotFoundError` (→ 404) og `TmdbUnavailableError` (→ 502, bl.a. ved manglende `TMDB_API_TOKEN`).
- Tilføjet `backend/app/integrations/upc_client.py`: UPCitemdb-opslag (trial-tier, ingen nøgle krævet). Fejler aldrig hardt — returnerer `None` ved intet match/timeout, jf. "nice-to-have, ikke kritisk sti" i MOVIE_API_REFERENCE.md. Renser producent-suffixe som "(DVD)"/"[Blu-ray]" fra titelgættet.
- Tilføjet `backend/app/services/scan_service.py`: orkestrerer UPC-opslag → TMDb-søgning.
- `backend/app/models/movie.py`: `MovieCreate` accepterer nu enten `tmdb_id` (backend henter fuld metadata server-side) eller en manuel `title` — valideret med en model-validator.
- `backend/app/services/movie_service.py`: `create_movie` henter fuld TMDb-metadata (titel, år, poster, plot, genrer, cast) når `tmdb_id` er angivet.
- Tilføjet `POST /api/scan/lookup` (`backend/app/api/scan.py`) og `GET /api/movies/tmdb-search` (registreret før `/{movie_id}` for ikke at blive skygget).
- Frontend: `ScanMovie.jsx` har nu en manuel TMDb-titel-søgning som fallback når stregkode-scan ikke giver match; `client.js` har fået `tmdbSearch()`.
- Pytest-suite udvidet med `tests/test_scan.py` (mocket TMDb/UPC via `monkeypatch`, ingen rigtige netværkskald i CI). 13/13 grønne.
- Live-verificeret mod ægte MongoDB og ægte UPCitemdb (rigtigt UPC-opslag lykkedes); TMDb-kaldene fejler pt. korrekt med 502 da `TMDB_API_TOKEN` endnu ikke er sat i `.env` — kræver at Jan opretter en gratis TMDb-konto/token.

## [0.2.0 build 0002] — 2026-07-31 — Film- og tag-CRUD

- Tilføjet `backend/app/models/movie.py`: Pydantic-modeller `Movie`, `MovieCreate`, `MovieUpdate`.
- Tilføjet `backend/app/repositories/movie_repository.py` og `tag_repository.py`: MongoDB-adgang via Motor, indexes (text-index på `title`+`overview`, index på `tags_normalized`, unique sparse index på `barcode`, unique index på `tags.normalized`).
- Tilføjet `backend/app/services/movie_service.py` og `tag_service.py`: forretningslogik, herunder tag-normalisering (trim+lowercase dedup, men bevarer først-indtastede casing på tværs af film — jf. CLAUDE.md regel 7).
- Tilføjet `backend/app/api/movies.py` (`GET/POST /api/movies`, `GET/PATCH/DELETE /api/movies/{id}`) og `tags.py` (`GET /api/tags`).
- Tilføjet `backend/app/core/errors.py`: `MovieNotFoundError` (→ 404) og `DuplicateBarcodeError` (→ 409), håndteret via exception-handlers i `main.py`.
- `main.py`: routere registreret, indexes oprettes ved app-start (lifespan).
- Tilføjet pytest-suite (`backend/tests/`) mod `mongomock_motor` — dækker CRUD, tag-dedup/casing, tag-filtrering, dublet-barcode. 7/7 grønne.
- `ARCHITECTURE.md` opdateret: endpoint-status, MongoDB-skema (`tags_normalized`), fjernet redundant `/api/search` (dækkes af `/api/movies?q=&tags=`).

## [0.1.0 build 0001] — 2026-07-31 — Projekt-scaffold

- Oprettet `CLAUDE.md` (system-prompt), `version.json`, `ARCHITECTURE.md`, `MOVIE_API_REFERENCE.md`, `TECH_REFERENCE.md`, `FEATURES.md`, `BUGS.md`, `RELEASE_NOTES.md`.
- Valgt stack: React (Vite, PWA) frontend, Python/FastAPI backend, MongoDB database.
- Valgt scan-flow: UPC/EAN-stregkode-scanning i browseren → UPC-opslag → TMDb-metadata-bekræftelse.
- Oprettet minimal backend-skelet (FastAPI + Motor + health-endpoint) og frontend-skelet (React/Vite PWA).
- Docker Compose-fil til backend + frontend + MongoDB.
- `.claude/settings.local.json` med læse/skrive-rettigheder til projektmappen.
