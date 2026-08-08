/**
 * Feature #88 — visningen af Plex-status. Selve hentningen ligger i
 * `usePlexAvailability.js`; her er kun de to steder status vises: badget på
 * posteren og afspilnings-linjen i detaljevinduet.
 */

/** Badget på selve posteren. Vises kun når elementet faktisk er i Plex. */
export function PlexCardBadge({ availability }) {
  if (!availability?.available) return null;
  return (
    <div
      className="movie-plex-badge"
      title={
        availability.matched_by === "tmdb"
          ? "Ligger i Plex (matchet på TMDb-id)"
          : `Ligger i Plex (matchet på titel: ${availability.plex_title}${
              availability.plex_year ? ` ${availability.plex_year}` : ""
            })`
      }
    >
      Plex
    </div>
  );
}

/**
 * Detaljevinduets Plex-linje. Modsat feature #45's knap er der ikke noget
 * at trykke på for at få svaret — status er allerede kendt når vinduet
 * åbnes; linket er kun til at *afspille* med.
 */
export function PlexPlayLink({ availability, plex }) {
  // `plex` mangler når vinduet genbruges til en netop scannet film, der
  // endnu ikke er en del af biblioteket (MovieLookupForm).
  if (!plex || plex.status === "unconfigured") return null;

  if (plex.status === "error") {
    return <p className="muted">Plex-status kunne ikke hentes: {plex.error}</p>;
  }

  if (!availability?.available) {
    return plex.status === "ready" ? <p className="muted">Ikke fundet i Plex.</p> : null;
  }

  // Uden machineIdentifier kan der ikke bygges en gyldig web-URL (sjælden
  // proxy-opsætning) — vi ved stadig at den ligger der, så det siges,
  // bare uden link.
  if (!availability.play_url) {
    return <p className="muted">▶ Ligger i Plex (kunne ikke bygge afspilnings-link).</p>;
  }

  return (
    <a href={availability.play_url} target="_blank" rel="noreferrer" className="btn btn-primary">
      ▶ Afspil i Plex
    </a>
  );
}
