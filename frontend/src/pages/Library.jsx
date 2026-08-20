import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import Chip from "../components/Chip";
import Combobox from "../components/Combobox";
import MovieLookupForm from "../components/MovieLookupForm";
import Pagination from "../components/Pagination";
import { PlexCardBadge, PlexPlayLink, PlexShieldPlayButton } from "../components/PlexAvailability";
import { usePlexAvailability } from "../components/usePlexAvailability";
import ScreeningRequestButton from "../components/ScreeningRequestButton";
import SubtitlesPicker from "../components/SubtitlesPicker";
import ViewModeToggle from "../components/ViewModeToggle";
import { useLocale, useT } from "../i18n";
import { cycleFilterValue, cycleTriState, EMPTY_FILTER_STATE } from "../utils/filterCycle";
import { cardPosterSize, posterSrc } from "../utils/posterUrl";
import { duplicateSerialSuffix, formatSerial, serialPrefix } from "../utils/serialNumber";
import "./Library.css";

// Feature #89 — `labelKey` frem for en færdig `label`: listen er et
// modul-konstant, der evalueres én gang ved import, længe før nogen
// oversætter findes. Nøglen slås derfor først op ved render.
const SORT_OPTIONS = [
  // Feature #96 — to valg, fordi de tre nummer-serier tælles hver for sig:
  // det ene grupperer digitale først, det andet fysiske først.
  { value: "serial_number", labelKey: "sort.serialDigitalFirst" },
  { value: "serial_number_physical", labelKey: "sort.serialMoviesFirst" },
  { value: "created_at", labelKey: "field.added" },
  { value: "title", labelKey: "field.title" },
  // Feature #184 — Jan: "i sortering skal det være muligt at ignorerer 'the'
  // i starten af titel navn". Eget valg, samme mønster som
  // serial_number/serial_number_physical ovenfor, i stedet for en til/fra-
  // kontakt på "title" selv.
  { value: "title_no_article", labelKey: "sort.titleNoArticle" },
  { value: "year", labelKey: "field.year" },
  { value: "rating", labelKey: "field.rating" },
  { value: "personal_rating", labelKey: "field.personalRating" },
  { value: "watched_at", labelKey: "field.watchedDate" },
  { value: "runtime", labelKey: "field.runtime" },
  { value: "format", labelKey: "field.format" },
  { value: "audio_types", labelKey: "field.audioType" },
  { value: "media_type", labelKey: "field.mediaType" },
  // Feature #146 — sortér på genre.
  { value: "genres", labelKey: "field.genres" },
  { value: "location", labelKey: "field.location" },
  { value: "owner", labelKey: "field.owner" },
  { value: "registered_by", labelKey: "field.registeredBy" },
  // Feature #127 — bestillingsstatus (kun sat på ønskeliste-poster).
  { value: "order_status", labelKey: "field.orderStatus" },
];
const MAX_SORT_LEVELS = 3;

// Feature #86 — appens standardværdier ét sted, så både "er der ændret
// noget?"-markeringen på værktøjslinjen og "Nulstil til standard"-knapperne
// måler mod præcis det samme, i stedet for hver sin hardcodede kopi.
const DEFAULT_SORT_LEVELS = [{ field: "serial_number", direction: "desc" }];

function initialSortLevels(settings) {
  if (settings?.sort_levels?.length) return settings.sort_levels;
  if (settings?.sort_field || settings?.sort_direction) {
    return [
      {
        field: settings.sort_field ?? DEFAULT_SORT_LEVELS[0].field,
        direction: settings.sort_direction ?? DEFAULT_SORT_LEVELS[0].direction,
      },
    ];
  }
  return DEFAULT_SORT_LEVELS;
}

function sortLevelsAreDefault(levels) {
  return (
    levels.length === DEFAULT_SORT_LEVELS.length &&
    levels.every(
      (level, i) =>
        level.field === DEFAULT_SORT_LEVELS[i].field &&
        level.direction === DEFAULT_SORT_LEVELS[i].direction
    )
  );
}

const VISIBLE_FIELD_OPTIONS = [
  { key: "year", labelKey: "field.year" },
  { key: "tags", labelKey: "field.tags" },
  { key: "format", labelKey: "field.format" },
  { key: "audioTypes", labelKey: "field.audioType" },
  { key: "mediaType", labelKey: "field.mediaType" },
  { key: "rating", labelKey: "field.rating" },
  { key: "runtime", labelKey: "field.runtime" },
  { key: "plex", labelKey: "field.plex" },
  { key: "genres", labelKey: "field.genres" },
];

const DEFAULT_VISIBLE_FIELDS = {
  year: true,
  tags: true,
  format: false,
  audioTypes: false,
  mediaType: false,
  rating: false,
  runtime: false,
  plex: false,
  genres: false,
};

