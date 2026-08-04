# Release Notes

## v0.56.0 (build 0075) — 2026-08-04

- Når du vælger en film/serie under scan eller søgning, springer du nu direkte til den samme fulde rediger-boks som når du redigerer et eksisterende kort — med overview, instruktør, medvirkende og alle felterne, ikke kun det begrænsede sæt fra før. Intet gemmes før du selv trykker "Opret".
- Indstillinger er delt op i faner (Brugere, Konto, Bibliotek, Backup & gendannelse, Eksterne API-nøgler, Drift) i stedet for én lang side — "Brugere" står først.
- Statistik viser nu hvilken stregkode-kilde der bruges mest (kun film/serier tilføjet via scan fremover). Ny indstilling i System-indstillinger lader dig vælge hvilken kilde der skal prøves først.

## v0.55.1 (build 0074) — 2026-08-04

- Audit-log i Indstillinger viser nu 10 ad gangen med rigtige "Forrige"/"Næste"-knapper, og dato/tid tydeligt hver for sig.

## v0.55.0 (build 0073) — 2026-08-04

- Ny "Test forbindelse"-knap ved hver API-nøgle i Indstillinger → System-indstillinger — viser om nøglen faktisk virker, ikke kun om den er gemt. Din UPCDatabase-nøgle var aldrig gemt under det rigtige felt (sandsynligvis indtastet i "UPC API-nøgle" ved en fejl) — det felt er nu fjernet, da det aldrig gjorde noget. Indtast din nøgle igen under "UPCDatabase-token".
- Tilføjet EAN-Search.org som en fjerde stregkode-kilde.

## v0.54.2 (build 0072) — 2026-08-03

- "Opdatér fra GitHub" viser nu en rolig "Allerede opdateret"-besked med det samme, hvis der intet nyt er at hente, i stedet for en alarmerende fejl efter to minutters ventetid. Kræver et lille manuelt trin på serveren, før den nye besked virker — spørg Claude når du er klar.

## v0.54.1 (build 0071) — 2026-08-03

- Fundet og rettet den rigtige årsag til sort skærm på iOS ved gem — den forrige rettelse ramte forbi. Test det gerne igen på din iPhone, men denne gang er fejlen faktisk genskabt og bekræftet rettet i test, ikke bare en teori.

## v0.54.0 (build 0070) — 2026-08-03

- Ny "TLS-certifikat"-sektion på Indstillinger (admin-only): forny produktionens HTTPS-certifikat direkte fra appen — generér en CSR til ekstern signering, eller importér en færdig PKCS12-fil — uden manuel SSH-adgang. Selve installationen kræver stadig dit eget password som bekræftelse, og de sidste systemd-brikker på serveren skal sættes op manuelt én gang, før knappen kan bruges i produktion.

## v0.53.5 (build 0069) — 2026-08-03

- Forsøgt rettelse af sort skærm på iOS efter at have gemt en scannet film — test det gerne på din iPhone og sig til om det stadig sker.

## v0.53.4 (build 0068) — 2026-08-03

- Bedre logging af stregkode-opslag, så vi hurtigere kan se hvorfor et scan ikke fandt noget. Vigtigt: UPCDatabase-nøglen (den tredje opslags-kilde) mangler stadig at blive sat i produktion — tilføj den under Indstillinger → System-indstillinger.

## v0.53.3 (build 0067) — 2026-08-03

- Voldby BIO's offentlige side har fået et federe, farverigt banner, og dato/tid står nu tydeligt ovenover hver film i stedet for som et overlay.
- Guest-konti kan nu sende en "Ønsk visning i Voldby BIO"-anmodning for film/serier i biblioteket. Fixet: guest-konti viste fejlagtigt "Standard" i stedet for "Guest" under Konto på Indstillinger.

## v0.53.2 (build 0066) — 2026-08-03

