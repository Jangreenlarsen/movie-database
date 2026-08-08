import { useEffect, useState } from "react";

import { api } from "../api/client";

/**
 * Feature #88 — portalen afgør selv om en film/serie ligger i Plex.
 *
 * Erstattede den manuelle "Tjek Plex"-knap fra feature #45, som lavede ét
 * kald pr. film. Her hentes hele fanens Plex-status i ét kald og slås op
 * lokalt pr. kort — ellers ville en side med 50 kort udløse 50 kald.
 *
 * Hook'en henter uanset om badget er slået til under "Vis felter": selve
 * kaldet er ét enkelt, backend-cachet opslag, og detaljevinduets "Afspil i
 * Plex"-link skal virke også for den der ikke ønsker badget på kortene.
 * Er Plex slet ikke konfigureret, svarer backend med det samme uden at
 * røre noget netværk.
 *
 * Ligger i sin egen fil frem for sammen med badge-komponenterne, så
 * PlexAvailability.jsx udelukkende eksporterer komponenter (Vites fast
 * refresh kan ellers ikke opdatere filen uden fuld genindlæsning).
 *
 * @param kind "movie" eller "show"
 */
export function usePlexAvailability(kind) {
  const [state, setState] = useState({ status: "loading", items: {}, error: null });

  function load(refresh = false) {
    setState((prev) => ({ ...prev, status: "loading" }));
    const call = refresh ? api.refreshPlexAvailability(kind) : api.getPlexAvailability(kind);
    return call
      .then((data) =>
        setState({
          // "unconfigured" holdes adskilt fra "error": at man ikke har en
          // Plex-server er ikke en fejl, og må ikke give en rød banner.
          status: data.configured ? (data.ok ? "ready" : "error") : "unconfigured",
          items: data.items ?? {},
          error: data.ok ? null : data.error,
          fetchedAt: data.fetched_at ?? null,
        })
      )
      // Netværks-/session-fejl mod vores egen backend. Vises i detaljevinduet
      // (CLAUDE.md regel 16), men vælter aldrig biblioteksvisningen.
      .catch((err) => setState({ status: "error", items: {}, error: err.message }));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  return { ...state, reload: () => load(true) };
}
