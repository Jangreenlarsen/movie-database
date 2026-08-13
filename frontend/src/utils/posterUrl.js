// Feature #143 — poster-optimering. TMDb-postere gemmes altid i `w500`
// (backendens `tmdb_client.IMAGE_BASE_URL`), men vises mange steder småt (kort,
// thumbnails). Ved at hente en mindre TMDb-størrelse dér loader siden hurtigere,
// fordi hvert billede er færre kilobytes. Kun rigtige TMDb-billed-URL'er
// omskrives; en null-værdi eller en manuelt angivet poster-URL røres ikke.
const TMDB_POSTER_RE = /(https:\/\/image\.tmdb\.org\/t\/p\/)w\d+(\/)/;

/**
 * Returnér `url` med TMDb-størrelses-segmentet skiftet til `size`
 * (fx "w185"/"w342"/"w500"). Ikke-TMDb-URL'er og null returneres uændret.
 */
export function posterSrc(url, size = "w342") {
  if (!url) return url;
  return url.replace(TMDB_POSTER_RE, `$1${size}$2`);
}

// Kort-størrelse (feature #59) → passende TMDb-bredde. Valgt så billedet er
// skarpt nok ved kortets faktiske pixelbredde (også på 2x-skærme) uden at hente
// den store w500 til et lille kort.
const CARD_SIZE_TO_TMDB = { small: "w185", medium: "w342", large: "w500" };

export function cardPosterSize(cardSize) {
  return CARD_SIZE_TO_TMDB[cardSize] ?? "w342";
}
