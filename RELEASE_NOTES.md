# Release Notes

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