- Voldby BIO's offentlige side: alle kommende visninger står nu side om side i et gitter (i stedet for en lang liste), og "Om Voldby BIO" er tilbage øverst.

## v0.53.1 (build 0065) — 2026-08-03

- Voldby BIO's offentlige side (`/bio`) har fået en tydelig overskrift, og viser nu programmet ("Hvad går i bio") øverst, med info om biografen ("Om Voldby BIO") nedenunder.

## v0.53.0 (build 0064) — 2026-08-03

- Nye film og TV-serier får nu automatisk et "Tilføjet af {dit brugernavn}"-tag — gør det nemt at filtrere biblioteket efter hvem der har tilføjet hvad.

## v0.52.0 (build 0063) — 2026-08-03

- Ny bruger-rolle: "Guest" (read-only) — kan se film-/TV-biblioteket og Voldby BIO, men ikke redigere noget. Sættes fra rolle-dropdown'en i Brugere-listen på Indstillinger.

## v0.51.0 (build 0062) — 2026-08-03

- Voldby BIO har nu en offentlig side på `/bio` du kan dele med andre (fx i en besked) — ingen login krævet, viser kun programmet + billeder/info om biografen. Find "🔗 Del link"-knappen på Voldby BIO-fanen.

## v0.50.0 (build 0061) — 2026-08-03

- Film- og TV-serie-biblioteket er nu pagineret — vælg hvor mange der vises pr. side, og bladr med Forrige/Næste. Fjerner samtidig et skjult loft på 500 film/serier.

## v0.49.0 (build 0060) — 2026-08-03

- Ny "Nulstil database"-knap under Indstillinger (kun admin) — tømmer film-/TV-biblioteket helt. Bekræftes med din adgangskode. Brugerkonti og system-indstillinger rører den ikke.

## v0.48.0 (build 0059) — 2026-08-03

- Nye brugere skal nu godkendes af en admin før de får adgang (Indstillinger → Brugere). Din egen konto er upåvirket.

## v0.47.0 (build 0058) — 2026-08-03

- Ny "Audit-log" under Indstillinger (kun admin): se hvem der har ændret roller, opdateret system-nøgler, udløst en opdatering, taget/gendannet backup, eller planlagt/afvist en Voldby BIO-visning — og hvornår.

## v0.46.0 (build 0057) — 2026-08-03

- Gem/slet-knapperne i film-/TV-seriens redigeringsvindue er nu altid synlige — ikke kun når du har scrollet helt ned.

## v0.45.0 (build 0056) — 2026-08-03

- "Føj til hjemmeskærm" på iPhone giver nu et rigtigt app-ikon i stedet for et tilfældigt skærmbillede af siden.

## v0.44.0 (build 0055) — 2026-08-03

- Stregkode-scanning har fået en ekstra, gratis opslags-kilde (UPCDatabase.org) som forsøges hvis de to andre ikke finder et match — kan forbedre chancen for at finde nordiske/danske DVD-covers. Konfigureres under Indstillinger ligesom de andre API-nøgler.

## v0.43.0 (build 0054) — 2026-08-03

- Ny fane: **🎬 Voldby BIO**! Ønsk en film eller TV-serie vist ved at trykke "Ønsk visning i Voldby BIO" i dens detaljevindue. Admin kan derefter planlægge dato/tid for de ønskede titler (eller tilføje en visning direkte), hvorefter den dukker op på Voldby BIO-siden for alle — med poster, plot, trailer-link og tidspunkt, ligesom en rigtig biograf-forside.

## v0.42.0 (build 0053) — 2026-08-03

- To nye admin-værktøjer under Indstillinger: "Bibliotek-eksport / -gendannelse" (hent hele film-/TV-biblioteket som en JSON-fil, eller gendan fra en tidligere fil) og "Fuld system-backup" (backup/gendan hele systemet — undtagen dine API-nøgler, som skal genindtastes manuelt bagefter). Begge kræver at du skriver en bekræftelsesfrase for at forhindre uheld.

