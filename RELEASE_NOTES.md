# Release Notes

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
