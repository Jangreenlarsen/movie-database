import { createContext, useContext, useMemo } from "react";

import da from "./da.json";
import en from "./en.json";

/**
 * Feature #89 — UI-sprog (dansk/engelsk).
 *
 * Bevidst ~60 linjer egen kode frem for react-i18next (Jans valg
 * 2026-08-08): to sprog, ingen lazy-loading af sprogfiler og ingen
 * pluralisering ud over "én/flere" retfærdiggør ikke 40 kB ekstra i en
 * bundle der allerede advarer om sin størrelse.
 *
 * Nøglerne er flade og punktum-adskilte ("library.title"), ikke indlejrede
 * objekter — det gør en nøgle i JSX direkte søgbar i sprogfilerne med præcis
 * den streng man har foran sig.
 */

const CATALOGS = { da, en };

// Dansk er kildesproget: al tekst skrives på dansk først, så det danske
// katalog er per definition komplet. Derfor er det også fallback'et — en
// nøgle der endnu ikke er oversat viser dansk tekst frem for en rå nøgle
// midt i brugerfladen.
export const SOURCE_LANGUAGE = "da";

export const LANGUAGES = [
  { code: "da", label: "Dansk" },
  { code: "en", label: "English" },
];

const I18nContext = createContext(SOURCE_LANGUAGE);

function lookup(language, key) {
  const value = CATALOGS[language]?.[key];
  if (value !== undefined) return value;
  const fallback = CATALOGS[SOURCE_LANGUAGE]?.[key];
  if (fallback !== undefined) return fallback;
  // Nøglen findes ikke i noget katalog — vis den rå nøgle. Det er grimt med
  // vilje: en manglende oversættelse skal være til at få øje på, ikke gemme
  // sig som tom tekst.
  return key;
}

function interpolate(template, vars) {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name) =>
    vars[name] === undefined || vars[name] === null ? match : String(vars[name])
  );
}

export function createTranslator(language) {
  /**
   * t("key") → tekst
   * t("key", { navn: "Anna" }) → indsætter i "{navn}"
   * t("key", { count: 3 }) → vælger "key_one"/"key_other" hvis de findes.
   *   Dansk og engelsk deler den samme simple flertalsregel (1 vs. resten),
   *   så et opslag rækker — ingen grund til Intl.PluralRules her.
   */
  return function t(key, vars) {
    let resolvedKey = key;
    if (vars && vars.count !== undefined) {
      const pluralKey = `${key}_${vars.count === 1 ? "one" : "other"}`;
      if (CATALOGS[language]?.[pluralKey] !== undefined || CATALOGS[SOURCE_LANGUAGE]?.[pluralKey] !== undefined) {
        resolvedKey = pluralKey;
      }
    }
    return interpolate(lookup(language, resolvedKey), vars);
  };
}

export function I18nProvider({ language, children }) {
  const value = CATALOGS[language] ? language : SOURCE_LANGUAGE;
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/** Oversætter-funktionen. Genskabes kun når sproget faktisk skifter. */
export function useT() {
  const language = useContext(I18nContext);
  return useMemo(() => createTranslator(language), [language]);
}

/**
 * Sprogkoden selv — til `Intl`-formatering (datoer, tal) og `lang`-attributter,
 * hvor det er BCP 47-tag'et og ikke en oversat streng der skal bruges.
 */
export function useLanguage() {
  return useContext(I18nContext);
}