## v0.41.1 (build 0052) — 2026-08-03

- Fix: sæson-badgen ("1/5 sæsoner") på TV-kortet sad forkert ved siden af skift til lille eller stor kortstørrelse — sidder nu konsekvent i højre hjørne uanset kortstørrelse.

## v0.41.0 (build 0051) — 2026-08-03

- Tags-, lokations- og ejer-felterne (ved tilføjelse og redigering af film/TV-serier) viser nu forslag ud fra hvad du allerede har brugt — men du kan stadig bare skrive noget nyt. Virker også fra telefonen.
- Ny indstilling under Indstillinger: "Kortstørrelse" (Lille/Mellem/Stor) — styrer hvor store film-/TV-serie-kortene vises i biblioteket, på begge faner.

## v0.40.0 (build 0050) — 2026-08-02

- Ny "TMDb-synkronisering"-knap for TV-serier under Indstillinger (admin) — akkurat som filmenes, henter frisk metadata (navn, status, poster, plot, rating, sæson-/episodetal) for alle TV-serier oprettet via TMDb. Dine egne sæson-/episode-markeringer (ejet/set) rører den ikke.
- Sæson-/episode-fejl i TV-serier viser nu en rigtig fejlbesked i stedet for bare at hoppe tilbage uden forklaring, og TV-kortets sæson-badge opdateres straks når du ændrer hvilke sæsoner du ejer.
- Fejl ved sletning af en film eller TV-serie viser nu en fejlbesked i stedet for at fejle stille.
- Ramte TMDb et rate-limit midt i et opslag, fik du tidligere en uforklarlig serverfejl — nu en klar besked om at prøve igen om lidt.
- Mindre robusthedsrettelser under motorhjelmen (ingen synlig ændring i det daglige): oprettelse af en ny TV-serie med valgte sæsoner er nu én sammenhængende handling i stedet for flere, så en fejl undervejs ikke kan give en dublet-serie ved et nyt forsøg.

## v0.39.1 (build 0049) — 2026-08-02

- Lille justering: sæson-badgen ("2/6 sæsoner") på TV-kort sidder nu lidt længere til højre, så den passer bedre sammen med rating-badgen.

## v0.39.0 (build 0048) — 2026-08-02

- Når du opretter en helt ny TV-serie via scan/søgning, kan du nu vælge hvilke sæsoner udgaven indeholder direkte i tilføj-formularen, før du gemmer — de markeres automatisk som ejet med det samme. Samme sæson-vælger (både ved ny serie og ved gruppering på en eksisterende serie) understøtter nu også at vælge flere sæsoner på én gang.
- TV-seriekort viser nu et lille "2/6 sæsoner"-badge med hvor mange sæsoner du ejer ud af seriens samlede antal.
- Print-siden har nu også en separat tabel for TV-serier, ud over filmtabellen.

## v0.38.0 (build 0047) — 2026-08-02

- Scanner du en ny sæson af en TV-serie du allerede har (fx "The Americans" sæson 2), foreslår appen nu at føje den til den eksisterende serie i stedet for at oprette en ny separat post — vælg bare den rigtige sæson i det nye panel, der dukker op. Serien viser derefter alle dine ejede sæsoner ét sted.

## v0.37.0 (build 0046) — 2026-08-02

- Den separate "Scan"-fane er væk — hver fane (Film/TV-serier) har nu sit eget "+ Tilføj film"/"+ Tilføj serie"-panel med samme scan-/søgefunktion som før, bare ét sted.
- TV-serie-fanen har nu samme sortering (op til 3 niveauer), "gemte visninger" og "Vis felter"-panel som filmbiblioteket — samme udseende og funktioner på tværs af de to faner.
- Fix: "Medietype"-visningen i "Vis felter"-panelet blev ikke husket ved genindlæsning — er nu rettet.

