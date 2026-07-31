# Release Notes

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
