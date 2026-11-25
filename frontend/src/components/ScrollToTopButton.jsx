import { useEffect, useState } from "react";

import { useT } from "../i18n";
import "./ScrollToTopButton.css";

// Feature #235 — knappen står først frem, når man er scrollet et godt
// stykke ned. Øverst på siden er den bare i vejen.
export const SHOW_AFTER_PX = 600;

function prefersReducedMotion() {
  try {
    return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  } catch {
    // Ældre browsere uden matchMedia: brug blød scroll som standard.
    return false;
  }
}

// I appen er det `body`, der scroller, ikke vinduet: `html` og `body` har
// begge `overflow-x: hidden` (index.css), og så ruller browseren `body`
// selv. Set i browseren under udviklingen, hvor `window.scrollY` stod på 0
// hele vejen ned. Begge læses og begge scrolles, så knappen virker uanset
// hvilken af dem browseren bruger.
export function currentScrollTop() {
  return Math.max(
    window.scrollY || 0,
    document.documentElement?.scrollTop || 0,
    document.body?.scrollTop || 0
  );
}

function scrollAllToTop(behavior) {
  window.scrollTo({ top: 0, behavior });
  document.body?.scrollTo?.({ top: 0, behavior });
  document.documentElement?.scrollTo?.({ top: 0, behavior });
}

/**
 * Feature #235 — "Til toppen" på Film, TV-serier og Indkøbsønsker. Én
 * fælles knap (renderet af App) dækker alle tre.
 */
export default function ScrollToTopButton({ threshold = SHOW_AFTER_PX }) {
  const t = useT();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const update = () => setVisible(currentScrollTop() > threshold);
    update();
    // `capture` — et scroll-event på `body` bobler ikke op, men fanges her.
    document.addEventListener("scroll", update, { capture: true, passive: true });
    window.addEventListener("scroll", update, { passive: true });
    return () => {
      document.removeEventListener("scroll", update, { capture: true });
      window.removeEventListener("scroll", update);
    };
  }, [threshold]);

  if (!visible) return null;

  return (
    <button
      type="button"
      className="scroll-to-top"
      onClick={() => scrollAllToTop(prefersReducedMotion() ? "auto" : "smooth")}
      aria-label={t("common.scrollToTop")}
      title={t("common.scrollToTop")}
    >
      <span aria-hidden="true">↑</span>
    </button>
  );
}
