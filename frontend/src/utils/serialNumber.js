/**
 * Serienummer-visning (feature #92).
 *
 * Lå tidligere som tre identiske `formatSerial`-kopier i Library.jsx,
 * TvShows.jsx og PrintList.jsx. Da præfikset kom til, skulle den samme regel
 * ellers vedligeholdes tre steder — og de tre kopier var allerede begyndt at
 * drive fra hinanden (kun PrintList håndterede et manglende nummer).
 *
 * Film og TV-serier har hver sin nummer-serie i backenden
 * (`movie_serial`/`tv_show_serial`-tællerne), så M#0001 og T#0001 er to
 * forskellige poster. Præfikset er netop det der gør dem til at skelne på
 * en hylde.
 */

export const MOVIE_SERIAL_PREFIX = "M#";
export const TV_SERIAL_PREFIX = "T#";

/**
 * @param serialNumber tallet, eller null/undefined for en post uden nummer
 *   (ønskeliste eller digital udgave — feature #92 nummererer kun fysiske)
 * @param paddingWidth antal foranstillede nuller, fra serienummer-opsætningen
 * @param prefix MOVIE_SERIAL_PREFIX eller TV_SERIAL_PREFIX
 */
export function formatSerial(serialNumber, paddingWidth, prefix) {
  if (serialNumber == null) return "—";
  return `${prefix}${String(serialNumber).padStart(paddingWidth, "0")}`;
}
