import { useEffect, useState } from "react";
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
import "../pages/Library.css";
import "./TvShows.css";

// Feature #89 — se Library.jsx' identiske note: `labelKey` frem for
// `label`, fordi listen evalueres ved import, før nogen oversætter findes.
const SORT_OPTIONS = [
  // Feature #96 — se den identiske note i Library.jsx.
  { value: "serial_number", labelKey: "sort.serialDigitalFirst" },
  { value: "serial_number_physical", labelKey: "sort.serialShowsFirst" },
  { value: "created_at", labelKey: "field.added" },
  { value: "name", labelKey: "field.name" },
  // Feature #184 — se den identiske note i Library.jsx.
  { value: "name_no_article", labelKey: "sort.nameNoArticle" },
  { value: "year", labelKey: "field.year" },
  { value: "rating", labelKey: "field.rating" },
  { value: "personal_rating", labelKey: "field.personalRating" },
  { value: "watched_at", labelKey: "field.watchedDate" },
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

// Feature #86 — se den identiske blok i Library.jsx: standardværdierne ét
// sted, så markering og nulstilling måler mod det samme.
const DEFAULT_SORT_LEVELS = [{ field: "serial_number", direction: "desc" }];

function initialSortLevels(settings) {
  if (settings?.tv_sort_levels?.length) return settings.tv_sort_levels;
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
  plex: false,
  genres: false,
};

function visibleFieldsFromSettings(settings) {
  const vf = settings?.tv_visible_fields ?? {};
  return {
    year: vf.year ?? DEFAULT_VISIBLE_FIELDS.year,
    tags: vf.tags ?? DEFAULT_VISIBLE_FIELDS.tags,
    format: vf.format ?? DEFAULT_VISIBLE_FIELDS.format,
    audioTypes: vf.audio_types ?? DEFAULT_VISIBLE_FIELDS.audioTypes,
    mediaType: vf.media_type ?? DEFAULT_VISIBLE_FIELDS.mediaType,
    rating: vf.rating ?? DEFAULT_VISIBLE_FIELDS.rating,
    plex: vf.plex ?? DEFAULT_VISIBLE_FIELDS.plex,
    genres: vf.genres ?? DEFAULT_VISIBLE_FIELDS.genres,
  };
}

function toggleValue(list, value) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/**
 * `onGoToMovies` (valgfri) — spejlbilledet af `Library`s `onGoToTvShows`:
 * genvej til film-visningen når add-panelets scan/søgning endte med en film,
 * som denne side aldrig kan vise (BUGS.md #47).
 */
export default function TvShows({
  user,
  onSettingsChanged,
  wishlist = false,
  onGoToMovies,
  // Feature #94 — se den identiske note i Library.jsx.
  onLibraryChanged,
}) {
  const t = useT();
  const isGuest = user.role === "guest";
  const isAdmin = user.role === "admin";
  const [query, setQuery] = useState("");
  // Feature #156 — se den identiske note i Library.jsx: {included, excluded}.
  const [tagFilter, setTagFilter] = useState(EMPTY_FILTER_STATE);
  const [formatFilter, setFormatFilter] = useState(EMPTY_FILTER_STATE);
  const [audioTypeFilter, setAudioTypeFilter] = useState(EMPTY_FILTER_STATE);
  const [mediaTypeFilter, setMediaTypeFilter] = useState(EMPTY_FILTER_STATE);
  // Feature #111 — se den identiske note i Library.jsx.
  const [genreFilter, setGenreFilter] = useState(EMPTY_FILTER_STATE);
  const [allGenres, setAllGenres] = useState([]);
  // Feature #157 — se den identiske note i Library.jsx.
  const [orderStatusFilter, setOrderStatusFilter] = useState(EMPTY_FILTER_STATE);
  const [watchedFilter, setWatchedFilter] = useState(null);
  const [plexFilter, setPlexFilter] = useState(null);
  const [sortLevels, setSortLevels] = useState(() => initialSortLevels(user.settings));
  const [shows, setShows] = useState([]);
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
  const [activeShow, setActiveShow] = useState(null);
  const [visibleFields, setVisibleFields] = useState(() => visibleFieldsFromSettings(user.settings));
  // Feature #108 — se den identiske note i Library.jsx.
  const [viewMode, setViewMode] = useState(user.settings.view_mode ?? "grid");
  // Feature #164 — se den identiske note i Library.jsx.
  const [openPanel, setOpenPanel] = useState(null); // null | "sort" | "filter" | "fields"
  const togglePanel = (name) => setOpenPanel((current) => (current === name ? null : name));
  // Feature #126 — tilføj-flowets to store knapper: "scan" | "manual" | null
  // (spejler Library.jsx). Erstatter det tidligere `showAddPanel`.
  const [addMode, setAddMode] = useState(null);
  const [serialPaddingWidth, setSerialPaddingWidth] = useState(0);
  const [settingsError, setSettingsError] = useState(null);
  // BUGS.md #61 — se den identiske note i Library.jsx.
  const [refreshError, setRefreshError] = useState(null);
  // Feature #156 — se den identiske note i Library.jsx.
  const [listError, setListError] = useState(null);
  const [savedMovie, setSavedMovie] = useState(false);
  // Feature #88 — "show" er Plex' eget navn for en TV-serie-sektion.
  const plex = usePlexAvailability("show");

  // BUGS.md #45 — see the identical helper in Library.jsx: a failed settings
  // save must be shown, not swallowed, since the UI reflects the change from
  // local state regardless of whether it was actually persisted.
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
      tv_visible_fields: {
        year: nextVisible.year,
        tags: nextVisible.tags,
        format: nextVisible.format,
        audio_types: nextVisible.audioTypes,
        media_type: nextVisible.mediaType,
        rating: nextVisible.rating,
        plex: nextVisible.plex,
        genres: nextVisible.genres,
      },
    });
  }

  function persistSortLevels(nextLevels) {
    persistSettings({ tv_sort_levels: nextLevels });
  }

  useEffect(() => {
    api.listTags().then(setAllTags).catch(() => {});
    api.listOwners().then(setAllOwners).catch(() => {});
    api.listLocations().then(setAllLocations).catch(() => {});
    api.tvAttributeOptions().then(setAttributeOptions).catch(() => {});
    api.listTvGenres().then(setAllGenres).catch(() => {});
    api
      .getSerialNumberConfig()
      .then((config) => setSerialPaddingWidth(config.padding_width))
      .catch(() => {});
  }, []);

  function fetchShows() {
    return api.listTvShows({
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
      page,
      pageSize,
    });
  }

  // See Library.jsx's identical pattern — separate effect so page resets to
  // 1 before the fetch effect below reads it (feature #15).
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
    pageSize,
  ]);

  useEffect(() => {
    setStatus("loading");
    setListError(null);
    fetchShows()
      .then((data) => {
        setShows(data.items);
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
    page,
    pageSize,
  ]);

  function persistPageSize(nextPageSize) {
    persistSettings({ page_size: nextPageSize });
  }

  function refresh() {
    onLibraryChanged?.();
    fetchShows()
      .then((data) => {
        setShows(data.items);
        setTotal(data.total);
        setRefreshError(null);
      })
      .catch((err) => setRefreshError(err.message));
  }

  // Feature #144 — admin godkender et afventende TV-ønske fra kortet.
  async function approveWishlist(show, event) {
    event.stopPropagation();
    try {
      await api.updateTvShow(show.id, { wishlist_status: "approved" });
      refresh();
    } catch (err) {
      setRefreshError(err.message);
    }
  }

  // Feature #165 — se den identiske note i Library.jsx.
  async function rejectWishlist(show, event) {
    event.stopPropagation();
    const message = window.prompt(t("lib.rejectWishlistPrompt"));
    if (message === null) return;
    try {
      await api.rejectTvShowWishlist(show.id, message);
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

  // Feature #86 — se Library.jsx' identiske blok.
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
    (plexFilter != null ? 1 : 0);
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
  }

  function resetVisibleFieldsToDefault() {
    setVisibleFields(DEFAULT_VISIBLE_FIELDS);
    persistVisibleFields(DEFAULT_VISIBLE_FIELDS);
  }

  // Feature #126 — delte toolbar-dele, så TV-siden og TV-ønskelisten kan dele
  // dem uden duplikering (spejler mønstret i Library.jsx).
  const searchInputWrap = (placeholder) => (
    <div className="search-input-wrap">
      <input
        type="search"
        placeholder={placeholder}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {/* Feature #102 — se den identiske note i Library.jsx. */}
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
        <h1>{t(wishlist ? "tv.wishlistTitle" : "tv.title")}</h1>
        <span className="muted">
          {/* BUGS.md #64 — total på tværs af alle sider, ikke kun de viste. */}
          {status === "ready" ? t("tv.count", { count: total }) : " "}
        </span>
      </div>

      <div className="library-toolbar">
        {/* Feature #126 — samme to store handlingsknapper som Film-siden og
            ønskelisten (Jans ønske 2026-08-12). Gæster ser dem kun på
            ønskelisten (feature #116). */}
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

        {/* Feature #214 — under "Søg titel"-tilføjelsen skjules rækken helt,
            uanset wishlist eller ej (samme rettelse som Library.jsx). */}
        {addMode !== "manual" && (
          <div className={`search-row${wishlist ? " search-row-secondary" : ""}`}>
            {searchInputWrap(t(wishlist ? "lib.wishlistFilterPlaceholder" : "tv.searchPlaceholder"))}
            {sortFilterFieldButtons}
          </div>
        )}

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
                // Se Library.jsx' identiske gren — søgningen rammer begge
                // TMDb-databaser, så en valgt film havner i movies og er
                // usynlig her (BUGS.md #47).
                setSavedMovie(kind === "movie");
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

        {openPanel === "filter" && (
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
            {/* Feature #111 — se den identiske note i Library.jsx. */}
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
            {/* Feature #157 — se den identiske note i Library.jsx. */}
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
            {/* Feature #86 — se Library.jsx: altid synlig, deaktiveret når
                der ikke er noget at rydde. */}
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

      {status === "loading" && (
        <div className="skeleton-grid">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="skeleton-card" />
          ))}
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

      {savedMovie && (
        <div className="banner banner-info" style={{ marginBottom: 16 }}>
          <span style={{ flex: 1 }}>
            {t("tv.savedMovieNotice", {
              target: t(wishlist ? "tv.movieWishes" : "lib.title"),
              here: t(wishlist ? "tv.tvWishes" : "tv.tvShows"),
            })}
          </span>
          {onGoToMovies && (
            <button
              type="button"
              className="btn"
              onClick={() => {
                setSavedMovie(false);
                onGoToMovies();
              }}
            >
              {t("lib.showTarget", {
                target: t(wishlist ? "tv.movieWishes" : "tv.movieLibraryLower"),
              })}
            </button>
          )}
          <button type="button" className="btn" onClick={() => setSavedMovie(false)}>
            ✕
          </button>
        </div>
      )}

      {status === "error" && (
        <div className="banner banner-error">{listError || t("tv.loadError")}</div>
      )}

      {status === "ready" && shows.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">📺</div>
          <p>
            {t(
              hasActiveFilters || query
                ? "tv.emptyFiltered"
                : wishlist
                  ? "tv.emptyWishlist"
                  : "tv.empty"
            )}
          </p>
        </div>
      )}

      {status === "ready" && shows.length > 0 && (
        <ul
          className={`movie-grid movie-grid--${user.settings.card_size ?? "medium"}${
            viewMode === "list" ? " movie-grid--list" : ""
          }`}
        >
          {shows.map((show) => (
            <li key={show.id} className="movie-card" onClick={() => setActiveShow(show)}>
              {/* Feature #92 — se den identiske note i Library.jsx. */}
              {show.serial_number != null && (
                <div className="movie-serial">
                  {formatSerial(show.serial_number, serialPaddingWidth, serialPrefix(show.media_type, "tv"))}
                </div>
              )}
              {show.format && <div className="movie-format-badge">{show.format}</div>}
              <div className="movie-poster">
                {show.poster_url ? (
                  // Feature #143 — poster-størrelse efter kortet, ikke altid w500.
                  <img
                    src={posterSrc(show.poster_url, cardPosterSize(user.settings.card_size ?? "medium"))}
                    alt={show.name}
                    loading="lazy"
                  />
                ) : (
                  "📺"
                )}
                {visibleFields.rating && show.rating != null && (
                  <div className="movie-rating-badge">★ {show.rating.toFixed(1)}</div>
                )}
                <div className="movie-badge-stack">
                  {/* Feature #144/#145 — se de identiske badges i Library.jsx. */}
                  {wishlist && show.wishlist_status === "pending" && (
                    <div className="movie-wishlist-badge" title={t("lib.wishlistPending")}>
                      {t("lib.wishlistPendingShort")}
                    </div>
                  )}
                  {wishlist && show.name_in_library && (
                    <div className="movie-namematch-badge" title={t("lib.nameInLibrary")}>
                      {t("lib.nameInLibraryShort")}
                    </div>
                  )}
                  {visibleFields.plex && <PlexCardBadge availability={plex.items[show.id]} />}
                  {show.number_of_seasons > 0 && (
                    <div className="movie-seasons-badge" title={t("tv.seasonsBadgeTitle")}>
                      {t("tv.seasonsBadge", {
                        owned: show.seasons.filter((s) => s.owned).length,
                        total: show.number_of_seasons,
                      })}
                    </div>
                  )}
                  {show.watched && (
                    <div className="movie-watched-badge" title={t("lib.watched")}>
                      {t("detail.watchedShort")}
                    </div>
                  )}
                </div>
              </div>
              <div className="movie-info">
                <div className="movie-title">{show.name}</div>
                <div className="movie-meta-grid">
                  {visibleFields.year && show.year && (
                    <span className="movie-meta-item">
                      {show.year}
                      {show.end_year && show.end_year !== show.year ? `–${show.end_year}` : ""}
                    </span>
                  )}
                  {visibleFields.format && show.format && (
                    <span className="movie-meta-item">{show.format}</span>
                  )}
                  {visibleFields.audioTypes && show.audio_types.length > 0 && (
                    <span className="movie-meta-item">{show.audio_types.join(", ")}</span>
                  )}
                  {visibleFields.mediaType && show.media_type && (
                    <span className="movie-meta-item">{show.media_type}</span>
                  )}
                  {visibleFields.genres && show.genres.length > 0 && (
                    <span className="movie-meta-item">{show.genres.join(", ")}</span>
                  )}
                </div>
                {/* Feature #144/#165 — admin godkender eller afviser ønsket
                    direkte fra kortet. */}
                {wishlist && isAdmin && show.wishlist_status === "pending" && (
                  <div className="movie-wishlist-actions">
                    <button
                      type="button"
                      className="btn btn-primary movie-approve-btn"
                      onClick={(e) => approveWishlist(show, e)}
                    >
                      {t("lib.approveWishlist")}
                    </button>
                    <button
                      type="button"
                      className="btn movie-reject-btn"
                      onClick={(e) => rejectWishlist(show, e)}
                    >
                      {t("lib.rejectWishlist")}
                    </button>
                  </div>
                )}
                {/* Feature #114/#116 — se den identiske note i Library.jsx
                    (kun ønske-kort, skjult for gæster). */}
                {show.is_wishlist && !isGuest && (
                  <div className="movie-tags">
                    <span
                      className={`movie-order-badge${show.order_status ? "" : " movie-order-badge--none"}`}
                    >
                      {show.order_status || t("orderStatus.notOrdered")}
                    </span>
                  </div>
                )}
                {/* Feature #203 — se den identiske note i Library.jsx. */}
                {show.is_wishlist && isGuest && show.order_status && (
                  <div className="movie-tags">
                    <span className="movie-order-badge">{t("orderStatus.ordered")}</span>
                  </div>
                )}
                {visibleFields.tags && show.tags.length > 0 && (
                  <div className="movie-tags">
                    {show.tags.map((tag) => (
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

      {activeShow && (
        <TvShowDetailModal
          show={activeShow}
          user={user}
          allTags={allTags}
          allOwners={allOwners}
          allLocations={allLocations}
          attributeOptions={attributeOptions}
          serialPaddingWidth={serialPaddingWidth}
          plex={plex}
          plexAvailability={plex.items[activeShow.id]}
          onClose={() => setActiveShow(null)}
          onChanged={() => {
            refresh();
            api.listTags().then(setAllTags).catch(() => {});
            api.listOwners().then(setAllOwners).catch(() => {});
            api.listLocations().then(setAllLocations).catch(() => {});
          }}
        />
      )}
    </section>
  );
}

export function TvShowDetailModal({
  show,
  user,
  allTags,
  allOwners,
  allLocations,
  attributeOptions,
  serialPaddingWidth,
  // Feature #88 — valgfri, se den identiske note i Library.MovieDetailModal.
  plex,
  plexAvailability,
  // Feature #106 — se den identiske note i Library.MovieDetailModal.
  duplicates,
  onBackToCandidates,
  onClose,
  onChanged,
}) {
  const t = useT();
  const locale = useLocale();
  // Feature #125 — titel-besøg når en gemt serie åbnes (ikke kladde-tilstand).
  useEffect(() => {
    if (show.id) {
      api
        .recordVisit({
          page: "title",
          kind: "title",
          resource_kind: "tv",
          resource_id: show.id,
          title: show.name,
        })
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [show.id]);
  const [tagsInput, setTagsInput] = useState(show.tags.join(", "));
  const [format, setFormat] = useState(show.format ?? "");
  const [audioTypes, setAudioTypes] = useState(show.audio_types);
  const [mediaType, setMediaType] = useState(show.media_type ?? "");
  const [location, setLocation] = useState(show.location ?? "");
  const [owner, setOwner] = useState(show.owner ?? "");
  // Feature #123 — undertekster som liste (se SubtitlesPicker), som i Library.jsx.
  const [subtitles, setSubtitles] = useState(show.subtitles ?? []);
  // Feature #114 — se den identiske note i Library.MovieDetailModal.
  const [orderStatus, setOrderStatus] = useState(show.order_status ?? "");
  const [personalRating, setPersonalRating] = useState(
    show.personal_rating != null ? String(show.personal_rating) : ""
  );
  const [personalNote, setPersonalNote] = useState(show.personal_note ?? "");
  const [watched, setWatched] = useState(show.watched);
  const [watchedAt, setWatchedAt] = useState(show.watched_at ? show.watched_at.slice(0, 10) : "");
  const [seasons, setSeasons] = useState(show.seasons);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [moving, setMoving] = useState(false);
  const [error, setError] = useState(null);
  const isGuest = user.role === "guest";
  // Feature #101 — se den identiske note i Library.MovieDetailModal.
  const [editing, setEditing] = useState(!show.id);

  /** Feature #101 — kaster ændringer væk og går tilbage til læsevisningen.
   *  Holdes ens med useState-linjerne ovenfor; et nyt felt skal huskes
   *  begge steder. `seasons` nulstilles ikke: sæson-/episode-markeringer
   *  gemmes med det samme hver for sig og er ikke en del af formularen. */
  function cancelEditing() {
    setTagsInput(show.tags.join(", "));
    setFormat(show.format ?? "");
    setAudioTypes(show.audio_types);
    setMediaType(show.media_type ?? "");
    setLocation(show.location ?? "");
    setOwner(show.owner ?? "");
    setSubtitles(show.subtitles ?? []);
    setOrderStatus(show.order_status ?? "");
    setPersonalRating(show.personal_rating != null ? String(show.personal_rating) : "");
    setPersonalNote(show.personal_note ?? "");
    setWatched(show.watched);
    setWatchedAt(show.watched_at ? show.watched_at.slice(0, 10) : "");
    setError(null);
    setEditing(false);
  }

  function addTag(tag) {
    const current = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
    if (current.some((t) => t.toLowerCase() === tag.toLowerCase())) return;
    setTagsInput([...current, tag].join(", "));
  }

  const canEditSerial = user.role === "admin" || user.username === show.registered_by;

  // Feature #92 — se den identiske regel i Library.MovieDetailModal.
  const missingClassification = !show.is_wishlist && (!mediaType || !format);
  // Feature #196 — se den identiske note i Library.MovieDetailModal.
  const missingClassificationForMove = !mediaType || !format;

  function toggleWatched() {
    setWatched((prev) => {
      const next = !prev;
      if (next && !watchedAt) setWatchedAt(new Date().toISOString().slice(0, 10));
      return next;
    });
  }

  // Feature #196 — udtrukket fra save(), se den identiske note i
  // Library.MovieDetailModal.buildPayload(). TV-serier har intet
  // serienummer-felt i denne formular (kun film kan redigere det direkte),
  // så her er det en ren, synkron felt-opbygning.
  function buildPayload() {
    return {
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
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const payload = buildPayload();
      if (show.id) {
        await api.updateTvShow(show.id, payload);
      } else {
        // "Kladde"-tilstand (feature #79) — se MovieDetailModal.save()'s
        // tilsvarende gren. Sæson-valget skete allerede i et tidligere trin
        // (MovieLookupForm.jsx), medsendes her som owned_seasons.
        //
        // Feature #128 — samme blokerende dublet-bekræftelse som for film:
        // findes serien allerede, kræv OK/Annuller før en kopi mere oprettes.
        if (duplicates?.length > 0) {
          const where = duplicates
            .map((d) =>
              d.is_wishlist ? t("scan.duplicateOnWishlist") : t("scan.duplicateInLibrary")
            )
            .join(t("scan.duplicateJoin"));
          if (!window.confirm(t("scan.duplicateConfirm", { where }))) return;
        }
        const ownedSeasonNumbers = seasons.filter((s) => s.owned).map((s) => s.season_number);
        await api.createTvShow({
          ...payload,
          tmdb_id: show.tmdb_id,
          barcode: show.barcode,
          barcode_source: show.barcode_source,
          is_wishlist: show.is_wishlist,
          ...(ownedSeasonNumbers.length > 0 ? { owned_seasons: ownedSeasonNumbers } : {}),
        });
        // Feature #147 — se den identiske logik i Library.jsx: registrerer man
        // til biblioteket og titlen lå på ønskelisten, tilbyd at fjerne ønsket.
        if (!show.is_wishlist) {
          const wish = duplicates?.find((d) => d.is_wishlist);
          if (wish && window.confirm(t("scan.removeFromWishlistConfirm", { title: wish.title }))) {
            await api.deleteTvShow(wish.id);
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
    if (!window.confirm(`Slet "${show.name}" fra biblioteket?`)) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deleteTvShow(show.id);
      onChanged();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  }

  // Feature #196 — se den identiske note i Library.MovieDetailModal.moveToLibrary().
  async function moveToLibrary() {
    setMoving(true);
    setError(null);
    try {
      const payload = buildPayload();
      await api.updateTvShow(show.id, { ...payload, is_wishlist: false });
      onChanged();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setMoving(false);
    }
  }

  async function setSeasonOwned(seasonNumber, owned) {
    setError(null);
    try {
      const updated = await api.setSeasonOwned(show.id, seasonNumber, owned);
      setSeasons(updated.seasons);
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  async function setEpisodeWatched(seasonNumber, episodeNumber, ep_watched) {
    setError(null);
    try {
      const updated = await api.setEpisodeWatched(
        show.id,
        seasonNumber,
        episodeNumber,
        ep_watched,
        ep_watched ? new Date().toISOString().slice(0, 10) : null
      );
      setSeasons(updated.seasons);
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-poster">
            {show.poster_url ? <img src={show.poster_url} alt={show.name} /> : "📺"}
          </div>
          <div>
            <h2>{show.name}</h2>
            <p className="muted">
              {show.year ?? t("detail.yearUnknown")}
              {show.end_year && show.end_year !== show.year ? `–${show.end_year}` : ""}
              {show.status && <> · {show.status}</>}
              {show.serial_number != null && (
                <>
                  {" · "}
                  {t("detail.serialShort", {
                    serial: formatSerial(show.serial_number, serialPaddingWidth, serialPrefix(show.media_type, "tv")),
                  })}
                </>
              )}
              {!show.id && <> · {t("detail.notCreatedYet")}</>}
              {show.rating != null && <> · ★ {show.rating.toFixed(1)}</>}
              {show.personal_rating != null && (
                <> · {t("detail.yourRatingShort", { rating: show.personal_rating })}</>
              )}
              {show.watched && <> · {t("detail.watchedShort")}</>}
            </p>
            {(show.imdb_url || show.tmdb_id) && (
              <p className="external-links">
                {show.imdb_url && (
                  <a href={show.imdb_url} target="_blank" rel="noreferrer">
                    IMDb
                  </a>
                )}
                {show.tmdb_id && (
                  <a
                    href={`https://www.themoviedb.org/tv/${show.tmdb_id}`}
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
          {/* Feature #106 — se den identiske note i Library.MovieDetailModal.
              Kun relevant her når TV-mellemtrinnet ikke selv har vist et
              dublet-fund (dvs. kun sjældne kant-tilfælde), men banneret
              koster intet at have med for en sikkerheds skyld. */}
          {!show.id && duplicates?.length > 0 && (
            <div className="banner banner-error">
              {t("scan.duplicateIntro", {
                what: t("scan.duplicateShow"),
                where: duplicates
                  .map((d) =>
                    d.is_wishlist
                      ? t("scan.duplicateOnWishlist")
                      : `${t("scan.duplicateInLibrary")}${duplicateSerialSuffix(d, "tv", serialPaddingWidth)}`
                  )
                  .join(t("scan.duplicateJoin")),
              })}
            </div>
          )}
          {show.overview && <p>{show.overview}</p>}
          {show.creators.length > 0 && (
            <p className="muted">
              <strong>{t("tv.createdBy")}</strong> {show.creators.join(", ")}
            </p>
          )}
          {show.cast.length > 0 && (
            <p className="muted">
              <strong>{t("detail.cast")}</strong> {show.cast.join(", ")}
            </p>
          )}

          {/* Feature #88/2026-08-10 — se den identiske note i Library.jsx. */}
          {show.id && show.media_type !== "Fysisk" && (
            <div className="plex-actions-row">
              <PlexPlayLink availability={plexAvailability} plex={plex} />
              <PlexShieldPlayButton
                availability={plexAvailability}
                shieldConfigured={plex.shieldConfigured}
                kind="show"
                itemId={show.id}
                isAdmin={user.role === "admin"}
                playAllowed={plex.playAllowed}
              />
            </div>
          )}

          {!editing ? (
            <>
              {/* Feature #87 — samme gruppering som i film-vinduet: korte
                  felter to og to, kun de brede står alene. */}
              <div className="modal-field-row">
                {show.serial_number != null && (
                  <div>
                    <div className="modal-section-label">{t("field.serialNumber")}</div>
                    <p>
                      {formatSerial(show.serial_number, serialPaddingWidth, serialPrefix(show.media_type, "tv"))}
                    </p>
                  </div>
                )}
                <div>
                  <div className="modal-section-label">{t("tv.watchedStatusWhole")}</div>
                  <p>
                    {show.watched
                      ? show.watched_at
                        ? t("detail.watchedOn", {
                            date: new Date(show.watched_at).toLocaleDateString(locale),
                          })
                        : t("detail.watchedShort")
                      : t("lib.notWatched")}
                  </p>
                </div>
              </div>
              <div>
                <div className="modal-section-label">{t("field.tags")}</div>
                <p>{show.tags.length > 0 ? show.tags.join(", ") : t("detail.noTags")}</p>
              </div>
              {show.genres.length > 0 && (
                <div>
                  <div className="modal-section-label">{t("field.genres")}</div>
                  <p>{show.genres.join(", ")}</p>
                </div>
              )}
              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">{t("field.location")}</div>
                  <p>{show.location || "—"}</p>
                </div>
                <div>
                  <div className="modal-section-label">{t("field.owner")}</div>
                  <p>{show.owner || "—"}</p>
                </div>
              </div>
              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">{t("field.format")}</div>
                  <p>{show.format || t("detail.notSpecified")}</p>
                </div>
                <div>
                  <div className="modal-section-label">{t("field.mediaType")}</div>
                  <p>{show.media_type || t("detail.notSpecified")}</p>
                </div>
              </div>
              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">{t("field.personalRating")}</div>
                  <p>{show.personal_rating != null ? `${show.personal_rating}/10` : "—"}</p>
                </div>
                {show.registered_by && (
                  <div>
                    <div className="modal-section-label">{t("field.registeredBy")}</div>
                    <p>{show.registered_by}</p>
                  </div>
                )}
              </div>
              <div>
                <div className="modal-section-label">{t("field.audioType")}</div>
                <p>{show.audio_types.length > 0 ? show.audio_types.join(", ") : "—"}</p>
              </div>
              <div>
                <div className="modal-section-label">{t("field.subtitles")}</div>
                <p>{show.subtitles?.length ? show.subtitles.join(", ") : "—"}</p>
              </div>
              {/* Feature #116 — bestillingsstatus skjules helt for gæster. */}
              {show.is_wishlist && !isGuest && (
                <div>
                  <div className="modal-section-label">{t("field.orderStatus")}</div>
                  <p>{show.order_status || t("orderStatus.notOrdered")}</p>
                </div>
              )}
              {/* Feature #203 — se den identiske note i Library.jsx. */}
              {show.is_wishlist && isGuest && show.order_status && (
                <div>
                  <div className="modal-section-label">{t("field.orderStatus")}</div>
                  <p>{t("orderStatus.ordered")}</p>
                </div>
              )}
              <div>
                <div className="modal-section-label">{t("field.personalNote")}</div>
                <p>{show.personal_note || "—"}</p>
              </div>
            </>
          ) : (
            <>
              {!show.id && (
                <p className="muted">{t("tv.createHint")}</p>
              )}
              {/* Feature #87 — se den identiske gruppering i Library.jsx. */}
              <div className="modal-field-row">
                {show.serial_number != null && (
                  <div>
                    <div className="modal-section-label">{t("field.serialNumber")}</div>
                    <p className="muted" style={{ margin: 0 }}>
                      {canEditSerial
                        ? t("tv.serialEditHint")
                        : t("tv.serialLockedHint", {
                            who: show.registered_by ?? t("tv.serialLockedFallback"),
                          })}
                    </p>
                  </div>
                )}

                <div>
                  <div className="modal-section-label">{t("tv.watchedStatusWhole")}</div>
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
                {/* Feature #138 — gæster vælger ikke tags (obligatorisk
                    "Tilføjet af {navn}" fra backenden, #4); andre vælger fra en
                    dropdown + fri tekst i stedet for en chip-væg (#5). */}
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
                    placeholder={t("tv.ownerPlaceholder")}
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

                {show.registered_by && (
                  <div>
                    <div className="modal-section-label">{t("field.registeredBy")}</div>
                    <p className="muted" style={{ margin: 0 }}>
                      {show.registered_by}
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

              {show.is_wishlist && !isGuest && (
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
                  placeholder={t("tv.notePlaceholder")}
                  rows={3}
                  style={{ width: "100%", resize: "vertical" }}
                />
              </div>
            </>
          )}

          {seasons.length > 0 && (
            <div>
              <div className="modal-section-label">{t("field.seasons")}</div>
              <div className="season-list">
                {seasons.map((season) => (
                  <SeasonRow
                    key={season.season_number}
                    season={season}
                    // I "kladde"-tilstand (intet show.id endnu) er sæson-valget
                    // allerede låst fast fra det forudgående trin i
                    // MovieLookupForm.jsx — vises read-only her, ligesom for
                    // en guest, i stedet for at kalde et API der kræver et id.
                    //
                    // Feature #101 — sæsoner og episoder forbliver klikbare i
                    // læsevisningen, modsat resten af formularen. De gemmes
                    // hver for sig med det samme og hører ikke til Gem/Fortryd;
                    // at skulle trykke "Redigér" for at hakke et afsnit af
                    // ville lægge et ekstra klik på den hyppigste handling.
                    isGuest={isGuest || !show.id}
                    onToggleOwned={(owned) => setSeasonOwned(season.season_number, owned)}
                    onToggleEpisode={(episodeNumber, ep_watched) =>
                      setEpisodeWatched(season.season_number, episodeNumber, ep_watched)
                    }
                  />
                ))}
              </div>
            </div>
          )}

          {error && <div className="banner banner-error">{error}</div>}
          {(missingClassification || (show.is_wishlist && missingClassificationForMove)) && (
            <div className="banner banner-info">{t("detail.classificationRequired")}</div>
          )}
        </div>

        {!editing ? (
          <div className="modal-footer">
            {show.id && <ScreeningRequestButton mediaKind="tv" id={show.id} username={user.username} />}
            {/* Feature #101 — kun rollen afgør om der kan redigeres; alle
                andre ser den samme læsevisning. */}
            {!isGuest && (
              <button type="button" className="btn btn-primary" onClick={() => setEditing(true)}>
                {t("detail.edit")}
              </button>
            )}
          </div>
        ) : (
          <div className="modal-footer">
            {show.id && (
              <button type="button" className="btn" onClick={remove} disabled={deleting}>
                {t(deleting ? "detail.deleting" : "tv.deleteShow")}
              </button>
            )}
            {show.id && show.is_wishlist && (
              <button
                type="button"
                className="btn"
                onClick={moveToLibrary}
                disabled={moving || missingClassificationForMove}
              >
                {t(moving ? "detail.moving" : "detail.moveToLibrary")}
              </button>
            )}
            {show.id && <ScreeningRequestButton mediaKind="tv" id={show.id} username={user.username} />}
            {show.id && (
              <button type="button" className="btn" onClick={cancelEditing} disabled={saving}>
                {t("common.cancel")}
              </button>
            )}
            {/* Feature #106 — se den identiske note i Library.MovieDetailModal. */}
            {!show.id && onBackToCandidates && (
              <button type="button" className="btn" onClick={onBackToCandidates} disabled={saving}>
                {t("scan.backToCandidates")}
              </button>
            )}
            <button
              type="button"
              className="btn btn-primary"
              onClick={save}
              disabled={saving || missingClassification}
            >
              {saving
                ? t("common.saving")
                : t(show.id ? "detail.saveChanges" : "detail.create")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function SeasonRow({ season, isGuest, onToggleOwned, onToggleEpisode }) {
  const t = useT();
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleOwnedChange(event) {
    setBusy(true);
    try {
      await onToggleOwned(event.target.checked);
      if (event.target.checked) setExpanded(true);
    } finally {
      setBusy(false);
    }
  }

  const watchedCount = season.episodes.filter((e) => e.watched).length;

  return (
    <div className="season-row">
      <div className="season-row-header">
        <label className="watched-toggle">
          <input
            type="checkbox"
            checked={season.owned}
            onChange={handleOwnedChange}
            disabled={busy || isGuest}
          />
          {t("tv.seasonEpisodes", {
            name: season.name ?? t("tv.seasonFallback", { number: season.season_number }),
            count: season.episode_count,
          })}
        </label>
        {season.episodes.length > 0 && (
          <>
            <span className="muted">
              {t("tv.episodesWatched", {
                watched: watchedCount,
                total: season.episodes.length,
              })}
            </span>
            <button type="button" className="btn" onClick={() => setExpanded((v) => !v)}>
              {t(expanded ? "tv.hideEpisodes" : "tv.showEpisodes")}
            </button>
          </>
        )}
      </div>

      {expanded && season.episodes.length > 0 && (
        <ul className="episode-list">
          {season.episodes.map((episode) => (
            <li key={episode.episode_number} className="episode-row">
              <label className="watched-toggle">
                <input
                  type="checkbox"
                  checked={episode.watched}
                  disabled={isGuest}
                  onChange={(e) => onToggleEpisode(episode.episode_number, e.target.checked)}
                />
                {episode.episode_number}.{" "}
                {episode.name ?? t("tv.episodeFallback", { number: episode.episode_number })}
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