## v0.36.1 (build 0045) — 2026-08-02

- Fix: login fra telefonen fejlede med "forkert brugernavn/adgangskode" selvom det var korrekt — telefonen (iOS) autokapitaliserede stille og roligt det første bogstav i brugernavnet, mens login krævede eksakt store/små bogstaver. Login tjekker nu ikke længere store/små bogstaver i brugernavnet, så det ikke sker igen.

## v0.36.0 (build 0044) — 2026-08-02

- **Ny "TV-serier"-fane!** Katalogisér TV-serier helt som film — scan et cover eller søg manuelt, sæt tags/format/lokation. Nyt: markér hvilke sæsoner du ejer, og hvilke episoder du har set, med dato. Scan og manuel søgning finder nu automatisk både film og TV-serier og foreslår det rigtige sted at gemme.
- Appen hedder nu "Film & TV-bibliotek" i stedet for "Filmbibliotek", og "Bibliotek"-fanen er omdøbt til "Film" for at gøre plads til den nye TV-fane.
- **Bemærk**: TV-serier har endnu ikke alle filmbibliotekets ekstra-funktioner (fler-niveau sortering/gemte visninger, skuespiller-browsing, Plex, statistik) — det kan komme senere.

## v0.35.1 (build 0043) — 2026-08-02