function visibleFieldsFromSettings(settings) {
  const vf = settings?.visible_fields ?? {};
  return {
    year: vf.year ?? DEFAULT_VISIBLE_FIELDS.year,
    tags: vf.tags ?? DEFAULT_VISIBLE_FIELDS.tags,
    format: vf.format ?? DEFAULT_VISIBLE_FIELDS.format,
    audioTypes: vf.audio_types ?? DEFAULT_VISIBLE_FIELDS.audioTypes,
    mediaType: vf.media_type ?? DEFAULT_VISIBLE_FIELDS.mediaType,
    rating: vf.rating ?? DEFAULT_VISIBLE_FIELDS.rating,
    runtime: vf.runtime ?? DEFAULT_VISIBLE_FIELDS.runtime,
    plex: vf.plex ?? DEFAULT_VISIBLE_FIELDS.plex,
    genres: vf.genres ?? DEFAULT_VISIBLE_FIELDS.genres,
  };
}

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="7" cy="7" r="5.25" stroke="currentColor" strokeWidth="1.5" />
      <path d="M11 11L14.5 14.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function toggleValue(list, value) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/**
 * `onGoToTvShows` (valgfri) er genvejen til den tilsvarende TV-visning —
 * "Ønsker"-sektionens TV-underfane, eller hovedfanen "TV-serier". Den bruges
 * når scan/søgning i add-panelet endte med en TV-serie, som denne side aldrig
 * kan vise (BUGS.md #47).
 */
export default function Library({
  user,
  onSettingsChanged,
  wishlist = false,
  onGoToTvShows,
  // Feature #94 — kaldes når biblioteket ændrer sig, så app-hovedets
  // optælling ikke bliver stående til næste sideindlæsning.
  onLibraryChanged,
}) {
  const t = useT();
  const isGuest = user.role === "guest";
  const isAdmin = user.role === "admin";
  const [query, setQuery] = useState("");
  // Feature #156 — hvert filter er nu {included, excluded} i stedet for en
  // flad liste: et badge cykler neutral → inkludér → ekskludér → neutral.
  const [tagFilter, setTagFilter] = useState(EMPTY_FILTER_STATE);
  const [formatFilter, setFormatFilter] = useState(EMPTY_FILTER_STATE);
  const [audioTypeFilter, setAudioTypeFilter] = useState(EMPTY_FILTER_STATE);
  const [mediaTypeFilter, setMediaTypeFilter] = useState(EMPTY_FILTER_STATE);
  // Feature #111 — genrer der rent faktisk findes i biblioteket (distinct
  // fra backend, ikke en fast enum som format/audio_types/media_type), så
  // filter-panelet kun viser genrer der reelt kan matche noget.
  const [genreFilter, setGenreFilter] = useState(EMPTY_FILTER_STATE);
  const [allGenres, setAllGenres] = useState([]);
  // Feature #157 — kun relevant (og kun vist) på ønskelisten, ligesom
  // bestillings-status-badget på selve kortet (feature #114).
  const [orderStatusFilter, setOrderStatusFilter] = useState(EMPTY_FILTER_STATE);
  const [watchedFilter, setWatchedFilter] = useState(null); // null | true | false
  // Feature #156 — samme tri-state som watchedFilter ovenfor, men mod
  // usePlexAvailability's id-sæt frem for et gemt felt på dokumentet.
  const [plexFilter, setPlexFilter] = useState(null); // null | true | false
  const [personFilter, setPersonFilter] = useState(null); // null | { type: "cast" | "director", name }
  const [sortLevels, setSortLevels] = useState(() => initialSortLevels(user.settings));
  const [presets, setPresets] = useState(user.settings.sort_presets ?? []);
  const [presetNameInput, setPresetNameInput] = useState("");
  const [movies, setMovies] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(user.settings.page_size ?? 50);
  const [status, setStatus] = useState("loading");
  const [allTags, setAllTags] = useState([]);
  const [allOwners, setAllOwners] = useState([]);
  const [allLocations, setAllLocations] = useState([]);
  const [attributeOptions, setAttributeOptions] = useState({
    formats: [],
    audio_types: [],
    media_types: [],
    order_statuses: [],
    subtitles: [],
  });
  const [activeMovie, setActiveMovie] = useState(null);
  const [visibleFields, setVisibleFields] = useState(() => visibleFieldsFromSettings(user.settings));
  // Feature #108 — grid/liste, læst direkte fra brugerens indstillinger
  // ligesom card_size; ingen lokal "ikke gemt endnu"-tilstand nødvendig, da
  // valget skal slå igennem med det samme og altid er én af de to.
  const [viewMode, setViewMode] = useState(user.settings.view_mode ?? "grid");
  // Feature #164 (Jan) — Sortér/Filtrér/Vis felter er nu gensidigt eksklusive:
  // ét delt "hvilket panel er åbent"-felt i stedet for tre uafhængige
  // booleans, så det er umuligt for to at stå åbne på samme tid (i stedet for
  // at skulle huske at lukke de andre to ved hvert af de tre onClick'et).
  const [openPanel, setOpenPanel] = useState(null); // null | "sort" | "filter" | "fields"
  const togglePanel = (name) => setOpenPanel((current) => (current === name ? null : name));
  // Feature #124/#126 — tilføj-flowets to store handlingsknapper: "scan" |
  // "manual" | null. Bruges nu på både bibliotek og ønskeliste (#126 bredte
  // det ud fra kun ønskelisten), så scan og titel-søgning åbnes hver for sig
  // og ikke forveksles med den generelle søgning.
  const [addMode, setAddMode] = useState(null);
  const [serialPaddingWidth, setSerialPaddingWidth] = useState(0);
  const [settingsError, setSettingsError] = useState(null);
  // BUGS.md #61 — en fejlet genindlæsning efter gem/slet vises nu (før slugt).
  const [refreshError, setRefreshError] = useState(null);
  // Feature #156 — Plex-filteret kan afvises (409) hvis Plex ikke er
  // konfigureret; den specifikke besked skal vises, ikke kun "kunne ikke
  // hente film" (CLAUDE.md regel 16).
  const [listError, setListError] = useState(null);
  const [savedTvShow, setSavedTvShow] = useState(false);
  // Feature #88 — hele bibliotekets Plex-status i ét kald, slået op pr. kort.
  const plex = usePlexAvailability("movie");

  // BUGS.md #45 — these saves used to end in a bare `.catch(() => {})`. The
  // UI updates from local state either way, so a failed save (session
  // expired, backend down) left the user believing their named sort preset
  // or page size had been stored — the loss only surfaced on next reload.
  // Every settings write now goes through here so the failure is actually
  // shown (CLAUDE.md regel 16, "Fejlbeskeder til brugeren").
  function persistSettings(patch) {
    setSettingsError(null);
    return api
      .updateMySettings(patch)
      .then(onSettingsChanged)
      .catch((err) => setSettingsError(err.message));
  }

  function changeViewMode(nextMode) {
    if (nextMode === viewMode) return;
    setViewMode(nextMode);
    persistSettings({ view_mode: nextMode });
  }

  function persistVisibleFields(nextVisible) {
    persistSettings({
      visible_fields: {
        year: nextVisible.year,
        tags: nextVisible.tags,
        format: nextVisible.format,
        audio_types: nextVisible.audioTypes,
        media_type: nextVisible.mediaType,
        rating: nextVisible.rating,
        runtime: nextVisible.runtime,
        plex: nextVisible.plex,
        genres: nextVisible.genres,
      },
    });
  }

  function persistSortLevels(nextLevels) {
    persistSettings({ sort_levels: nextLevels });
  }

  function persistSortPresets(nextPresets) {
    persistSettings({ sort_presets: nextPresets });
  }

  useEffect(() => {
    api.listTags().then(setAllTags).catch(() => {});
    api.listOwners().then(setAllOwners).catch(() => {});
    api.listLocations().then(setAllLocations).catch(() => {});
    api.attributeOptions().then(setAttributeOptions).catch(() => {});
    api.listMovieGenres().then(setAllGenres).catch(() => {});
    api
      .getSerialNumberConfig()
      .then((config) => setSerialPaddingWidth(config.padding_width))
      .catch(() => {});
  }, []);

  function fetchMovies() {
    return api.listMovies({
      q: query || undefined,
      tags: tagFilter.included,
      tagsExclude: tagFilter.excluded,
      format: formatFilter.included,
      formatExclude: formatFilter.excluded,
      audioTypes: audioTypeFilter.included,
      audioTypesExclude: audioTypeFilter.excluded,
      mediaTypes: mediaTypeFilter.included,
      mediaTypesExclude: mediaTypeFilter.excluded,
      genres: genreFilter.included,
      genresExclude: genreFilter.excluded,
      orderStatuses: orderStatusFilter.included,
      orderStatusesExclude: orderStatusFilter.excluded,
      sort: sortLevels,
      wishlist,
      watched: watchedFilter,
      plex: plexFilter,
      cast: personFilter?.type === "cast" ? personFilter.name : undefined,
      director: personFilter?.type === "director" ? personFilter.name : undefined,
      page,
      pageSize,
    });
  }

  // Changing a filter/sort/search must jump back to page 1 — the current
  // page number may no longer exist in the new, smaller/reordered result
  // set (feature #15). Kept as its own effect (separate from the fetch
  // effect below) so it fires before the fetch reads `page`.
  useEffect(() => {
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    query,
    tagFilter,
    formatFilter,
    audioTypeFilter,
    mediaTypeFilter,
    genreFilter,
    orderStatusFilter,
    sortLevels,
    watchedFilter,
    plexFilter,
    personFilter,
    pageSize,
  ]);

  useEffect(() => {
    setStatus("loading");
    setListError(null);
    fetchMovies()
      .then((data) => {
        setMovies(data.items);
        setTotal(data.total);
        setStatus("ready");
      })
      .catch((err) => {
        setListError(err.message);
        setStatus("error");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    query,
    tagFilter,
    formatFilter,
    audioTypeFilter,
    mediaTypeFilter,
    genreFilter,
    orderStatusFilter,
    sortLevels,
    watchedFilter,
    plexFilter,
    personFilter,
    page,
    pageSize,
  ]);

  function persistPageSize(nextPageSize) {
    persistSettings({ page_size: nextPageSize });
  }

  function refresh() {
    onLibraryChanged?.();
    fetchMovies()
      .then((data) => {
        setMovies(data.items);
        setTotal(data.total);
        setRefreshError(null);
      })
      // BUGS.md #61 — mutationen er gemt, men listen kunne ikke genindlæses;
      // vis det frem for at lade listen stå tavst forældet.
      .catch((err) => setRefreshError(err.message));
  }

  // Feature #144 — admin godkender et afventende ønske direkte fra kortet.
  async function approveWishlist(movie, event) {
    event.stopPropagation();
    try {
      await api.updateMovie(movie.id, { wishlist_status: "approved" });
      refresh();
    } catch (err) {
      setRefreshError(err.message);
    }
  }

  // Feature #165 — modparten: afvis i stedet for at godkende. Fjerner ønsket
  // og sender opretteren en besked med adminens (valgfrie) begrundelse.
  // `window.prompt` returnerer null ved Annuller — kun da springes handlingen
  // helt over; en tom streng (OK uden tekst) sendes videre, backend falder
  // selv tilbage til en generisk besked.
  async function rejectWishlist(movie, event) {
    event.stopPropagation();
    const message = window.prompt(t("lib.rejectWishlistPrompt"));
    if (message === null) return;
    try {
      await api.rejectMovieWishlist(movie.id, message);
      refresh();
    } catch (err) {
      setRefreshError(err.message);
    }
  }

  function updateVisibleField(key, value) {
    setVisibleFields((prev) => {
      const next = { ...prev, [key]: value };
      persistVisibleFields(next);
      return next;
    });
  }

  function updateSortLevelField(index, field) {
    setSortLevels((prev) => {
      const next = prev.map((level, i) => (i === index ? { ...level, field } : level));
      persistSortLevels(next);
      return next;
    });
  }

  function toggleSortLevelDirection(index) {
    setSortLevels((prev) => {
      const next = prev.map((level, i) =>
        i === index ? { ...level, direction: level.direction === "asc" ? "desc" : "asc" } : level
      );
      persistSortLevels(next);
      return next;
    });
  }

  function addSortLevel() {
    setSortLevels((prev) => {
      if (prev.length >= MAX_SORT_LEVELS) return prev;
      const used = new Set(prev.map((level) => level.field));
      const nextField = SORT_OPTIONS.find((opt) => !used.has(opt.value))?.value ?? SORT_OPTIONS[0].value;
      const next = [...prev, { field: nextField, direction: "asc" }];
      persistSortLevels(next);
      return next;
    });
  }

  function removeSortLevel(index) {
    setSortLevels((prev) => {
      if (prev.length <= 1) return prev;
      const next = prev.filter((_, i) => i !== index);
      persistSortLevels(next);
      return next;
    });
  }

  function applyPreset(name) {
    const preset = presets.find((p) => p.name === name);
    if (!preset) return;
    setSortLevels(preset.levels);
    persistSortLevels(preset.levels);
    // Presets saved before feature #44 only have `levels` — the ?? []/null
    // fallbacks make applying an old, sort-only preset a no-op for the rest
    // of the filter state instead of wiping out what the user had selected.
    setQuery(preset.query ?? "");
    // Feature #156 — presets gemmer kun den inkluderede side af hvert filter
    // (uændret gemme-format); anvendes et gemt preset starter et evt. negeret
    // valg fra en tidligere session altså rent, ikke bevaret.
    setTagFilter({ included: preset.tags ?? [], excluded: [] });
    setFormatFilter({ included: preset.formats ?? [], excluded: [] });
    setAudioTypeFilter({ included: preset.audio_types ?? [], excluded: [] });
    setMediaTypeFilter({ included: preset.media_types ?? [], excluded: [] });
    setWatchedFilter(preset.watched ?? null);
  }

  function saveCurrentAsPreset() {
    const name = presetNameInput.trim();
    if (!name) return;
    const next = [
      ...presets.filter((p) => p.name !== name),
      {
        name,
        levels: sortLevels,
        query: query || null,
        tags: tagFilter.included,
        formats: formatFilter.included,
        audio_types: audioTypeFilter.included,
        media_types: mediaTypeFilter.included,
        watched: watchedFilter,
      },
    ];
    setPresets(next);
    persistSortPresets(next);
    setPresetNameInput("");
  }

  function deletePreset(name) {
    const next = presets.filter((p) => p.name !== name);
    setPresets(next);
    persistSortPresets(next);
  }

  // Feature #86 — ét tal pr. værktøj, så knappen på værktøjslinjen kan vise
  // om der overhovedet er valgt noget uden at man skal åbne panelet.
  // personFilter tælles med her; før stod den kun i `hasActiveFilters`, så et
  // rent person-filter fik knappen til at vise "Filtrér (0)".
  // Feature #156 — hvert filter tæller både inkluderede og ekskluderede valg.
  const activeFilterCount =
    tagFilter.included.length +
    tagFilter.excluded.length +
    formatFilter.included.length +
    formatFilter.excluded.length +
    audioTypeFilter.included.length +
    audioTypeFilter.excluded.length +
    mediaTypeFilter.included.length +
    mediaTypeFilter.excluded.length +
    genreFilter.included.length +
    genreFilter.excluded.length +
    orderStatusFilter.included.length +
    orderStatusFilter.excluded.length +
    (watchedFilter != null ? 1 : 0) +
    (plexFilter != null ? 1 : 0) +
    (personFilter != null ? 1 : 0);
  const hasActiveFilters = activeFilterCount > 0;
  const sortIsDefault = sortLevelsAreDefault(sortLevels);
  const changedFieldCount = VISIBLE_FIELD_OPTIONS.filter(
    (opt) => visibleFields[opt.key] !== DEFAULT_VISIBLE_FIELDS[opt.key]
  ).length;

  function resetSortToDefault() {
    setSortLevels(DEFAULT_SORT_LEVELS);
    persistSortLevels(DEFAULT_SORT_LEVELS);
  }

  function resetFilters() {
    setTagFilter(EMPTY_FILTER_STATE);
    setFormatFilter(EMPTY_FILTER_STATE);
    setAudioTypeFilter(EMPTY_FILTER_STATE);
    setMediaTypeFilter(EMPTY_FILTER_STATE);
    setGenreFilter(EMPTY_FILTER_STATE);
    setOrderStatusFilter(EMPTY_FILTER_STATE);
    setWatchedFilter(null);
    setPlexFilter(null);
    setPersonFilter(null);
  }

  function resetVisibleFieldsToDefault() {
    setVisibleFields(DEFAULT_VISIBLE_FIELDS);
    persistVisibleFields(DEFAULT_VISIBLE_FIELDS);
  }

  // Feature #124 — delte toolbar-dele, så bibliotekets og ønskelistens to
  // forskellige toolbar-layouts kan genbruge dem uden duplikering.
  const searchInputWrap = (placeholder) => (
    <div className="search-input-wrap">
      <SearchIcon />
      <input
        type="search"
        placeholder={placeholder}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {/* Feature #102 — egen ryd-knap frem for at stole på browserens
          indbyggede: `type="search"` viser kun et kryds i WebKit og Chrome,
          ikke i Firefox, så den var usynlig for halvdelen af brugerne. */}
      {query && (
        <button
          type="button"
          className="search-clear"
          onClick={() => setQuery("")}
          title={t("lib.clearSearch")}
          aria-label={t("lib.clearSearch")}
        >
          ✕
        </button>
      )}
    </div>
  );

  const sortFilterFieldButtons = (
    <>
      <button
        type="button"
        className={`btn${sortIsDefault ? "" : " btn-modified"}`}
        title={t(sortIsDefault ? "lib.sortDefaultTitle" : "lib.sortModifiedTitle")}
        onClick={() => togglePanel("sort")}
      >
        {t("lib.sort")} {sortIsDefault ? "" : "● "}▾
      </button>

      <button
        type="button"
        className={`btn${hasActiveFilters ? " btn-modified" : ""}`}
        title={
          hasActiveFilters
            ? t("lib.filterActiveTitle", { count: activeFilterCount })
            : t("lib.filterNoneTitle")
        }
        onClick={() => togglePanel("filter")}
      >
        {t("lib.filter")} {hasActiveFilters ? `(${activeFilterCount}) ` : ""}▾
      </button>

      <button
        type="button"
        className={`btn${changedFieldCount > 0 ? " btn-modified" : ""}`}
        title={t(changedFieldCount > 0 ? "lib.fieldsModifiedTitle" : "lib.fieldsDefaultTitle")}
        onClick={() => togglePanel("fields")}
      >
        {t("lib.fields")} {changedFieldCount > 0 ? "● " : ""}▾
      </button>

      <ViewModeToggle viewMode={viewMode} onChange={changeViewMode} />
    </>
  );

  return (
    <section>
      <div className="page-header">
        <h1>{t(wishlist ? "lib.wishlistTitle" : "lib.title")}</h1>
        <span className="muted">
          {/* BUGS.md #64 — total på tværs af alle sider, ikke kun de viste på
              den aktuelle side (`movies` er kun den hentede side). */}
          {status === "ready" ? t("lib.count", { count: total }) : " "}
        </span>
      </div>

      <div className="library-toolbar">
        {/* Feature #124/#126 — to store handlingsknapper (Scan cover / Søg
            titel) der hver åbner kun den relevante del, så den manuelle
            titel-søgning ikke forveksles med bibliotekets generelle søgning.
            #124 gav ønskelisten dette; #126 bredte det ud til Film- og
            TV-siderne (Jans ønske 2026-08-12). Gæster ser dem kun på
            ønskelisten (de må oprette ønsker, men intet i selve biblioteket,
            jf. feature #116). */}
        {(!isGuest || wishlist) && (
          <div className="add-actions">
            <button
              type="button"
              className={`btn btn-primary add-action${addMode === "scan" ? " active" : ""}`}
              onClick={() => setAddMode((m) => (m === "scan" ? null : "scan"))}
            >
              📷 {t("lib.addScan")}
            </button>
            <button
              type="button"
              className={`btn btn-primary add-action${addMode === "manual" ? " active" : ""}`}
              onClick={() => setAddMode((m) => (m === "manual" ? null : "manual"))}
            >
              🔍 {t("lib.addSearchTitle")}
            </button>
          </div>
        )}

        {/* Ønskelisten demoter den generelle søgning (man filtrerer sjældent
            sine ønsker); Film-siden beholder den fremtrædende (Jans valg
            2026-08-12), da den bruges meget til at filtrere biblioteket. */}
        <div className={`search-row${wishlist ? " search-row-secondary" : ""}`}>
          {searchInputWrap(t(wishlist ? "lib.wishlistFilterPlaceholder" : "lib.searchPlaceholder"))}
          {sortFilterFieldButtons}
        </div>

        {addMode && (
          <div style={{ marginTop: 8 }}>
            <MovieLookupForm
              user={user}
              wishlist={wishlist}
              mode={addMode}
              key={addMode}
              onSaved={(kind) => {
                refresh();
                setAddMode(null);
                // Scan/søgning her rammer også TMDb's TV-database, og en
                // valgt TV-serie havner i tv_shows — en collection denne
                // side aldrig viser. Uden beskeden nedenfor så det ud som
                // om serien forsvandt (BUGS.md #47).
                setSavedTvShow(kind === "tv");
              }}
            />
          </div>
        )}

        {openPanel === "sort" && (
          <div className="filter-panel">
            <div className="sort-levels">
              {sortLevels.map((level, index) => (
                <div key={index} className="sort-level-row">
                  <span className="sort-level-index">{index + 1}.</span>
                  <select value={level.field} onChange={(e) => updateSortLevelField(index, e.target.value)}>
                    {SORT_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {t(opt.labelKey)}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn"
                    title={t(level.direction === "asc" ? "lib.sortAscending" : "lib.sortDescending")}
                    onClick={() => toggleSortLevelDirection(index)}
                  >
                    {level.direction === "asc" ? "↑" : "↓"}
                  </button>
                  {sortLevels.length > 1 && (
                    <button
                      type="button"
                      className="btn"
                      title={t("lib.removeSortLevel")}
                      onClick={() => removeSortLevel(index)}
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
              <div className="panel-actions">
                {sortLevels.length < MAX_SORT_LEVELS && (
                  <button type="button" className="btn" onClick={addSortLevel}>
                    {t("lib.addSortLevel")}
                  </button>
                )}
                <button
                  type="button"
                  className="btn"
                  onClick={resetSortToDefault}
                  disabled={sortIsDefault}
                >
                  {t("lib.resetSort")}
                </button>
              </div>
            </div>

            <div className="filter-group sort-preset-row">
              <span className="filter-group-label">{t("lib.savedViews")}</span>
              <select value="" onChange={(e) => e.target.value && applyPreset(e.target.value)}>
                <option value="">{t("lib.selectSavedView")}</option>
                {presets.map((preset) => (
                  <option key={preset.name} value={preset.name}>
                    {preset.name}
                  </option>
                ))}
              </select>
              <input
                placeholder={t("lib.nameViewPlaceholder")}
                value={presetNameInput}
                onChange={(e) => setPresetNameInput(e.target.value)}
                style={{ maxWidth: 160 }}
              />
              <button
                type="button"
                className="btn"
                onClick={saveCurrentAsPreset}
                disabled={!presetNameInput.trim()}
              >
                {t("lib.saveCurrentView")}
              </button>
            </div>
            <p className="muted" style={{ margin: 0 }}>
              {t("lib.savedViewHint")}
            </p>

            {presets.length > 0 && (
              <div className="sort-preset-list">
                {presets.map((preset) => (
                  <span key={preset.name} className="sort-preset-item">
                    {preset.name}
                    <button
                      type="button"
                      className="sort-preset-remove"
                      title={t("lib.deletePreset", { name: preset.name })}
                      onClick={() => deletePreset(preset.name)}
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {openPanel === "fields" && (
          <div className="filter-panel">
            <div className="filter-group">
              <span className="filter-group-label">{t("lib.showOnCard")}</span>
              <div className="chip-row">
                {VISIBLE_FIELD_OPTIONS.map((opt) => (
                  <Chip
                    key={opt.key}
                    label={t(opt.labelKey)}
                    active={visibleFields[opt.key]}
                    onClick={() => updateVisibleField(opt.key, !visibleFields[opt.key])}
                  />
                ))}
              </div>
            </div>
            <div className="panel-actions">
              <button
                type="button"
                className="btn"
                onClick={resetVisibleFieldsToDefault}
                disabled={changedFieldCount === 0}
              >
                {t("lib.resetFields")}
              </button>
            </div>
          </div>
        )}

        {openPanel === "filter" &&
          (allTags.length > 0 ||
            allGenres.length > 0 ||
            attributeOptions.formats.length > 0 ||
            attributeOptions.media_types.length > 0) && (
          <div className="filter-panel">
            {allTags.length > 0 && (
              <div className="filter-group">
                <span className="filter-group-label">{t("field.tags")}</span>
                <div className="chip-row">
                  {allTags.map((tag) => (
                    <Chip
                      key={tag}
                      label={tag}
                      active={tagFilter.included.includes(tag)}
                      negated={tagFilter.excluded.includes(tag)}
                      onClick={() => setTagFilter((prev) => cycleFilterValue(prev, tag))}
                    />
                  ))}
                </div>
              </div>
            )}
            {/* Feature #111 — samme "distinct fra biblioteket" mønster som
                tags ovenfor, ikke en fast enum som format/lyd-type/medietype
                nedenfor. */}
            {allGenres.length > 0 && (
              <div className="filter-group">
                <span className="filter-group-label">{t("field.genres")}</span>
                <div className="chip-row">
                  {allGenres.map((genre) => (
                    <Chip
                      key={genre}
                      label={genre}
                      active={genreFilter.included.includes(genre)}
                      negated={genreFilter.excluded.includes(genre)}
                      onClick={() => setGenreFilter((prev) => cycleFilterValue(prev, genre))}
                    />
                  ))}
                </div>
              </div>
            )}
            {attributeOptions.formats.length > 0 && (
              <div className="filter-group">
                <span className="filter-group-label">{t("field.format")}</span>
                <div className="chip-row">
                  {attributeOptions.formats.map((format) => (
                    <Chip
                      key={format}
                      label={format}
                      active={formatFilter.included.includes(format)}
                      negated={formatFilter.excluded.includes(format)}
                      onClick={() => setFormatFilter((prev) => cycleFilterValue(prev, format))}
                    />
                  ))}
                </div>
              </div>
            )}
            {attributeOptions.audio_types.length > 0 && (
              <div className="filter-group">
                <span className="filter-group-label">{t("field.audio")}</span>
                <div className="chip-row">
                  {attributeOptions.audio_types.map((audioType) => (
                    <Chip
                      key={audioType}
                      label={audioType}
                      active={audioTypeFilter.included.includes(audioType)}
                      negated={audioTypeFilter.excluded.includes(audioType)}
                      onClick={() =>
                        setAudioTypeFilter((prev) => cycleFilterValue(prev, audioType))
                      }
                    />
                  ))}
                </div>
              </div>
            )}
            {attributeOptions.media_types.length > 0 && (
              <div className="filter-group">
                <span className="filter-group-label">{t("field.mediaType")}</span>
                <div className="chip-row">
                  {attributeOptions.media_types.map((mediaType) => (
                    <Chip
                      key={mediaType}
                      label={mediaType}
                      active={mediaTypeFilter.included.includes(mediaType)}
                      negated={mediaTypeFilter.excluded.includes(mediaType)}
                      onClick={() =>
                        setMediaTypeFilter((prev) => cycleFilterValue(prev, mediaType))
                      }
                    />
                  ))}
                </div>
              </div>
            )}
            <div className="filter-group">
              <span className="filter-group-label">{t("field.watchedStatus")}</span>
              <div className="chip-row">
                <Chip
                  label={t("lib.watched")}
                  active={watchedFilter === true}
                  negated={watchedFilter === false}
                  onClick={() => setWatchedFilter((prev) => cycleTriState(prev))}
                />
              </div>
            </div>
            {/* Feature #156 — kun tilbudt når Plex reelt er sat op; ellers
                ville badget bare producere en fejlbanner ved klik. */}
            {plex.status !== "unconfigured" && (
              <div className="filter-group">
                <span className="filter-group-label">{t("field.plex")}</span>
                <div className="chip-row">
                  <Chip
                    label={t("lib.onPlex")}
                    active={plexFilter === true}
                    negated={plexFilter === false}
                    onClick={() => setPlexFilter((prev) => cycleTriState(prev))}
                  />
                </div>
              </div>
            )}
            {/* Feature #157 — kun relevant på ønskelisten, samme gating som
                bestillings-status-badget på selve ønske-kortet (feature #114). */}
            {wishlist && !isGuest && attributeOptions.order_statuses.length > 0 && (
              <div className="filter-group">
                <span className="filter-group-label">{t("field.orderStatus")}</span>
                <div className="chip-row">
                  {attributeOptions.order_statuses.map((status) => (
                    <Chip
                      key={status}
                      label={status}
                      active={orderStatusFilter.included.includes(status)}
                      negated={orderStatusFilter.excluded.includes(status)}
                      onClick={() =>
                        setOrderStatusFilter((prev) => cycleFilterValue(prev, status))
                      }
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Feature #86 — knappen står der altid (deaktiveret når intet er
                valgt), så den er til at få øje på og selv fortæller om der
                er noget at rydde. Før dukkede den kun op når et filter var
                aktivt, hvilket kun hjalp den der allerede vidste det. */}
            <div className="panel-actions">
              <button
                type="button"
                className="btn"
                onClick={resetFilters}
                disabled={!hasActiveFilters}
              >
                {t("lib.clearFilters")}
              </button>
            </div>
          </div>
        )}
      </div>

      {personFilter && (
        <div className="banner banner-info person-filter-banner">
          {t(personFilter.type === "director" ? "lib.personFilterDirector" : "lib.personFilterCast")}{" "}
          <strong>{personFilter.name}</strong>
          <button type="button" className="btn" onClick={() => setPersonFilter(null)}>
            {t("lib.clear")}
          </button>
        </div>
      )}

      {settingsError && (
        <div className="banner banner-error">
          {t("lib.settingsNotSaved", { message: settingsError })}
        </div>
      )}

      {refreshError && (
        <div className="banner banner-error">
          {t("lib.refreshFailed", { message: refreshError })}
        </div>
      )}

      {savedTvShow && (
        <div className="banner banner-info" style={{ marginBottom: 16 }}>
          <span style={{ flex: 1 }}>
            {t("lib.savedTvShowNotice", {
              target: t(wishlist ? "lib.tvWishes" : "app.nav.tv"),
              here: t(wishlist ? "lib.movieWishes" : "lib.movieLibrary"),
            })}
          </span>
          {onGoToTvShows && (
            <button
              type="button"
              className="btn"
              onClick={() => {
                setSavedTvShow(false);
                onGoToTvShows();
              }}
            >
              {t("lib.showTarget", { target: t(wishlist ? "lib.tvWishes" : "app.nav.tv") })}
            </button>
          )}
          <button type="button" className="btn" onClick={() => setSavedTvShow(false)}>
            ✕
          </button>
        </div>
      )}

      {status === "loading" && (
        <div className="skeleton-grid">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="skeleton-card" />
          ))}
        </div>
      )}

      {status === "error" && (
        <div className="banner banner-error">{listError || t("lib.loadError")}</div>
      )}

      {status === "ready" && movies.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">🎞️</div>
          <p>
            {t(
              hasActiveFilters || query
                ? "lib.emptyFiltered"
                : wishlist
                  ? "lib.emptyWishlist"
                  : "lib.empty"
            )}
          </p>
        </div>
      )}

      {status === "ready" && movies.length > 0 && (
        <ul
          className={`movie-grid movie-grid--${user.settings.card_size ?? "medium"}${
            viewMode === "list" ? " movie-grid--list" : ""
          }`}
        >
          {movies.map((movie) => (
            <li key={movie.id} className="movie-card" onClick={() => setActiveMovie(movie)}>
              {/* Feature #92 — betinget af nummeret selv, ikke af
                  ønskeliste-flaget: en digital biblioteks-post har heller
                  ikke noget nummer at vise. */}
              {movie.serial_number != null && (
                <div className="movie-serial">
                  {formatSerial(movie.serial_number, serialPaddingWidth, serialPrefix(movie.media_type, "movie"))}
                </div>
              )}
              {movie.format && <div className="movie-format-badge">{movie.format}</div>}
              <div className="movie-poster">
                {movie.poster_url ? (
                  // Feature #143 — hent en poster-størrelse der passer til
                  // kortet i stedet for altid w500, så et lille kort loader
                  // et lille billede.
                  <img
                    src={posterSrc(movie.poster_url, cardPosterSize(user.settings.card_size ?? "medium"))}
                    alt={movie.title}
                    loading="lazy"
                  />
                ) : (
                  "🎬"
                )}
                {visibleFields.rating && movie.rating != null && (
                  <div className="movie-rating-badge">★ {movie.rating.toFixed(1)}</div>
                )}
                <div className="movie-badge-stack">
                  {/* Feature #144 — afventer admin-godkendelse. */}
                  {wishlist && movie.wishlist_status === "pending" && (
                    <div className="movie-wishlist-badge" title={t("lib.wishlistPending")}>
                      {t("lib.wishlistPendingShort")}
                    </div>
                  )}
                  {/* Feature #145 — navnet falder sammen med en titel i biblioteket. */}
                  {wishlist && movie.name_in_library && (
                    <div className="movie-namematch-badge" title={t("lib.nameInLibrary")}>
                      {t("lib.nameInLibraryShort")}
                    </div>
                  )}
                  {visibleFields.plex && <PlexCardBadge availability={plex.items[movie.id]} />}
                  {movie.watched && (
                    <div className="movie-watched-badge" title={t("lib.watched")}>
                      {t("detail.watchedShort")}
                    </div>
                  )}
                </div>
              </div>
              <div className="movie-info">
                <div className="movie-title">{movie.title}</div>
                <div className="movie-meta-grid">
                  {visibleFields.year && movie.year && (
                    <span className="movie-meta-item">{movie.year}</span>
                  )}
                  {visibleFields.runtime && movie.runtime && (
                    <span className="movie-meta-item">
                      {t("lib.minutes", { minutes: movie.runtime })}
                    </span>
                  )}
                  {visibleFields.format && movie.format && (
                    <span className="movie-meta-item">{movie.format}</span>
                  )}
                  {visibleFields.audioTypes && movie.audio_types.length > 0 && (
                    <span className="movie-meta-item">{movie.audio_types.join(", ")}</span>
                  )}
                  {visibleFields.mediaType && movie.media_type && (
                    <span className="movie-meta-item">{movie.media_type}</span>
                  )}
                  {visibleFields.genres && movie.genres.length > 0 && (
                    <span className="movie-meta-item">{movie.genres.join(", ")}</span>
                  )}
                </div>
                {/* Feature #144/#165 — admin godkender eller afviser ønsket
                    direkte fra kortet. */}
                {wishlist && isAdmin && movie.wishlist_status === "pending" && (
                  <div className="movie-wishlist-actions">
                    <button
                      type="button"
                      className="btn btn-primary movie-approve-btn"
                      onClick={(e) => approveWishlist(movie, e)}
                    >
                      {t("lib.approveWishlist")}
                    </button>
                    <button
                      type="button"
                      className="btn movie-reject-btn"
                      onClick={(e) => rejectWishlist(movie, e)}
                    >
                      {t("lib.rejectWishlist")}
                    </button>
                  </div>
                )}
                {/* Feature #114 — bestillingsstatus vises kun på ønske-kort,
                    i både grid- og liste-visning (samme markup, jf. #108).
                    Feature #116 — skjult for gæster, som ikke ser order-status. */}
                {movie.is_wishlist && !isGuest && (
                  <div className="movie-tags">
                    <span
                      className={`movie-order-badge${movie.order_status ? "" : " movie-order-badge--none"}`}
                    >
                      {movie.order_status || t("orderStatus.notOrdered")}
                    </span>
                  </div>
                )}
                {visibleFields.tags && movie.tags.length > 0 && (
                  <div className="movie-tags">
                    {movie.tags.map((tag) => (
                      <span key={tag} className="movie-tag-pill">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {status === "ready" && total > 0 && (
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={(nextPageSize) => {
            setPageSize(nextPageSize);
            persistPageSize(nextPageSize);
          }}
        />
      )}

      {activeMovie && (
        <MovieDetailModal
          movie={activeMovie}
          user={user}
          allTags={allTags}
          allOwners={allOwners}
          allLocations={allLocations}
          attributeOptions={attributeOptions}
          serialPaddingWidth={serialPaddingWidth}
          plex={plex}
          plexAvailability={plex.items[activeMovie.id]}
          onClose={() => setActiveMovie(null)}
          onChanged={() => {
            refresh();
            api.listTags().then(setAllTags).catch(() => {});
            api.listOwners().then(setAllOwners).catch(() => {});
            api.listLocations().then(setAllLocations).catch(() => {});
          }}
          onFilterByPerson={(type, name) => {
            setPersonFilter({ type, name });
            setActiveMovie(null);
          }}
        />
      )}
    </section>
  );
}

export function MovieDetailModal({
  movie,
  user,
  allTags,
  allOwners,
  allLocations,
  attributeOptions,
  serialPaddingWidth,
  // Feature #88 — valgfri: MovieLookupForm genbruger dette vindue til en
  // netop scannet film, hvor der endnu ikke findes nogen Plex-status at vise.
  plex,
  plexAvailability,
  // Feature #106 — begge valgfri, kun sat af MovieLookupForm i
  // "kladde"-tilstand: `duplicates` er dublet-tjekket der tidligere stod i
  // et separat mellemtrin, `onBackToCandidates` går tilbage til
  // kandidat-gitteret uden at gemme noget, hvis det viste sig at være det
  // forkerte match.
  duplicates,
  onBackToCandidates,
  onClose,
  onChanged,
  onFilterByPerson,
}) {
  const t = useT();
  const locale = useLocale();
  // Feature #125 — registrér et titel-besøg når en gemt film åbnes. Kun for
  // rigtige poster (`movie.id`), ikke for MovieLookupForms kladde-tilstand.
  // Fire-and-forget, [movie.id] så et nyt åbnet kort tæller igen.
  useEffect(() => {
    if (movie.id) {
      api
        .recordVisit({
          page: "title",
          kind: "title",
          resource_kind: "movie",
          resource_id: movie.id,
          title: movie.title,
        })
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [movie.id]);
  const [tagsInput, setTagsInput] = useState(movie.tags.join(", "));
  const [format, setFormat] = useState(movie.format ?? "");
  const [audioTypes, setAudioTypes] = useState(movie.audio_types);
  const [mediaType, setMediaType] = useState(movie.media_type ?? "");
  const [serialNumberInput, setSerialNumberInput] = useState(
    movie.serial_number != null ? String(movie.serial_number) : ""
  );
  const [location, setLocation] = useState(movie.location ?? "");
  const [owner, setOwner] = useState(movie.owner ?? "");
  // Feature #123 — undertekster som liste: faste valg Eng/DK + fritekst under
  // "Andet" (se SubtitlesPicker). Tidligere ét frit tekstfelt (#109).
  const [subtitles, setSubtitles] = useState(movie.subtitles ?? []);
  // Feature #114 — bestillingsstatus, kun relevant/synligt for ønskeliste-poster.
  // Tom streng = "Ikke bestilt" (gemmes som null); de tre bestilte kilder er enum-værdier.
  const [orderStatus, setOrderStatus] = useState(movie.order_status ?? "");
  const [personalRating, setPersonalRating] = useState(
    movie.personal_rating != null ? String(movie.personal_rating) : ""
  );
  const [personalNote, setPersonalNote] = useState(movie.personal_note ?? "");
  const isGuest = user.role === "guest";
  // Feature #101 — vinduet åbner i læsevisning (Jans ønske 2026-08-09).
  // Undtagelsen er "kladde"-tilstanden fra scan-flowet: en film der endnu
  // ikke findes, er der intet at læse på, og man er kommet for at udfylde
  // den. Guests kan aldrig skifte til redigering.
  const [editing, setEditing] = useState(!movie.id);

  function addTag(tag) {
    const current = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
    if (current.some((t) => t.toLowerCase() === tag.toLowerCase())) return;
    setTagsInput([...current, tag].join(", "));
  }
  const [watched, setWatched] = useState(movie.watched);
  const [watchedAt, setWatchedAt] = useState(
    movie.watched_at ? movie.watched_at.slice(0, 10) : ""
  );
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [moving, setMoving] = useState(false);
  const [error, setError] = useState(null);

  /** Feature #101 — kaster ændringer væk og går tilbage til læsevisningen.
   *  Sat lige efter alle useState-linjerne, så nulstillingen og
   *  initialiseringen står tæt nok på hinanden til at kunne holdes ens —
   *  et nyt felt skal huskes begge steder. */
  function cancelEditing() {
    setTagsInput(movie.tags.join(", "));
    setFormat(movie.format ?? "");
    setAudioTypes(movie.audio_types);
    setMediaType(movie.media_type ?? "");
    setSerialNumberInput(movie.serial_number != null ? String(movie.serial_number) : "");
    setLocation(movie.location ?? "");
    setOwner(movie.owner ?? "");
    setSubtitles(movie.subtitles ?? []);
    setOrderStatus(movie.order_status ?? "");
    setPersonalRating(movie.personal_rating != null ? String(movie.personal_rating) : "");
    setPersonalNote(movie.personal_note ?? "");
    setWatched(movie.watched);
    setWatchedAt(movie.watched_at ? movie.watched_at.slice(0, 10) : "");
    setError(null);
    setEditing(false);
  }

  const canEditSerial = user.role === "admin" || user.username === movie.registered_by;

  // Feature #92 — en biblioteks-post skal have både medietype og format før
  // den kan gemmes; backend afviser den ellers (MovieCreate-validatoren).
  // Ønskelisten er undtaget: man ejer ikke det man ønsker sig endnu.
  const missingClassification = !movie.is_wishlist && (!mediaType || !format);

  const dirty = useMemo(() => {
    if (!movie.id) return true; // "kladde"-tilstand — Gem må altid være aktiv (feature #79)
    const tagsChanged =
      tagsInput.split(",").map((t) => t.trim()).filter(Boolean).join(",") !==
      movie.tags.join(",");
    const serialChanged =
      canEditSerial &&
      Number(serialNumberInput) > 0 &&
      Number(serialNumberInput) !== movie.serial_number;
    return (
      tagsChanged ||
      format !== (movie.format ?? "") ||
      audioTypes.join(",") !== movie.audio_types.join(",") ||
      mediaType !== (movie.media_type ?? "") ||
      location !== (movie.location ?? "") ||
      owner !== (movie.owner ?? "") ||
      subtitles.join("|") !== (movie.subtitles ?? []).join("|") ||
      orderStatus !== (movie.order_status ?? "") ||
      personalRating !== (movie.personal_rating != null ? String(movie.personal_rating) : "") ||
      personalNote !== (movie.personal_note ?? "") ||
      watched !== movie.watched ||
      watchedAt !== (movie.watched_at ? movie.watched_at.slice(0, 10) : "") ||
      serialChanged
    );
  }, [
    tagsInput,
    format,
    audioTypes,
    mediaType,
    serialNumberInput,
    location,
    owner,
    subtitles,
    orderStatus,
    personalRating,
    personalNote,
    watched,
    watchedAt,
    canEditSerial,
    movie,
  ]);

  function toggleWatched() {
    setWatched((prev) => {
      const next = !prev;
      if (next && !watchedAt) {
        setWatchedAt(new Date().toISOString().slice(0, 10));
      }
      return next;
    });
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        tags: tagsInput.split(",").map((t) => t.trim()).filter(Boolean),
        format: format || null,
        audio_types: audioTypes,
        media_type: mediaType || null,
        location: location.trim() || null,
        owner: owner.trim() || null,
        subtitles,
        order_status: orderStatus || null,
        personal_rating: personalRating ? Number(personalRating) : null,
        personal_note: personalNote.trim() || null,
        watched,
        watched_at: watched && watchedAt ? watchedAt : null,
      };
      if (movie.id) {
        const nextSerial = Number(serialNumberInput);
        if (canEditSerial && nextSerial > 0 && nextSerial !== movie.serial_number) {
          // BUGS.md #56 — er nummeret allerede taget i samme serie, bytter de
          // to poster plads. Bekræft først, og vis hvilken titel man bytter med
          // (kan være en digital TV-serie, da D#-serien er delt). Prefikset
          // (M/D) styres af medietypen, ikke af noget man taster her.
          const holder = await api.getSerialSwapTarget(movie.id, nextSerial);
          if (holder?.title) {
            const confirmed = window.confirm(
              t("detail.serialSwapConfirm", { serial: nextSerial, title: holder.title })
            );
            if (!confirmed) return; // finally nulstiller saving
          }
          payload.serial_number = nextSerial;
        }
        await api.updateMovie(movie.id, payload);
      } else {
        // "Kladde"-tilstand (feature #79) — intet er oprettet endnu, dette
        // ER selve oprettelsen. movie er her et forhåndsvist TMDb-objekt
        // (se MovieLookupForm.jsx), ikke en gemt film.
        //
        // Feature #128 — findes titlen allerede (på ønskelisten eller i
        // biblioteket), kræv en aktiv OK/Annuller-bekræftelse før en kopi mere
        // oprettes (Jans ønske 2026-08-12). Banneret ovenfor oplyser passivt;
        // dette er den blokerende dialog man skal svare på først.
        if (duplicates?.length > 0) {
          const where = duplicates
            .map((d) =>
              d.is_wishlist ? t("scan.duplicateOnWishlist") : t("scan.duplicateInLibrary")
            )
            .join(t("scan.duplicateJoin"));
          if (!window.confirm(t("scan.duplicateConfirm", { where }))) return;
        }
        await api.createMovie({
          ...payload,
          tmdb_id: movie.tmdb_id,
          barcode: movie.barcode,
          barcode_source: movie.barcode_source,
          is_wishlist: movie.is_wishlist,
        });
        // Feature #147 — registrerer man til biblioteket (ikke ønskelisten) og
        // titlen allerede lå på ønskelisten, så tilbyd at fjerne ønsket derfra
        // (man ejer den jo nu). Kun ønske-dubletter, aldrig en biblioteks-kopi.
        if (!movie.is_wishlist) {
          const wish = duplicates?.find((d) => d.is_wishlist);
          if (wish && window.confirm(t("scan.removeFromWishlistConfirm", { title: wish.title }))) {
            await api.deleteMovie(wish.id);
          }
        }
      }
      onChanged();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Slet "${movie.title}" fra biblioteket?`)) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deleteMovie(movie.id);
      onChanged();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  }

  async function moveToLibrary() {
    setMoving(true);
    setError(null);
    try {
      await api.updateMovie(movie.id, { is_wishlist: false });
      onChanged();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setMoving(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-poster">
            {movie.poster_url ? <img src={movie.poster_url} alt={movie.title} /> : "🎬"}
          </div>
          <div>
            <h2>{movie.title}</h2>
            <p className="muted">
              {movie.year ?? t("detail.yearUnknown")}
              {movie.serial_number != null && (
                <>
                  {" · "}
                  {t("detail.serialShort", {
                    serial: formatSerial(
                      movie.serial_number,
                      serialPaddingWidth,
                      serialPrefix(movie.media_type, "movie")
                    ),
                  })}
                </>
              )}
              {!movie.id && <> · {t("detail.notCreatedYet")}</>}
              {movie.runtime != null && <> · {t("lib.minutes", { minutes: movie.runtime })}</>}
              {movie.rating != null && <> · ★ {movie.rating.toFixed(1)}</>}
              {movie.personal_rating != null && (
                <> · {t("detail.yourRatingShort", { rating: movie.personal_rating })}</>
              )}
              {movie.watched && (
                <>
                  {" · "}
                  {movie.watched_at
                    ? t("detail.watchedOn", {
                        date: new Date(movie.watched_at).toLocaleDateString(locale),
                      })
                    : t("detail.watchedShort")}
                </>
              )}
            </p>
            {(movie.imdb_url || movie.trailer_url || movie.tmdb_id) && (
              <p className="external-links">
                {movie.imdb_url && (
                  <a href={movie.imdb_url} target="_blank" rel="noreferrer">
                    IMDb
                  </a>
                )}
                {movie.trailer_url && (
                  <a href={movie.trailer_url} target="_blank" rel="noreferrer">
                    Trailer
                  </a>
                )}
                {movie.tmdb_id && (
                  <a
                    href={`https://www.themoviedb.org/movie/${movie.tmdb_id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    TMDb
                  </a>
                )}
              </p>
            )}
          </div>
          <button type="button" className="btn modal-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          {/* Feature #106 — dette mellemtrin flyttede fra et separat kort
              før rediger-boksen ind i selve boksen: et dublet-fund ændrer
              intet ved oprettelsen, kun brugeren skal have besked om det. */}
          {!movie.id && duplicates?.length > 0 && (
            <div className="banner banner-error">
              {t("scan.duplicateIntro", {
                what: t("scan.duplicateMovie"),
                where: duplicates
                  .map((d) =>
                    d.is_wishlist
                      ? t("scan.duplicateOnWishlist")
                      : `${t("scan.duplicateInLibrary")}${duplicateSerialSuffix(d, "movie", serialPaddingWidth)}`
                  )
                  .join(t("scan.duplicateJoin")),
              })}
            </div>
          )}
          {movie.overview && <p>{movie.overview}</p>}
          {movie.director && (
            <p className="muted">
              <strong>{t("detail.director")}</strong>{" "}
              <button
                type="button"
                className="person-link"
                onClick={() => onFilterByPerson("director", movie.director)}
              >
                {movie.director}
              </button>
            </p>
          )}
          {movie.cast.length > 0 && (
            <p className="muted">
              <strong>{t("detail.cast")}</strong>{" "}
              {movie.cast.map((name, i) => (
                <span key={name}>
                  <button
                    type="button"
                    className="person-link"
                    onClick={() => onFilterByPerson("cast", name)}
                  >
                    {name}
                  </button>
                  {i < movie.cast.length - 1 ? ", " : ""}
                </span>
              ))}
            </p>
          )}

          {movie.id && movie.collection_id && (
            <CollectionSection movie={movie} onChanged={onChanged} />
          )}

          {/* Feature #88/2026-08-10 — en fysisk kopi er per definition ikke i
              Plex; at vise "Ikke fundet i Plex" på hver eneste DVD/Blu-ray
              ville bare være støj for den der udelukkende har et fysisk
              bibliotek. */}
          {movie.id && movie.media_type !== "Fysisk" && (
            <div className="plex-actions-row">
              <PlexPlayLink availability={plexAvailability} plex={plex} />
              <PlexShieldPlayButton
                availability={plexAvailability}
                shieldConfigured={plex.shieldConfigured}
                kind="movie"
                itemId={movie.id}
                isAdmin={user.role === "admin"}
                playAllowed={plex.playAllowed}
              />
            </div>
          )}

          {!editing ? (
            <>
              {/* Feature #87 — korte felter står to og to (én kolonne på en
                  telefon), så vinduet ikke bliver en lang scroll af
                  enkeltlinjer. Kun Tags/note/lyd-type får fuld bredde. */}
              <div className="modal-field-row">
                {movie.serial_number != null && (
                  <div>
                    <div className="modal-section-label">{t("field.serialNumber")}</div>
                    <p>
                      {formatSerial(movie.serial_number, serialPaddingWidth, serialPrefix(movie.media_type, "movie"))}
                    </p>
                  </div>
                )}
                <div>
                  <div className="modal-section-label">{t("field.watchedStatus")}</div>
                  <p>
                    {movie.watched
                      ? movie.watched_at
                        ? t("detail.watchedOn", {
                            date: new Date(movie.watched_at).toLocaleDateString(locale),
                          })
                        : t("detail.watchedShort")
                      : t("lib.notWatched")}
                  </p>
                </div>
              </div>
              <div>
                <div className="modal-section-label">{t("field.tags")}</div>
                <p>{movie.tags.length > 0 ? movie.tags.join(", ") : t("detail.noTags")}</p>
              </div>
              {movie.genres.length > 0 && (
                <div>
                  <div className="modal-section-label">{t("field.genres")}</div>
                  <p>{movie.genres.join(", ")}</p>
                </div>
              )}
              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">{t("field.location")}</div>
                  <p>{movie.location || "—"}</p>
                </div>
                <div>
                  <div className="modal-section-label">{t("field.owner")}</div>
                  <p>{movie.owner || "—"}</p>
                </div>
              </div>
              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">{t("field.format")}</div>
                  <p>{movie.format || t("detail.notSpecified")}</p>
                </div>
                <div>
                  <div className="modal-section-label">{t("field.mediaType")}</div>
                  <p>{movie.media_type || t("detail.notSpecified")}</p>
                </div>
              </div>
              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">{t("field.personalRating")}</div>
                  <p>{movie.personal_rating != null ? `${movie.personal_rating}/10` : "—"}</p>
                </div>
                {movie.registered_by && (
                  <div>
                    <div className="modal-section-label">{t("field.registeredBy")}</div>
                    <p>{movie.registered_by}</p>
                  </div>
                )}
              </div>
              <div>
                <div className="modal-section-label">{t("field.audioType")}</div>
                <p>{movie.audio_types.length > 0 ? movie.audio_types.join(", ") : "—"}</p>
              </div>
              <div>
                <div className="modal-section-label">{t("field.subtitles")}</div>
                <p>{movie.subtitles?.length ? movie.subtitles.join(", ") : "—"}</p>
              </div>
              {/* Feature #116 — bestillingsstatus skjules helt for gæster. */}
              {movie.is_wishlist && !isGuest && (
                <div>
                  <div className="modal-section-label">{t("field.orderStatus")}</div>
                  <p>{movie.order_status || t("orderStatus.notOrdered")}</p>
                </div>
              )}
              <div>
                <div className="modal-section-label">{t("field.personalNote")}</div>
                <p>{movie.personal_note || "—"}</p>
              </div>
            </>
          ) : (
            <>
              {!movie.id && (
                <p className="muted">{t("detail.createHint")}</p>
              )}
              {/* Feature #87 — se den tilsvarende gruppering i guest-visningen
                  ovenfor: korte felter to og to, kun de brede står alene. */}
              <div className="modal-field-row">
                {movie.serial_number != null && (
                  <div>
                    <div className="modal-section-label">{t("field.serialNumber")}</div>
                    <input
                      type="number"
                      min="1"
                      disabled={!canEditSerial}
                      value={serialNumberInput}
                      onChange={(e) => setSerialNumberInput(e.target.value)}
                      style={{ width: 100 }}
                    />
                    {canEditSerial ? (
                      <p className="muted" style={{ marginTop: 4 }}>
                        {t("detail.serialSwapHint")}
                      </p>
                    ) : (
                      <p className="muted" style={{ marginTop: 4 }}>
                        {t("detail.serialLockedHint", {
                          who: movie.registered_by ?? t("detail.serialLockedFallback"),
                        })}
                      </p>
                    )}
                  </div>
                )}

                <div>
                  <div className="modal-section-label">{t("field.watchedStatus")}</div>
                  <label className="watched-toggle">
                    <input type="checkbox" checked={watched} onChange={toggleWatched} />
                    {t("lib.watched")}
                  </label>
                  {watched && (
                    <input
                      type="date"
                      value={watchedAt}
                      onChange={(e) => setWatchedAt(e.target.value)}
                      style={{ marginTop: 6, display: "block" }}
                    />
                  )}
                </div>
              </div>

              <div>
                <div className="modal-section-label">{t("field.tags")}</div>
                {/* Feature #138 — gæster vælger ikke tags; ønsket tagges
                    obligatorisk "Tilføjet af {navn}" af backenden (#4). Alle
                    andre vælger eksisterende tags fra en dropdown (+ fri tekst
                    til nye) i stedet for en chip-væg (#5). */}
                {isGuest ? (
                  <p className="muted">{t("detail.guestTagNote", { name: user.username })}</p>
                ) : (
                  <>
                    <input value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} />
                    {allTags.length > 0 && (
                      <select
                        value=""
                        onChange={(e) => {
                          if (e.target.value) addTag(e.target.value);
                        }}
                        style={{ marginTop: 8, display: "block" }}
                      >
                        <option value="">{t("detail.pickTag")}</option>
                        {allTags.map((tag) => (
                          <option key={tag} value={tag}>
                            {tag}
                          </option>
                        ))}
                      </select>
                    )}
                  </>
                )}
              </div>

              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">{t("field.location")}</div>
                  <Combobox
                    value={location}
                    onChange={setLocation}
                    options={allLocations}
                    placeholder={t("detail.locationPlaceholder")}
                  />
                </div>

                <div>
                  <div className="modal-section-label">{t("field.owner")}</div>
                  <Combobox
                    value={owner}
                    onChange={setOwner}
                    options={allOwners}
                    placeholder={t("detail.ownerPlaceholder")}
                  />
                </div>
              </div>

              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">{t("field.format")}</div>
                  <select value={format} onChange={(e) => setFormat(e.target.value)}>
                    <option value="">{t("detail.notSpecified")}</option>
                    {attributeOptions.formats.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <div className="modal-section-label">{t("field.mediaType")}</div>
                  <select value={mediaType} onChange={(e) => setMediaType(e.target.value)}>
                    <option value="">{t("detail.notSpecified")}</option>
                    {attributeOptions.media_types.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">{t("field.personalRatingRange")}</div>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={personalRating}
                    onChange={(e) => setPersonalRating(e.target.value)}
                    style={{ width: 80 }}
                  />
                </div>

                {movie.registered_by && (
                  <div>
                    <div className="modal-section-label">{t("field.registeredBy")}</div>
                    <p className="muted" style={{ margin: 0 }}>
                      {movie.registered_by}
                    </p>
                  </div>
                )}
              </div>

              <div>
                <div className="modal-section-label">{t("field.audioType")}</div>
                <div className="chip-row">
                  {attributeOptions.audio_types.map((audioType) => (
                    <Chip
                      key={audioType}
                      label={audioType}
                      active={audioTypes.includes(audioType)}
                      onClick={() => setAudioTypes((prev) => toggleValue(prev, audioType))}
                    />
                  ))}
                </div>
              </div>

              <div>
                <div className="modal-section-label">{t("field.subtitles")}</div>
                <SubtitlesPicker
                  value={subtitles}
                  onChange={setSubtitles}
                  options={attributeOptions.subtitles}
                />
              </div>

              {movie.is_wishlist && !isGuest && (
                <div>
                  <div className="modal-section-label">{t("field.orderStatus")}</div>
                  <select value={orderStatus} onChange={(e) => setOrderStatus(e.target.value)}>
                    <option value="">{t("orderStatus.notOrdered")}</option>
                    {attributeOptions.order_statuses.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <div className="modal-section-label">{t("field.personalNote")}</div>
                <textarea
                  value={personalNote}
                  onChange={(e) => setPersonalNote(e.target.value)}
                  placeholder={t("detail.notePlaceholder")}
                  rows={3}
                  style={{ width: "100%", resize: "vertical" }}
                />
              </div>
            </>
          )}

          {error && <div className="banner banner-error">{error}</div>}
          {missingClassification && (
            <div className="banner banner-info">{t("detail.classificationRequired")}</div>
          )}
        </div>

        {!editing ? (
          // Feature #72's later refinement: guests may still request a
          // screening (their one allowed write action) even though the
          // rest of the footer (save/delete/move) stays hidden for them.
          // Feature #101 — samme fod bruges nu af alle i læsevisning; kun
          // "Redigér" er betinget af rollen.
          <div className="modal-footer">
            {movie.id && <ScreeningRequestButton mediaKind="movie" id={movie.id} username={user.username} />}
            {!isGuest && (
              <button type="button" className="btn btn-primary" onClick={() => setEditing(true)}>
                {t("detail.edit")}
              </button>
            )}
          </div>
        ) : (
          <div className="modal-footer">
            {movie.id && (
              <button type="button" className="btn" onClick={remove} disabled={deleting}>
                {t(deleting ? "detail.deleting" : "detail.deleteMovie")}
              </button>
            )}
            {movie.id && movie.is_wishlist && (
              <button type="button" className="btn" onClick={moveToLibrary} disabled={moving}>
                {t(moving ? "detail.moving" : "detail.moveToLibrary")}
              </button>
            )}
            {movie.id && <ScreeningRequestButton mediaKind="movie" id={movie.id} username={user.username} />}
            {/* Kun for en film der allerede findes: i kladde-tilstand er
                der ingen læsevisning at fortryde tilbage til. */}
            {movie.id && (
              <button type="button" className="btn" onClick={cancelEditing} disabled={saving}>
                {t("common.cancel")}
              </button>
            )}
            {/* Feature #106 — modstykket til den tidligere "Annullér" i
                kladde-tilstand: viste det sig at være det forkerte match,
                går man tilbage til kandidat-gitteret i stedet for helt at
                forlade scan-/søge-flowet. */}
            {!movie.id && onBackToCandidates && (
              <button type="button" className="btn" onClick={onBackToCandidates} disabled={saving}>
                {t("scan.backToCandidates")}
              </button>
            )}
            <button
              type="button"
              className="btn btn-primary"
              onClick={save}
              disabled={!dirty || saving || missingClassification}
            >
              {saving
                ? t("common.saving")
                : t(movie.id ? "detail.saveChanges" : "detail.create")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function CollectionSection({ movie, onChanged }) {
  const t = useT();
  const [expanded, setExpanded] = useState(false);
  const [collection, setCollection] = useState(null);
  const [status, setStatus] = useState("idle");
  const [addingId, setAddingId] = useState(null);
  const [addError, setAddError] = useState(null);

  function load() {
    setStatus("loading");
    api
      .getCollection(movie.collection_id)
      .then((data) => {
        setCollection(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }

  function toggle() {
    setExpanded((prev) => {
      const next = !prev;
      if (next && !collection) load();
      return next;
    });
  }

  async function addPart(part) {
    setAddError(null);
    // "Følg forælderen" (Jans valg 2026-08-11, BUGS.md #58): ser man en
    // ønskeliste-film, tilføjes søsterfilmen til ønskelisten; ser man en ejet
    // film, skal søsteren også ejes. En ejet biblioteksfilm kræver format +
    // medietype (feature #92 / MovieCreate.require_media_type_and_format_for_library),
    // som ikke kan vælges her i samlingslisten — så i stedet for at sende et
    // kald vi ved backend afviser med 422, henviser vi til det fulde tilføj-flow.
    if (!movie.is_wishlist) {
      setAddError(t("collection.addNeedsFullFlow"));
      return;
    }
    setAddingId(part.tmdb_id);
    try {
      await api.createMovie({ tmdb_id: part.tmdb_id, is_wishlist: true });
      load();
      onChanged();
    } catch (err) {
      // Vis den specifikke fejl (CLAUDE.md regel 16) i stedet for at sluge den —
      // knappen så ellers bare ud til ikke at gøre noget (BUGS.md #58).
      setAddError(err.message);
    } finally {
      setAddingId(null);
    }
  }

  const ownedCount = collection?.parts.filter((p) => p.owned && !p.owned_is_wishlist).length ?? null;

  return (
    <div>
      <button type="button" className="person-link" onClick={toggle}>
        {t("collection.partOf", { name: movie.collection_name })}{" "}
        {ownedCount != null &&
          t("collection.ownedOf", { owned: ownedCount, total: collection.parts.length })}{" "}
        {expanded ? "▴" : "▾"}
      </button>

      {expanded && (
        <div className="collection-parts">
          {status === "loading" && <p className="muted">{t("common.loading")}</p>}
          {status === "error" && (
            <div className="banner banner-error">{t("collection.loadError")}</div>
          )}
          {addError && <div className="banner banner-error">{addError}</div>}
          {status === "ready" &&
            collection.parts.map((part) => (
              <div key={part.tmdb_id} className="collection-part-row">
                <span>
                  {part.title} {part.year ? `(${part.year})` : ""}
                </span>
                {part.owned ? (
                  <span className="muted">
                    {t(part.owned_is_wishlist ? "collection.onWishlist" : "collection.owned")}
                  </span>
                ) : (
                  <button
                    type="button"
                    className="btn"
                    onClick={() => addPart(part)}
                    disabled={addingId === part.tmdb_id}
                  >
                    {t(
                      addingId === part.tmdb_id
                        ? "collection.adding"
                        : movie.is_wishlist
                          ? "collection.addWish"
                          : "collection.add"
                    )}
                  </button>
                )}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
