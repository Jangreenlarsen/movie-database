/**
 * Serienummer-visning (feature #92, udvidet i #93).
 *
 * Lå tidligere som tre identiske `formatSerial`-kopier i Library.jsx,
 * TvShows.jsx og PrintList.jsx, som allerede var begyndt at drive fra
 * hinanden (kun PrintList håndterede et manglende nummer).
 *
 * Tre serier tælles hver for sig i backenden, og præfikset er det der gør
 * dem til at skelne på en hylde:
 *
 *   M  fysiske film        (movie_serial-tælleren)
 *   T  fysiske TV-serier   (tv_show_serial-tælleren)
 *   D  alle digitale       (digital_serial-tælleren, delt mellem film og
 *                           serier — så et D-nummer altid peger på præcis
 *                           én ting, Jans valg 2026-08-08)
 *
 * Uden `#` (Jans ønske 2026-08-08): M0042 er film nr. 42.
 */

export const MOVIE_SERIAL_PREFIX = "M";
export const TV_SERIAL_PREFIX = "T";
export const DIGITAL_SERIAL_PREFIX = "D";

const DIGITAL_MEDIA_TYPE = "Digital";

/**
 * Præfikset for én post. Medietypen vinder over ressourcen, fordi den
 * digitale serie går på tværs af film og serier.
 *
 * @param mediaType postens `media_type` ("Fysisk"/"Digital"/tom)
 * @param kind "movie" eller "tv" — afgør kun den fysiske serie
 */
export function serialPrefix(mediaType, kind) {
  if (mediaType === DIGITAL_MEDIA_TYPE) return DIGITAL_SERIAL_PREFIX;
  return kind === "tv" ? TV_SERIAL_PREFIX : MOVIE_SERIAL_PREFIX;
}

/**
 * @param serialNumber tallet, eller null/undefined for en post uden nummer
 *   (ønskelisten nummereres ikke)
 * @param paddingWidth antal foranstillede nuller, fra serienummer-opsætningen
 * @param prefix fra `serialPrefix()`
 */
export function formatSerial(serialNumber, paddingWidth, prefix) {
  if (serialNumber == null) return "—";
  return `${prefix}${String(serialNumber).padStart(paddingWidth, "0")}`;
}
