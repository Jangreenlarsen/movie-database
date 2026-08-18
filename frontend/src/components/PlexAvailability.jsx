/**
 * Feature #88 — visningen af Plex-status. Selve hentningen ligger i
 * `usePlexAvailability.js`; her er kun de to steder status vises: badget på
 * posteren og afspilnings-linjen i detaljevinduet.
 */

import { useState } from "react";
import { api } from "../api/client";
import { useT } from "../i18n";

/** Badget på selve posteren. Vises kun når elementet faktisk er i Plex. */
export function PlexCardBadge({ availability }) {
  const t = useT();
  if (!availability?.available) return null;
  return (
    <div
      className="movie-plex-badge"
      title={
        availability.matched_by === "tmdb"
          ? t("plex.badgeTmdb")
          : t("plex.badgeTitle", {
              title: `${availability.plex_title}${
                availability.plex_year ? ` ${availability.plex_year}` : ""
              }`,
            })
      }
    >
      {t("field.plex")}
    </div>
  );
}

/**
 * Detaljevinduets Plex-linje. Modsat feature #45's knap er der ikke noget
 * at trykke på for at få svaret — status er allerede kendt når vinduet
 * åbnes; linket er kun til at *afspille* med.
 */
export function PlexPlayLink({ availability, plex }) {
  const t = useT();
  // `plex` mangler når vinduet genbruges til en netop scannet film, der
  // endnu ikke er en del af biblioteket (MovieLookupForm).
  if (!plex || plex.status === "unconfigured") return null;

  if (plex.status === "error") {
    return <p className="muted">{t("plex.statusError", { message: plex.error })}</p>;
  }

  if (!availability?.available) {
    return plex.status === "ready" ? <p className="muted">{t("plex.notFound")}</p> : null;
  }

  // Uden machineIdentifier kan der ikke bygges en gyldig web-URL (sjælden
  // proxy-opsætning) — vi ved stadig at den ligger der, så det siges,
  // bare uden link.
  if (!availability.play_url) {
    return <p className="muted">{t("plex.noLink")}</p>;
  }

  return (
    <a href={availability.play_url} target="_blank" rel="noreferrer" className="btn btn-primary">
      {t("plex.play")}
    </a>
  );
}

/**
 * Feature #178 (Jan: "når man trykker på vis i plex så er option at starte
 * den i plex på shield der også") — ekstra knapper ved siden af
 * `PlexPlayLink`, der styrer det admin-konfigurerede Shield TV direkte, i
 * stedet for kun at åbne Plex Web.
 *
 * Kun vist når titlen faktisk er i Plex OG admin har sat Shieldens client-id
 * op (`shieldConfigured`, en boolean der følger med det samme ikke-admin-
 * only `/api/plex/availability`-kald `PlexPlayLink` allerede bruger — se
 * `PlexAvailabilityMap.shield_configured`'s begrundelse i backend).
 *
 * **Kendt forudsætning, ikke noget disse knapper kan rette**: Plex-appen
 * skal allerede være åben/logget ind på Shielden — Plex kan ikke selv tænde
 * eller starte appen fra slukket/standby.
 *
 * Opfølgning (Jan: "afspil på shield skal være en funktion som kun er på
 * admin users") — kun admin ser knapperne; `isAdmin` gates dem her, og
 * backend håndhæver det samme uafhængigt (`require_admin` på begge
 * endpoints), så en gæt-og-kald udenom UI'et heller ikke virker.
 *
 * Opfølgning (Jan, efter at "Afspil på Shield TV" transcodede video/lyd
 * hvor direkte afspilning på Shielden ikke gør det: "er det muligt så at
 * hoppe ind i plex klienten der hvor man skal til at trykke på play ... og
 * af den vej få spillet film med de local settings for klient der måtte
 * være") — "Vis på Shield TV" starter derfor IKKE længere afspilningen selv
 * (`playMedia`), den navigerer Shielden hen til titlens side
 * (`mirror/details`, samme Companion-kald Plex' eget cast-ikon bruger), så
 * brugerens eget tryk på Play på selve apparatet respekterer Plex-appens
 * lokale kvalitets-/lyd-indstillinger. Konsekvens: der er ikke længere en
 * "afspiller nu"-tilstand vi kan følge (vi ved ikke om/hvornår brugeren rent
 * faktisk trykker Play på fjernbetjeningen) — derfor to uafhængige knapper i
 * stedet for én toggle. "Stop" virker stadig uanset hvordan afspilningen
 * blev startet (Companion-stop rammer klientens aktuelle session, ikke kun
 * sessioner vi selv startede).
 */
export function PlexShieldControls({ availability, shieldConfigured, kind, itemId, isAdmin }) {
  const t = useT();
  const [busy, setBusy] = useState(null); // null | "show" | "stop"
  const [message, setMessage] = useState(null);
  const [isError, setIsError] = useState(false);

  if (!isAdmin || !availability?.available || !shieldConfigured) return null;

  async function run(action, apiCall) {
    setBusy(action);
    setMessage(null);
    setIsError(false);
    try {
      const result = await apiCall();
      setMessage(result.message);
      setIsError(!result.ok);
    } catch (err) {
      setMessage(err.message);
      setIsError(true);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="plex-shield-play">
      <div className="plex-shield-buttons">
        <button
          type="button"
          className="btn"
          onClick={() => run("show", () => api.playOnShield(kind, itemId))}
          disabled={busy !== null}
        >
          {t(busy === "show" ? "plex.shieldOpening" : "plex.shieldShow")}
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => run("stop", () => api.stopShield())}
          disabled={busy !== null}
        >
          {t(busy === "stop" ? "plex.shieldStopping" : "plex.shieldStop")}
        </button>
      </div>
      {message && <p className={isError ? "banner banner-error" : "muted"}>{message}</p>}
    </div>
  );
}
