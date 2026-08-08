import { useState } from "react";
import Library from "./Library";
import TvShows from "./TvShows";
import { useT } from "../i18n";

/**
 * "Ønsker"-sektionen. Film og TV-serier er to bevidst adskilte ressourcer
 * (CLAUDE.md), så ønskelisten har samme opdeling som bibliotekets egne faner
 * i stedet for én blandet liste.
 *
 * Før BUGS.md #47 renderede App.jsx kun `<Library wishlist />` her. Add-panelets
 * scan/søgning finder både film og TV-serier, så en TV-serie tilføjet fra
 * ønskelisten blev gemt korrekt i tv_shows med `is_wishlist: true` — men var
 * derefter usynlig i hele appen: ikke her (kun film), og heller ikke under
 * "TV-serier", som filtrerer ønsker fra.
 */
export default function Wishlist({ user, onSettingsChanged }) {
  const t = useT();
  const [kind, setKind] = useState("movies");

  return (
    <section>
      <nav className="tabs" style={{ marginBottom: 16 }}>
        <button
          type="button"
          className={kind === "movies" ? "active" : ""}
          onClick={() => setKind("movies")}
        >
          {t("app.nav.movies")}
        </button>
        <button
          type="button"
          className={kind === "tv" ? "active" : ""}
          onClick={() => setKind("tv")}
        >
          {t("app.nav.tv")}
        </button>
      </nav>

      {kind === "movies" ? (
        <Library
          user={user}
          onSettingsChanged={onSettingsChanged}
          wishlist
          onGoToTvShows={() => setKind("tv")}
        />
      ) : (
        <TvShows
          user={user}
          onSettingsChanged={onSettingsChanged}
          wishlist
          onGoToMovies={() => setKind("movies")}
        />
      )}
    </section>
  );
}