- Endnu et skridt mod TV-serie-understøttelse (teknisk, ikke synligt i UI'et endnu): stregkode-scanning kan nu genkende TV-serier, ikke kun film.

## v0.35.0 (build 0042) — 2026-08-02

- Første skridt mod TV-serie-understøttelse: teknisk fundament på plads (egen ressource, sæson/episode-sporing). Endnu ingen synlig knap/fane i appen — det kommer i en efterfølgende opdatering.

## v0.34.1 (build 0041) — 2026-08-02

- Fix: forbedret oprensning af titler fra stregkode-opslag før TMDb-søgning — flere "special edition"/"complete series"/rå "DVD"/"Blu-ray"-tilføjelser i produktnavnet fjernes nu, hvilket burde give flere match for rigtige film.

## v0.34.0 (build 0040) — 2026-08-02

- Ny funktion: filmens rating viser nu den faktiske IMDb-rating (kræver egen gratis OMDb-nøgle under Indstillinger → System-indstillinger) i stedet for TMDb's egen rating. Uden nøgle sat virker alt som før.

## v0.33.1 (build 0039) — 2026-08-02

- Fix: kamera-scanning af stregkoder skulle nu finde markant flere matches. Scanneren forsøgte tidligere at læse alle mulige stregkode-typer (også dem der aldrig forekommer på film) i stedet for kun de to relevante — det kunne i sjældne tilfælde få den til at læse et forkert tal på et cover med flere stregkoder/meget grafik.

## v0.33.0 (build 0038) — 2026-08-01

- Ny Plex-integration: filmens detaljevindue kan nu tjekke om filmen er tilgængelig på din egen Plex-server, med et direkte "Afspil i Plex"-link hvis den er. Kræver at Plex-server-URL og -token sættes under Indstillinger → System-indstillinger (admin). **Bemærk**: endnu ikke afprøvet mod en rigtig Plex-server — sig til hvis noget ikke matcher korrekt, så kan det justeres.

## v0.32.0 (build 0037) — 2026-08-01

- Gemte visninger husker nu søgetekst og alle filtre (tags/format/lyd/medietype/set-status), ikke kun sorteringen — så en gemt visning genskaber præcis den samme liste du havde, ikke bare rækkefølgen.

## v0.31.0 (build 0036) — 2026-08-01

- Ny "Statistik"-fane: antal film, samlet spilletid, hvor mange du har set, samt fordeling på genre/årti/format og hvilke instruktører/skuespillere der går igen i din samling.

## v0.30.0 (build 0035) — 2026-08-01

- Film der er del af en filmserie/franchise (fx en trilogi) viser nu det i detaljevinduet, sammen med hvor mange af filmene i serien du allerede ejer — og en "+ Tilføj"-knap til at hente de manglende.

## v0.29.0 (build 0034) — 2026-08-01

- Skuespillere og instruktør i filmens detaljevindue er nu klikbare — klik for at se andre film i din samling med samme person.

## v0.28.0 (build 0033) — 2026-08-01

- Kan nu markere film som "set" med en dato — vises som badge på filmkortet, kan filtreres og sorteres på. Praktisk til at holde styr på hvad I allerede har set.

## v0.27.0 (build 0032) — 2026-08-01

- Kan nu give hver film din egen rating (1-10) og skrive en personlig note, uafhængigt af TMDb's rating — rediger i filmens detaljevindue. Kan også sorteres efter.

## v0.26.0 (build 0031) — 2026-08-01

- Ny advarsel når du vælger en film der allerede findes i biblioteket eller på ønskelisten — praktisk hvis du er i tvivl om du allerede har scannet den. Du kan stadig tilføje den igen, fx hvis du ejer flere kopier.

## v0.25.0 (build 0030) — 2026-08-01

- Kan nu indtaste en stregkode manuelt (i stedet for kun at scanne med kameraet) på både "Scan film"-siden og ønskelistens "+ Tilføj ønske"-panel — praktisk hvis kameraet driller eller en kode er svær at scanne.

## v0.24.0 (build 0029) — 2026-08-01

- Ny "System-indstillinger" på Indstillinger-siden (kun admin): TMDb-, UPC- og Discogs-nøgler kan nu skrives ind og opdateres direkte i appen, i stedet for at kræve SSH-adgang til serveren. Af sikkerhedshensyn vises en gemt nøgle aldrig igen bagefter — kun om der er sat en, og hvorfra (server-opsætning eller her i UI'et).

## v0.23.1 (build 0028) — 2026-08-01

- Fix: "Opdatér fra GitHub"-knappen gav en fejl (500) ved det første rigtige forsøg — en genstart-mekanisme på serveren var ikke sat helt korrekt op. Rettet og grundigt efterprøvet; knappen skulle nu virke som forventet.

## v0.23.0 (build 0027) — 2026-08-01

- Ny "Opdatér fra GitHub"-knap på Indstillinger (kun synlig/virker for admin): henter og installerer den nyeste version direkte fra serveren, uden at du skal logge ind via SSH selv. Kun relevant i produktion.

## v0.22.1 (build 0026) — 2026-08-01

- Fulgt op på den kode-gennemgang du bad om tidligere: TMDb-synkroniseringen håndterer nu manglende API-nøgle og TMDb-rate-limits pænt (én klar besked i stedet for en lang liste af "mislykkede" film), og en sjælden fejlkilde i trailer-links er rettet.

## v0.22.0 (build 0025) — 2026-08-01

- Ny "Medietype"-mulighed (Fysisk/Digital) du kan sætte på hver film — filtrerbar og sorterbar som format og lyd-type.
- Format- og lyd-type-navne er gjort kortere (fx "Blu-ray" hedder nu "BD", "Dolby Digital 5.1" hedder nu "DD5.1", "4K Ultra HD" hedder nu "UHD") — dine eksisterende film er automatisk opdateret til de nye navne. "Digital" er desuden delt op i tre kvalitetsniveauer (Digital-UHD/Digital-HD/Digital-STD) — dine gamle "Digital"-film er sat til "Digital-HD" som udgangspunkt; ret dem manuelt hvis en anden kvalitet passer bedre.
- Sortering: "Serienummer" og "Tilføjet" er nu to rigtige, adskilte muligheder (før delte de fejlagtigt værdi). Du kan nu også sortere efter spilletid, lokation, ejer og hvem der registrerede filmen.

## v0.21.0 (build 0024) — 2026-08-01

- Filmens detaljevindue viser nu links til IMDb, en YouTube-trailer (når TMDb har en) og filmens TMDb-side.
- Ny knap på Indstillinger under "TMDb-synkronisering": henter frisk metadata fra TMDb for alle dine film på én gang — praktisk hvis en poster, et plot eller en rating er blevet rettet på TMDb siden du tilføjede filmen. Dine egne oplysninger (tags, format, lokation osv.) røres ikke.

## v0.20.0 (build 0023) — 2026-08-01

- Fik du fat i en film der stod på din ønskeliste? Åbn den og tryk "Flyt til bibliotek" — den får automatisk et rigtigt serienummer og flyttes over i filmbiblioteket.

## v0.19.0 (build 0022) — 2026-08-01

- Ønskelisten har nu sin egen "+ Tilføj ønske"-knap der åbner præcis samme scan/søge-metode som "Scan film"-siden (barcode-scan eller TMDb-søgning) — direkte inde i Ønsker-fanen, i stedet for at skulle huske en afkrydsningsboks på Scan film-siden.

## v0.18.1 (build 0021) — 2026-08-01

- Rettet: gemte sorterings-presets kunne i sjældne tilfælde forsvinde igen kort efter du gemte dem (hvis du nåede at ændre noget andet i sorteringen lige efter). De gemmes nu pålideligt.

## v0.18.0 (build 0020) — 2026-08-01

- Ny fane "Ønsker": en ønskeliste med samme søgning/filtrering/sortering som filmbiblioteket, men uden serienummer — til film du gerne vil have, men ikke ejer endnu.
- Når du scanner eller søger en film op, kan du nu krydse af "Tilføj til ønskeliste i stedet for biblioteket".

## v0.17.0 (build 0019) — 2026-08-01

- Sortering i biblioteket understøtter nu op til 3 niveauer ad gangen (fx: format → lyd-type → titel) — klik "Sortér ▾" for at tilføje/fjerne niveauer.
- Du kan gemme en sorterings-kombination som et navngivet preset og hurtigt vælge det igen fra en dropdown, i stedet for at skulle stille alle niveauerne op igen hver gang.

## v0.16.0 (build 0018) — 2026-08-01

- Stregkode-scanning fandt ofte intet match — det var ikke en fejl, men fordi den hidtidige opslagstjeneste (UPCitemdb) er amerikansk-centreret og ofte ikke kender europæiske stregkoder på film. Appen prøver nu automatisk **Discogs** som ekstra kilde, hvis den første ikke finder noget — bedre chance for at ramme danske/europæiske udgivelser.

## v0.15.0 (build 0017) — 2026-08-01

- Sletter du en film forsvinder den ikke bare — den logges nu i en ny liste under Indstillinger ("Slettede film") med serienummer, titel, hvornår og hvem der slettede den. Serienummeret bliver automatisk frit til en ny film bagefter.

## v0.14.0 (build 0016) — 2026-08-01

- Ny fane "Print": en kompakt, print-venlig liste over hele filmsamlingen (serienr., titel, år, format, lokation), én linje pr. film. Tryk "🖨️ Print" for at udskrive.

## v0.13.0 (build 0015) — 2026-08-01

- Når du scanner/registrerer en film kan du nu angive **lokation** (fx "Stue, reol 2") og **ejer** (forudfyldt med dig selv, men kan ændres) — og appen husker automatisk hvem der registrerede filmen.
- Serienummeret på en film kan fremover kun ændres af en administrator, eller af den person der oprindeligt registrerede den pågældende film. Andre brugere kan stadig se serienummeret, bare ikke ændre det.

## v0.12.0 (build 0014) — 2026-08-01

- Du kan nu se hvilken version af appen der kører nederst på siden.
- Filmkort kan nu vise spilletid (minutter), og de valgte felter (år/format/lyd/spilletid) fylder mindre — de vises nu i to kolonner i stedet for én lang liste.
- Sortering og filtrering (tags/format/lyd) er nu skjult bag "Sortér ▾"/"Filtrér ▾"-knapper, samme måde som "Vis felter" allerede virkede — mindre rod i toolbaren, men alt er der stadig ét klik væk.

## v0.11.1 (build 0013) — 2026-08-01

Rettet 10 fejl fundet ved en systematisk kode-gennemgang (se BUGS.md #3-12). Ingen af dem var noget du havde oplevet endnu, men bl.a.:
- Man kan ikke længere komme til at fjerne den sidste administrator ved et uheld.
- Fejlbeskeder ved scan-gem og bruger-rolle-ændring viser nu den rigtige årsag i stedet for en generisk besked.
- En sjælden race condition der kunne crashe et gem ved et helt nyt tag er rettet.
- En film med TMDb-rating på præcis 0.0 vises nu korrekt i stedet for "ingen rating".

## v0.11.0 (build 0012) — 2026-08-01

- Du kan nu åbne appen fra din telefon på samme netværk: **https://10.1.1.72:5173/**. Telefonens browser advarer om at certifikatet ikke er "betroet" (fordi det er selvsigneret) — vælg "Avanceret"/"Fortsæt alligevel", det er sikkert på jeres eget netværk.
- Hele sitet er gjort mere mobilvenligt: navigationen stables ordentligt på smalle skærme, filmkortene tilpasser sig skærmbredden, og film-detaljevinduet fylder næsten hele skærmen på telefonen i stedet for at være en lille boks.

## v0.10.0 (build 0011) — 2026-08-01

- Din konto ("jan") er nu **administrator** — det sker automatisk for den første bruger i systemet.
- Ny mulighed for at **skifte adgangskode** på Indstillinger-siden.
- Kun administratorer kan ændre serienummer-opsætningen fremover (alle kan stadig se den).
- Administratorer har fået en "Brugere"-oversigt på Indstillinger-siden, hvor man kan gøre andre brugere til admin (eller fjerne admin-rettigheder igen).

## v0.9.0 (build 0010) — 2026-08-01

Justering af gårsdagens Settings-side: at rette én bestemt films serienummer gør du nu i filmens redigeringsvindue i biblioteket (sammen med tags/format/lyd), ikke på Settings-siden. Settings-siden har i stedet fået en "Serienummer-opsætning" hvor du styrer selve nummereringen: hvilket nummer den næste tilføjede film får, hvor stort et spring der er mellem numre, og om numrene skal vises med foranstillede nuller (fx "00007").

## v0.8.0 (build 0009) — 2026-08-01

Ny **Indstillinger**-fane: her kan du rette en films serienummer for at omorganisere biblioteket. Sætter du et nummer der allerede er i brug af en anden film, bytter de to film automatisk plads — ingen numre går tabt eller duplikeres.

## v0.7.0 (build 0008) — 2026-08-01

- Appen kræver nu **login**. Alle kan oprette en konto (brugernavn + adgangskode) — I deler stadig ét fælles filmbibliotek, men jeres personlige indstillinger for sortering og hvilke felter der vises på filmkort huskes nu pr. bruger (i stedet for kun i den ene browser du sad i).
- Ny "Log ud"-knap i toppen.

**Vigtigt for dig, Jan**: næste gang du åbner appen skal du oprette en konto (eller logge ind, hvis du allerede har en) — appen viser nu en login-side i stedet for biblioteket, indtil du er logget ind.

## v0.6.1 (build 0007) — 2026-08-01

Rettet: serienummer- og format-mærkaterne på filmkort i biblioteket var utilsigtet skjult bag poster-billedet (regression fra v0.6.0's rating-badge). De vises nu korrekt igen.

## v0.6.0 (build 0006) — 2026-07-31

- Film får nu automatisk en **rating** (TMDb's egen bedømmelse, 0-10) når de oprettes via TMDb — bemærk at dette ikke er den faktiske IMDb-rating (se `MOVIE_API_REFERENCE.md` hvis I senere ønsker rigtig IMDb-data via OMDb).
- Biblioteket kan nu **sorteres**: Titel, År, Tilføjet eller Rating, stigende eller faldende.
- Ny **"Vis felter"**-knap lader dig selv vælge hvilke oplysninger der vises under hver films ikon (År, Tags, Format, Lyd-type, Rating) — valget huskes i din browser.

## v0.5.0 (build 0005) — 2026-07-31

Nyt udseende og nye måder at bruge biblioteket på:
- Hele appen har fået et gennemgående moderne design (lys/mørk tilstand), i stedet for Vite-standardskabelonen.
- Klik på en film i biblioteket for at se detaljer (plot, cast, genre) og redigere tags/format/lyd-type — eller slette filmen.
- Biblioteket kan nu filtreres med klikbare chips for tags, format og lyd-type, ikke kun fritekst-søgning.
- Ved scan/manuel søgning vælger du nu tags, format og lyd-type *før* filmen gemmes, i stedet for at den blev gemt med det samme ved bekræftelse.
- Kameraet vises nu i en tydelig "viewfinder" med sigtemærker, så det er klart hvornår scanning er aktiv.

## v0.4.0 (build 0004) — 2026-07-31

Hver film kan nu få strukturerede attributter ud over frie tags:
- **Format** (vælg én): VHS, DVD, Blu-ray, 4K Ultra HD eller Digital.
- **Lyd-type** (vælg flere): Stereo, Mono, Dolby Digital (5.1/7.1), DTS, DTS-HD Master Audio, Dolby Atmos, Dolby TrueHD.
- Hver film får automatisk et fortløbende **serienummer** (1, 2, 3, ...) den dag den oprettes — kan ikke ændres bagefter.
- Biblioteket kan filtreres på format og lyd-type, ud over eksisterende tekst- og tag-søgning.

**Fejlrettelse**: en fejl der forhindrede oprettelse af mere end én film uden stregkode er rettet (se BUGS.md #1) — opdaget under test af denne funktion mod den rigtige database.

## v0.3.0 (build 0003) — 2026-07-31

Stregkode-scanning virker nu hele vejen igennem:
- Scan et cover → koden slås op i en gratis UPC-database for et titel-gæt → titlen søges automatisk på TMDb → du bekræfter det rigtige match → filmen gemmes med fuld metadata (poster, plot, genre, skuespillere).
- Intet match ved scan? Der er nu en manuel søgeboks på Scan-siden, der søger direkte på TMDb på titel.

**Kræver opsætning før det virker fuldt ud**: du skal selv oprette en gratis TMDb-konto og lægge en API-token i `backend/.env` (`TMDB_API_TOKEN`) — uden den svarer TMDb-relaterede kald med en tydelig fejl i stedet for at crashe. Se `MOVIE_API_REFERENCE.md`.

## v0.2.0 (build 0002) — 2026-07-31

Filmbiblioteket kan nu bruges rigtigt mod databasen:
- Opret, hent, opdatér og slet film via API'et.
- Tildel frie tags til film — samme tag genkendes uanset store/små bogstaver, og genbruger den formatering du skrev første gang.
- Bibliotek-siden i frontend kan nu reelt vise, søge og filtrere film (kræver at backend kører mod en rigtig MongoDB — se `TECH_REFERENCE.md` for opsætning uden Docker).

Stregkode-scanning i appen finder stadig kun koden — selve UPC/TMDb-opslaget (feature #4) er endnu ikke implementeret.

## v0.1.0 (build 0001) — 2026-07-31

Første scaffold af Movie Database App. Ingen brugervendte features endnu — dette er grundstrukturen (dokumentation, backend- og frontend-skelet, deployment-opsætning) som features bygges oven på.
