import { useT } from "../i18n";

function GridIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1" fill="currentColor" />
      <rect x="9" y="1" width="6" height="6" rx="1" fill="currentColor" />
      <rect x="1" y="9" width="6" height="6" rx="1" fill="currentColor" />
      <rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor" />
    </svg>
  );
}

function ListIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="2" width="14" height="2.4" rx="1" fill="currentColor" />
      <rect x="1" y="6.8" width="14" height="2.4" rx="1" fill="currentColor" />
      <rect x="1" y="11.6" width="14" height="2.4" rx="1" fill="currentColor" />
    </svg>
  );
}

/**
 * Feature #108 — grid-/listevalg for Film- og TV-serie-fanen (Jans ønske
 * 2026-08-10). Delt komponent, da begge sider bruger præcis samme to
 * tilstande og samme `view_mode`-indstilling — én fælles indstilling for
 * begge faner, samme begrundelse som `card_size` (feature #59): en ren
 * visuel præference, ikke indholds-specifik.
 */
export default function ViewModeToggle({ viewMode, onChange }) {
  const t = useT();
  const isList = viewMode === "list";
  return (
    <div className="view-mode-toggle" role="group" aria-label={t("lib.viewMode")}>
      <button
        type="button"
        className={isList ? "" : "active"}
        onClick={() => onChange("grid")}
        title={t("lib.viewGrid")}
        aria-label={t("lib.viewGrid")}
        aria-pressed={!isList}
      >
        <GridIcon />
      </button>
      <button
        type="button"
        className={isList ? "active" : ""}
        onClick={() => onChange("list")}
        title={t("lib.viewList")}
        aria-label={t("lib.viewList")}
        aria-pressed={isList}
      >
        <ListIcon />
      </button>
    </div>
  );
}
