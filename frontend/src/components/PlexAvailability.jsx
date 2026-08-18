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
 * den i plex på shield der også") — en ekstra knap ved siden af
 * `PlexPlayLink`, der sender en direkte afspilnings-kommando til det
 * admin-konfigurerede Shield TV, i stedet for kun at åbne Plex Web.
 *
 * Kun vist når titlen faktisk er i Plex OG admin har sat Shieldens client-id
 * op (`shieldConfigured`, en boolean der følger med det samme ikke-admin-
 * only `/api/plex/availability`-kald `PlexPlayLink` allerede bruger — se
 * `PlexAvailabilityMap.shield_configured`'s begrundelse i backend).
 *
 * **Kendt forudsætning, ikke noget denne knap kan rette**: Plex-appen skal
 * allerede være åben/logget ind på Shielden — Plex kan ikke selv tænde eller
 * starte appen fra slukket/standby.
 */
export function PlexShieldPlayButton({ availability, shieldConfigured, kind, itemId }) {
  const t = useT();
  const [state, setState] = useState("idle"); // idle | sending | done | error
  const [message, setMessage] = useState(null);

  if (!availability?.available || !shieldConfigured) return null;

  async function play() {
    setState("sending");
    setMessage(null);
    try {
      const result = await api.playOnShield(kind, itemId);
      setState(result.ok ? "done" : "error");
      setMessage(result.message);
    } catch (err) {
      setState("error");
      setMessage(err.message);
    }
  }

  return (
    <div className="plex-shield-play">
      <button type="button" className="btn" onClick={play} disabled={state === "sending"}>
        {t(state === "sending" ? "plex.shieldSending" : "plex.shieldPlay")}
      </button>
      {message && (
        <p className={state === "error" ? "banner banner-error" : "muted"}>{message}</p>
      )}
    </div>
  );
}
