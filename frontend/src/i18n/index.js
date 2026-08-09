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

/** Findes der overhovedet et katalog for denne sprogkode? */
export function hasCatalog(language) {
  return Boolean(CATALOGS[language]);
}

// Dansk er kildesproget: al tekst skrives på dansk først, så det danske
// katalog er per definition komplet. Derfor er det også fallback'et — en
// nøgle der endnu ikke er oversat viser dansk tekst frem for en rå nøgle
// midt i brugerfladen.
export const SOURCE_LANGUAGE = "da";

export const LANGUAGES = [
  // `short` er den korte form til sprogvælgeren før login (feature #97),
  // hvor der kun er plads til et par tegn.
  { code: "da", label: "Dansk", short: "DK" },
  { code: "en", label: "English", short: "ENG" },
];

// Eksporteret, fordi provider-komponenten ligger i sin egen fil
// (I18nProvider.jsx) — denne fil eksporterer bevidst kun ikke-komponenter,
// så Vites fast refresh kan opdatere den uden fuld genindlæsning.
export const I18nContext = createContext(SOURCE_LANGUAGE);

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

// BCP 47-tags til `Intl`/`toLocaleDateString`. Engelsk mappes til en-GB, ikke
// en-US: en dansk bruger der slår over på engelsk forventer stadig dag-før-
// måned og 24-timers ur, ikke amerikansk datoformat.
const LOCALES = { da: "da-DK", en: "en-GB" };

/** Locale-tagget til dato-/talformatering — ikke en oversat streng. */
export function useLocale() {
  return LOCALES[useContext(I18nContext)] ?? LOCALES[SOURCE_LANGUAGE];
}

// Feature #97 — sprogvalget fra login-boksen.
//
// Sproget gemmes normalt pr. bruger i databasen (feature #89), men på login-
// skærmen og den offentlige /bio findes der ingen bruger endnu. Valget her
// ligger derfor i browserens localStorage: det er en *enheds*-præference for
// de skærme der kommer før man er logget ind, ikke en konkurrent til
// konto-indstillingen. Så snart man er logget ind, vinder kontoens sprog.
const STORAGE_KEY = "moviedb.language";

export function readStoredLanguage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return hasCatalog(stored) ? stored : SOURCE_LANGUAGE;
  } catch {
    // Privat browsing/blokeret storage — så er kildesproget svaret. Ikke
    // værd at vise en fejl for: sproget er stadig valgbart i selve sessionen.
    return SOURCE_LANGUAGE;
  }
}

export function storeLanguage(language) {
  try {
    localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // Se readStoredLanguage — valget gælder stadig for denne sidevisning.
  }
}
