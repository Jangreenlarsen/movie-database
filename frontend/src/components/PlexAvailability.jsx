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
 *
 * Opfølgning (Jan: "sæt op i users styring hvem kan se og bruge vis iplex/
 * spil i plex i detajle for film/tv") — pr.-bruger til/fra, ikke rolle-
 * baseret. Er `plex.playAllowed` false (denne bruger er slået fra af en
 * admin), vises knappen slet ikke — adskilt fra det tekniske "intet link
 * kunne bygges"-tilfælde nedenfor, som stadig skal vise sin egen besked.
 * Backend har allerede udeladt selve `play_url` for en bruger uden adgang
 * (CLAUDE.md regel 16 — ikke kun en UI-bekvemmelighed), så denne boolean er
 * kun til at vælge den rigtige visning, ikke selve håndhævelsen.
 */
export function PlexPlayLink({ availability, plex }) {
  const t = useT();
  // `plex` mangler når vinduet genbruges til en netop scannet film, der
  // endnu ikke er en del af biblioteket (MovieLookupForm).
  if (!plex || plex.status === "unconfigured") return null;
  if (plex.playAllowed === false) return null;

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
 *
 * Opfølgning (Jan: "lave dem toggle bar sådan at når man trykker på dem så
 * ændre knap sig fra 'play start' til 'play stop'") — kun DENNE knap blev en
 * rigtig toggle: den kalder allerede Plex' egen kommando-API og kan derfor
 * sende en ægte stop-kommando (`api.stopShield`). `PlexPlayLink` ovenfor
 * forbliver bevidst et almindeligt link (åbner Plex Web i en ny fane) — der
 * er ingen session vi kan sende en stop-kommando til derfra, så en
 * tilsvarende toggle på den knap ville vise noget vi reelt ikke kan gøre.
 *
 * Opfølgning (Jan: "afspil på shield skal være en funktion som kun er på
 * admin users") — kun admin ser knappen; `isAdmin` gates den her, og
 * backend håndhæver det samme uafhængigt (`require_admin` på begge
 * endpoints), så en gæt-og-kald udenom UI'et heller ikke virker.
 *
 * Opfølgning (Jan: "hvis jeg disabler 'vis i plex' skal 'afspil i plex også
 * disablet, alt plex under detajle kort på film/tv skal ikke være
 * syndeligt hvis plex er disablet på user") — Shield-kommandoerne krævede
 * hidtil kun `available` (som stadig er sand for en bruger uden adgang;
 * backend udelader kun selve `play_url`, ikke tilstedeværelsen), så en
 * admin med sin egen `plex_play_enabled` slået fra kunne stadig se denne
 * knap. `playAllowed` lukker det hul — samme boolean `PlexPlayLink` bruger.
 *
 * 2026-08-19 — genindført en tredje, SEPARAT test-knap, "Vis på Shield TV
 * (test)" (Jan, efter research bekræftede hvorfor det oprindelige
 * `mirror/details`-forsøg fejlede — se backend for hele baggrunden: "lave
 * igen en knap mere til 'vis i plex' sådan vi kan teste på den funktion
 * igen sammen med de andre, jeg se på om der skulle være opdateringer til
 * plex klient"). Bevidst UDENFOR afspil/stop-toggle'en: den starter ikke
 * en kendt "afspiller nu"-tilstand (vi ved ikke om/hvornår brugeren rent
 * faktisk trykker Play på selve apparatet), så den har sin egen simple
 * busy/besked-tilstand i stedet for at dele toggle'ens `phase`.
 */
export function PlexShieldPlayButton({
  availability,
  shieldConfigured,
  kind,
  itemId,
  isAdmin,
  playAllowed,
}) {
  const t = useT();
  const [phase, setPhase] = useState("idle"); // idle | starting | playing | stopping
  const [message, setMessage] = useState(null);
  const [isError, setIsError] = useState(false);
  const [showBusy, setShowBusy] = useState(false);
  const [showMessage, setShowMessage] = useState(null);
  const [showIsError, setShowIsError] = useState(false);

  if (!isAdmin || playAllowed === false || !availability?.available || !shieldConfigured) {
    return null;
  }

  async function play() {
    setPhase("starting");
    setMessage(null);
    setIsError(false);
    try {
      const result = await api.playOnShield(kind, itemId);
      setMessage(result.message);
      setIsError(!result.ok);
      setPhase(result.ok ? "playing" : "idle");
    } catch (err) {
      setMessage(err.message);
      setIsError(true);
      setPhase("idle");
    }
  }

  async function stop() {
    setPhase("stopping");
    setMessage(null);
    setIsError(false);
    try {
      const result = await api.stopShield();
      setMessage(result.ok ? null : result.message);
      setIsError(!result.ok);
      // Fejler stoppet, antager vi den stadig spiller (giv brugeren chancen
      // for at prøve stop igen, i stedet for at tvinge knappen tilbage til
      // "Afspil", som ville sende endnu en playMedia-kommando).
      setPhase(result.ok ? "idle" : "playing");
    } catch (err) {
      setMessage(err.message);
      setIsError(true);
      setPhase("playing");
    }
  }

  async function show() {
    setShowBusy(true);
    setShowMessage(null);
    setShowIsError(false);
    try {
      const result = await api.showOnShield(kind, itemId);
      setShowMessage(result.message);
      setShowIsError(!result.ok);
    } catch (err) {
      setShowMessage(err.message);
      setShowIsError(true);
    } finally {
      setShowBusy(false);
    }
  }

  const isPlaying = phase === "playing";
  const isBusy = phase === "starting" || phase === "stopping";

  return (
    <div className="plex-shield-play">
      <div className="plex-shield-buttons">
        <button
          type="button"
          className={isPlaying ? "btn btn-primary" : "btn"}
          onClick={isPlaying ? stop : play}
          disabled={isBusy}
        >
          {t(
            phase === "starting"
              ? "plex.shieldSending"
              : phase === "stopping"
                ? "plex.shieldStopping"
                : isPlaying
                  ? "plex.shieldStop"
                  : "plex.shieldPlay"
          )}
        </button>
        <button type="button" className="btn" onClick={show} disabled={showBusy}>
          {t(showBusy ? "plex.shieldShowing" : "plex.shieldShow")}
        </button>
      </div>
      {message && <p className={isError ? "banner banner-error" : "muted"}>{message}</p>}
      {showMessage && (
        <p className={showIsError ? "banner banner-error" : "muted"}>{showMessage}</p>
      )}
    </div>
  );
}
