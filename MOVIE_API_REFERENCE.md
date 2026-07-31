# Film- & Stregkode-API Reference

Konsulteres ved al integration med eksterne film-/stregkode-API'er (jf. CLAUDE.md regel 9). Hold denne fil opdateret med nye fund (rate-limits, quirks, fejlkoder).

---

## TMDb (The Movie Database)

- **Base URL**: `https://api.themoviedb.org/3`
- **Auth**: Bearer-token (API Read Access Token, v4-auth) i `Authorization: Bearer <token>` header. Alternativt API-nøgle som query-param (`?api_key=`) på v3-endpoints — brug Bearer-metoden, den er nyere og anbefalet.
- **Nøgle opbevares**: `backend/.env` som `TMDB_API_TOKEN`. Hentes gratis på https://www.themoviedb.org/settings/api (kræver konto).
- **Rate limit**: Ingen hård grænse dokumenteret pr. sekund længere (tidligere ~40 req/10s), men vær nænsom og cache resultater i MongoDB.

### Relevante endpoints
| Endpoint                          | Brug                                             |
|------------------------------------|----------------------------------------------------|
| `GET /search/movie?query=<titel>`    | Fritekst-søgning på titel → liste af kandidater      |
| `GET /movie/{id}`                    | Fuld detalje for én film (overview, genres, release_date) |
| `GET /movie/{id}/credits`            | Cast/crew                                             |
| Billeder                             | Poster-path fra søge/detalje-svar kombineres med image base URL: `https://image.tmdb.org/t/p/w500{poster_path}` |

### Felt-mapping til vores `movies`-collection
| TMDb-felt         | Vores felt      |
|--------------------|------------------|
| `id`                | `tmdb_id`        |
| `title`             | `title`          |
| `release_date`      | `year` (parses år ud) |
| `overview`          | `overview`       |
| `genre_ids` → navne | `genres`         |
| `poster_path`       | `poster_url` (præfikset med image base URL) |
| `credits.cast[0..N]`| `cast`           |

### Fejlhåndtering
- Tomt `results[]` ved søgning → vis "ingen match, prøv en anden titel" i frontend, tilbyd manuel indtastning.
- HTTP 401 → ugyldig/manglende token, log som konfigurationsfejl (ikke bruger-fejl).
- HTTP 429 → backoff og retry (se `TECH_REFERENCE.md` for retry-strategi i `integrations/tmdb_client.py`).

---

## UPC-opslagstjeneste (stregkode → produkt/titel)

> **TODO ved implementering**: Vælg og opret konto hos en konkret udbyder. Anbefalet startpunkt er **UPCitemdb** (gratis "trial" tier, ingen kreditkort krævet, ~100 opslag/dag), men skift frit hvis en anden udbyder (fx Barcode Lookup, Barcodable) passer bedre. Uanset udbyder skal integrationen isoleres i `backend/app/integrations/upc_client.py` så udbyderen kan skiftes uden at røre service-laget.

### UPCitemdb (foreløbig reference)
- **Base URL**: `https://api.upcitemdb.com/prod/trial/lookup`
- **Auth**: ingen nøgle krævet på trial-tier, men rate-limited pr. IP (~100/dag). Produktions-tier kræver `user_key` + `key_type` headers.
- **Request**: `GET ?upc=<stregkode>`
- **Response**: `items[]` med bl.a. `title`, `brand`, `images[]`. Titel bruges som gæt til efterfølgende TMDb-søgning — brand/model-navne på DVD-covers er ofte ikke rene filmtitler, så forvent at skulle rense/forkorte strengen (fx fjern "(DVD)", "[Blu-ray]", årstal i parentes) før TMDb-søgning.

### Fejlhåndtering
- `code: "INVALID_UPC"` eller tomt `items[]` → intet gæt, frontend falder tilbage til manuel TMDb-søgning (se `/api/movies/tmdb-search` i ARCHITECTURE.md).
- Rate-limit ramt → log som warning, returnér "intet gæt" til frontend i stedet for at fejle hele scan-flowet (UPC-opslag er et *nice-to-have* forudfyld, ikke en kritisk sti).

---

## Stregkode-formater i praksis

- DVD/Blu-ray-covers i EU/DK bruger typisk **EAN-13**. Amerikanske udgivelser bruger ofte **UPC-A** (12 cifre) — EAN-13 er et superset (UPC-A = EAN-13 med et foranstillet 0), så samme lookup-flow håndterer begge hvis stregkode-detection-biblioteket understøtter begge formater (se TECH_REFERENCE.md).
