// Feature #156 — delt af Library.jsx og TvShows.jsx: et filter-badge har tre
// tilstande i stedet for to. Klik cykler neutral → inkludér → ekskludér →
// neutral, samme rækkefølge alle steder i begge filter-paneler.
export function cycleFilterValue(state, value) {
  const included = state.included.includes(value);
  const excluded = state.excluded.includes(value);
  if (included) {
    return {
      included: state.included.filter((v) => v !== value),
      excluded: [...state.excluded, value],
    };
  }
  if (excluded) {
    return { included: state.included, excluded: state.excluded.filter((v) => v !== value) };
  }
  return { included: [...state.included, value], excluded: state.excluded };
}

export const EMPTY_FILTER_STATE = { included: [], excluded: [] };

// Singleton-badges (Set/Ikke set, Plex/Ikke Plex) bruger samme rækkefølge,
// men på en enkelt tri-state værdi (null | true | false) i stedet for to
// lister — der er jo kun ét muligt "valg", ikke en liste af tags/genrer.
export function cycleTriState(value) {
  if (value === null) return true;
  if (value === true) return false;
  return null;
}
