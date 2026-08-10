import { useEffect, useState } from "react";
import { api } from "../api/client";
import Chip from "../components/Chip";
import Combobox from "../components/Combobox";
import MovieLookupForm from "../components/MovieLookupForm";
import Pagination from "../components/Pagination";
import { PlexCardBadge, PlexPlayLink } from "../components/PlexAvailability";
import { usePlexAvailability } from "../components/usePlexAvailability";
import ScreeningRequestButton from "../components/ScreeningRequestButton";
import ViewModeToggle from "../components/ViewModeToggle";
import { useLocale, useT } from "../i18n";
import { formatSerial, serialPrefix } from "../utils/serialNumber";
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
  { value: "year", labelKey: "field.year" },
  { value: "rating", labelKey: "field.rating" },
  { value: "personal_rating", labelKey: "field.personalRating" },
  { value: "watched_at", labelKey: "field.watchedDate" },
  { value: "format", labelKey: "field.format" },
  { value: "audio_types", labelKey: "field.audioType" },
  { value: "media_type", labelKey: "field.mediaType" },
  { value: "location", labelKey: "field.location" },
  { value: "owner", labelKey: "field.owner" },
  { value: "registered_by", labelKey: "field.registeredBy" },
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
];

const DEFAULT_VISIBLE_FIELDS = {
  year: true,
  tags: true,
  format: false,
  audioTypes: false,
  mediaType: false,
  rating: false,
  plex: false,
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
  const [query, setQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState([]);
  const [selectedFormats, setSelectedFormats] = useState([]);
  const [selectedAudioTypes, setSelectedAudioTypes] = useState([]);
  const [selectedMediaTypes, setSelectedMediaTypes] = useState([]);
  // Feature #111 — se den identiske note i Library.jsx.
  const [selectedGenres, setSelectedGenres] = useState([]);
  const [allGenres, setAllGenres] = useState([]);
  const [watchedFilter, setWatchedFilter] = useState(null);
  const [sortLevels, setSortLevels] = useState(() => initialSortLevels(user.settings));
  const [presets, setPresets] = useState(user.settings.tv_sort_presets ?? []);
  const [presetNameInput, setPresetNameInput] = useState("");
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
  });
  const [activeShow, setActiveShow] = useState(null);
  const [visibleFields, setVisibleFields] = useState(() => visibleFieldsFromSettings(user.settings));
  // Feature #108 — se den identiske note i Library.jsx.
  const [viewMode, setViewMode] = useState(user.settings.view_mode ?? "grid");
  const [showFieldPanel, setShowFieldPanel] = useState(false);
  const [showSortPanel, setShowSortPanel] = useState(false);
  const [showFilterPanel, setShowFilterPanel] = useState(false);
  const [showAddPanel, setShowAddPanel] = useState(false);
  const [serialPaddingWidth, setSerialPaddingWidth] = useState(0);
  const [settingsError, setSettingsError] = useState(null);
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
      },
    });
  }

  function persistSortLevels(nextLevels) {
    persistSettings({ tv_sort_levels: nextLevels });
  }

  function persistSortPresets(nextPresets) {
    persistSettings({ tv_sort_presets: nextPresets });
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
      tags: selectedTags,
      format: selectedFormats,
      audioTypes: selectedAudioTypes,
      mediaTypes: selectedMediaTypes,
      genres: selectedGenres,
      sort: sortLevels,
      wishlist,
      watched: watchedFilter,
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
    selectedTags,
    selectedFormats,
    selectedAudioTypes,
    selectedMediaTypes,
    selectedGenres,
    sortLevels,
    watchedFilter,
    pageSize,
  ]);

  useEffect(() => {
    setStatus("loading");
    fetchShows()
      .then((data) => {
        setShows(data.items);
        setTotal(data.total);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    query,
    selectedTags,
    selectedFormats,
    selectedAudioTypes,
    selectedMediaTypes,
    selectedGenres,
    sortLevels,
    watchedFilter,
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
      })
      .catch(() => {});
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
    setQuery(preset.query ?? "");
    setSelectedTags(preset.tags ?? []);
    setSelectedFormats(preset.formats ?? []);
    setSelectedAudioTypes(preset.audio_types ?? []);
    setSelectedMediaTypes(preset.media_types ?? []);
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
        tags: selectedTags,
        formats: selectedFormats,
        audio_types: selectedAudioTypes,
        media_types: selectedMediaTypes,
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

  // Feature #86 — se Library.jsx' identiske blok.
  const activeFilterCount =
    selectedTags.length +
    selectedFormats.length +
    selectedAudioTypes.length +
    selectedMediaTypes.length +
    selectedGenres.length +
    (watchedFilter != null ? 1 : 0);
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
    setSelectedTags([]);
    setSelectedFormats([]);
    setSelectedAudioTypes([]);
    setSelectedMediaTypes([]);
    setSelectedGenres([]);
    setWatchedFilter(null);
  }

  function resetVisibleFieldsToDefault() {
    setVisibleFields(DEFAULT_VISIBLE_FIELDS);
    persistVisibleFields(DEFAULT_VISIBLE_FIELDS);
  }

  return (
    <section>
      <div className="page-header">
        <h1>{t(wishlist ? "tv.wishlistTitle" : "tv.title")}</h1>
        <span className="muted">
          {status === "ready" ? t("tv.count", { count: shows.length }) : " "}
        </span>
      </div>

      <div className="library-toolbar">
        <div className="search-row">
          <div className="search-input-wrap">
            <input
              type="search"
              placeholder={t("tv.searchPlaceholder")}
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

          {!isGuest && (
            <button type="button" className="btn btn-primary" onClick={() => setShowAddPanel((v) => !v)}>
              {showAddPanel
                ? t("common.close")
                : t(wishlist ? "lib.addWish" : "tv.addShow")}{" "}
              ▾
            </button>
          )}

          <button
            type="button"
            className={`btn${sortIsDefault ? "" : " btn-modified"}`}
            title={t(sortIsDefault ? "lib.sortDefaultTitle" : "lib.sortModifiedTitle")}
            onClick={() => setShowSortPanel((v) => !v)}
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
            onClick={() => setShowFilterPanel((v) => !v)}
          >
            {t("lib.filter")} {hasActiveFilters ? `(${activeFilterCount}) ` : ""}▾
          </button>

          <button
            type="button"
            className={`btn${changedFieldCount > 0 ? " btn-modified" : ""}`}
            title={t(
              changedFieldCount > 0 ? "lib.fieldsModifiedTitle" : "lib.fieldsDefaultTitle"
            )}
            onClick={() => setShowFieldPanel((v) => !v)}
          >
            {t("lib.fields")} {changedFieldCount > 0 ? "● " : ""}▾
          </button>

          <ViewModeToggle viewMode={viewMode} onChange={changeViewMode} />
        </div>

        {showAddPanel && (
          <div style={{ marginTop: 8 }}>
            <MovieLookupForm
              user={user}
              wishlist={wishlist}
              onSaved={(kind) => {
                refresh();
                setShowAddPanel(false);
                // Se Library.jsx' identiske gren — søgningen rammer begge
                // TMDb-databaser, så en valgt film havner i movies og er
                // usynlig her (BUGS.md #47).
                setSavedMovie(kind === "movie");
              }}
            />
          </div>
        )}

        {showSortPanel && (
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

        {showFieldPanel && (
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

        {showFilterPanel && (
          <div className="filter-panel">
            {allTags.length > 0 && (
              <div className="filter-group">
                <span className="filter-group-label">{t("field.tags")}</span>
                <div className="chip-row">
                  {allTags.map((tag) => (
                    <Chip
                      key={tag}
                      label={tag}
                      active={selectedTags.includes(tag)}
                      onClick={() => setSelectedTags((prev) => toggleValue(prev, tag))}
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
                      active={selectedGenres.includes(genre)}
                      onClick={() => setSelectedGenres((prev) => toggleValue(prev, genre))}
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
                      active={selectedFormats.includes(format)}
                      onClick={() => setSelectedFormats((prev) => toggleValue(prev, format))}
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
                      active={selectedAudioTypes.includes(audioType)}
                      onClick={() => setSelectedAudioTypes((prev) => toggleValue(prev, audioType))}
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
                      active={selectedMediaTypes.includes(mediaType)}
                      onClick={() => setSelectedMediaTypes((prev) => toggleValue(prev, mediaType))}
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
                  onClick={() => setWatchedFilter((prev) => (prev === true ? null : true))}
                />
                <Chip
                  label={t("lib.notWatched")}
                  active={watchedFilter === false}
                  onClick={() => setWatchedFilter((prev) => (prev === false ? null : false))}
                />
              </div>
            </div>
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
        <div className="banner banner-error">{t("tv.loadError")}</div>
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
                  <img src={show.poster_url} alt={show.name} loading="lazy" />
                ) : (
                  "📺"
                )}
                {visibleFields.rating && show.rating != null && (
                  <div className="movie-rating-badge">★ {show.rating.toFixed(1)}</div>
                )}
                <div className="movie-badge-stack">
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
                </div>
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
  const [tagsInput, setTagsInput] = useState(show.tags.join(", "));
  const [format, setFormat] = useState(show.format ?? "");
  const [audioTypes, setAudioTypes] = useState(show.audio_types);
  const [mediaType, setMediaType] = useState(show.media_type ?? "");
  const [location, setLocation] = useState(show.location ?? "");
  const [owner, setOwner] = useState(show.owner ?? "");
  // Feature #109 — se den identiske note i Library.jsx.
  const [subtitles, setSubtitles] = useState(show.subtitles ?? "");
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
    setSubtitles(show.subtitles ?? "");
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

  function toggleWatched() {
    setWatched((prev) => {
      const next = !prev;
      if (next && !watchedAt) setWatchedAt(new Date().toISOString().slice(0, 10));
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
        subtitles: subtitles.trim() || null,
        personal_rating: personalRating ? Number(personalRating) : null,
        personal_note: personalNote.trim() || null,
        watched,
        watched_at: watched && watchedAt ? watchedAt : null,
      };
      if (show.id) {
        await api.updateTvShow(show.id, payload);
      } else {
        // "Kladde"-tilstand (feature #79) — se MovieDetailModal.save()'s
        // tilsvarende gren. Sæson-valget skete allerede i et tidligere trin
        // (MovieLookupForm.jsx), medsendes her som owned_seasons.
        const ownedSeasonNumbers = seasons.filter((s) => s.owned).map((s) => s.season_number);
        await api.createTvShow({
          ...payload,
          tmdb_id: show.tmdb_id,
          barcode: show.barcode,
          barcode_source: show.barcode_source,
          is_wishlist: show.is_wishlist,
          ...(ownedSeasonNumbers.length > 0 ? { owned_seasons: ownedSeasonNumbers } : {}),
        });
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

  async function moveToLibrary() {
    setMoving(true);
    setError(null);
    try {
      await api.updateTvShow(show.id, { is_wishlist: false });
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
            {show.genres.length > 0 && <p className="muted">{show.genres.join(", ")}</p>}
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
                      : `${t("scan.duplicateInLibrary")}${d.serial_number ? ` (#${d.serial_number})` : ""}`
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
            <PlexPlayLink availability={plexAvailability} plex={plex} />
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
                <p>{show.subtitles || "—"}</p>
              </div>
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
                <input value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} />
                {allTags.length > 0 && (
                  <div className="chip-row" style={{ marginTop: 8 }}>
                    {allTags.map((tag) => (
                      <Chip key={tag} label={tag} onClick={() => addTag(tag)} />
                    ))}
                  </div>
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
                <input
                  value={subtitles}
                  onChange={(e) => setSubtitles(e.target.value)}
                  placeholder={t("detail.subtitlesPlaceholder")}
                />
              </div>

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
          {missingClassification && (
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
              <button type="button" className="btn" onClick={moveToLibrary} disabled={moving}>
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
