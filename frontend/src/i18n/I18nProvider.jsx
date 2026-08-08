import { hasCatalog, I18nContext, SOURCE_LANGUAGE } from "./index";

/**
 * Feature #89 — sætter sproget for hele undertræet. Ligger i sin egen fil,
 * så `i18n/index.js` udelukkende eksporterer hooks og konstanter; en fil der
 * blander komponenter og ikke-komponenter kan Vites fast refresh ikke
 * opdatere uden at genindlæse hele siden.
 *
 * Et ukendt sprog falder tilbage til kildesproget frem for at lade hele
 * brugerfladen kollapse til rå nøgler.
 */
export default function I18nProvider({ language, children }) {
  const value = hasCatalog(language) ? language : SOURCE_LANGUAGE;
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
