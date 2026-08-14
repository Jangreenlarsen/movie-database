// Feature #153 — permanent poster-cache. Postere blev tidligere hentet
// direkte fra TMDb's CDN (image.tmdb.org) i browseren, hver gang — appen
// mistede derfor ALLE billeder så snart serveren ikke selv havde
// internetadgang, selvom resten af appen (kun den lokale MongoDB) virkede
// fint. `posterSrc` peger nu i stedet på vores egen backend
// (`/api/posters/{size}/{path}`), som cacher billedet permanent i MongoDB
// første gang det efterspørges — se `poster_cache_service.py`.
const TMDB_POSTER_RE = /^https:\/\/image\.tmdb\.org\/t\/p\/w\d+\/(.+)$/;

/**
 * Returnér en poster-URL i størrelsen `size` (fx "w185"/"w342"/"w500").
 * En rigtig TMDb-URL omskrives til vores egen cache-endpoint; en manuelt
 * angivet (ikke-TMDb) poster-URL og null/undefined røres ikke.
 */
export function posterSrc(url, size = "w342") {
  if (!url) return url;
  const match = url.match(TMDB_POSTER_RE);
  if (!match) return url;
  return `/api/posters/${size}/${match[1]}`;
}

// Kort-størrelse (feature #59) → passende TMDb-bredde. Valgt så billedet er
// skarpt nok ved kortets faktiske pixelbredde (også på 2x-skærme) uden at hente
// den store w500 til et lille kort.
const CARD_SIZE_TO_TMDB = { small: "w185", medium: "w342", large: "w500" };

export function cardPosterSize(cardSize) {
  return CARD_SIZE_TO_TMDB[cardSize] ?? "w342";
}
