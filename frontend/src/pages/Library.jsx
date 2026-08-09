import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import Chip from "../components/Chip";
import Combobox from "../components/Combobox";
import MovieLookupForm from "../components/MovieLookupForm";
import Pagination from "../components/Pagination";
import { PlexCardBadge, PlexPlayLink } from "../components/PlexAvailability";
import { usePlexAvailability } from "../components/usePlexAvailability";
import ScreeningRequestButton from "../components/ScreeningRequestButton";
import { useLocale, useT } from "../i18n";
import { formatSerial, serialPrefix } from "../utils/serialNumber";
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
  { value: "year", labelKey: "field.year" },
  { value: "rating", labelKey: "field.rating" },
  { value: "personal_rating", labelKey: "field.personalRating" },
  { value: "watched_at", labelKey: "field.watchedDate" },
  { value: "runtime", labelKey: "field.runtime" },
  { value: "format", labelKey: "field.format" },
  { value: "audio_types", labelKey: "field.audioType" },
  { value: "media_type", labelKey: "field.mediaType" },
  { value: "location", labelKey: "field.location" },
  { value: "owner", labelKey: "field.owner" },
  { value: "registered_by", labelKey: "field.registeredBy" },
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
  const [query, setQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState([]);
  const [selectedFormats, setSelectedFormats] = useState([]);
  const [selectedAudioTypes, setSelectedAudioTypes] = useState([]);
  const [selectedMediaTypes, setSelectedMediaTypes] = useState([]);
  const [watchedFilter, setWatchedFilter] = useState(null); // null | true | false
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
  });
  const [activeMovie, setActiveMovie] = useState(null);
  const [visibleFields, setVisibleFields] = useState(() => visibleFieldsFromSettings(user.settings));
  const [showFieldPanel, setShowFieldPanel] = useState(false);
  const [showSortPanel, setShowSortPanel] = useState(false);
  const [showFilterPanel, setShowFilterPanel] = useState(false);
  const [showAddPanel, setShowAddPanel] = useState(false);
  const [serialPaddingWidth, setSerialPaddingWidth] = useState(0);
  const [settingsError, setSettingsError] = useState(null);
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
    api
      .getSerialNumberConfig()
      .then((config) => setSerialPaddingWidth(config.padding_width))
      .catch(() => {});
  }, []);

  function fetchMovies() {
    return api.listMovies({
      q: query || undefined,
      tags: selectedTags,
      format: selectedFormats,
      audioTypes: selectedAudioTypes,
      mediaTypes: selectedMediaTypes,
      sort: sortLevels,
      wishlist,
      watched: watchedFilter,
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
    selectedTags,
    selectedFormats,
    selectedAudioTypes,
    selectedMediaTypes,
    sortLevels,
    watchedFilter,
    personFilter,
    pageSize,
  ]);

  useEffect(() => {
    setStatus("loading");
    fetchMovies()
      .then((data) => {
        setMovies(data.items);
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
    sortLevels,
    watchedFilter,
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
    // Presets saved before feature #44 only have `levels` — the ?? []/null
    // fallbacks make applying an old, sort-only preset a no-op for the rest
    // of the filter state instead of wiping out what the user had selected.
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

  // Feature #86 — ét tal pr. værktøj, så knappen på værktøjslinjen kan vise
  // om der overhovedet er valgt noget uden at man skal åbne panelet.
  // personFilter tælles med her; før stod den kun i `hasActiveFilters`, så et
  // rent person-filter fik knappen til at vise "Filtrér (0)".
  const activeFilterCount =
    selectedTags.length +
    selectedFormats.length +
    selectedAudioTypes.length +
    selectedMediaTypes.length +
    (watchedFilter != null ? 1 : 0) +
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
    setSelectedTags([]);
    setSelectedFormats([]);
    setSelectedAudioTypes([]);
    setSelectedMediaTypes([]);
    setWatchedFilter(null);
    setPersonFilter(null);
  }

  function resetVisibleFieldsToDefault() {
    setVisibleFields(DEFAULT_VISIBLE_FIELDS);
    persistVisibleFields(DEFAULT_VISIBLE_FIELDS);
  }

  return (
    <section>
      <div className="page-header">
        <h1>{t(wishlist ? "lib.wishlistTitle" : "lib.title")}</h1>
        <span className="muted">
          {status === "ready" ? t("lib.count", { count: movies.length }) : " "}
        </span>
      </div>

      <div className="library-toolbar">
        <div className="search-row">
          <div className="search-input-wrap">
            <SearchIcon />
            <input
              type="search"
              placeholder={t("lib.searchPlaceholder")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {!isGuest && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowAddPanel((v) => !v)}
            >
              {showAddPanel
                ? t("common.close")
                : t(wishlist ? "lib.addWish" : "lib.addMovie")}{" "}
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
        </div>

        {showAddPanel && (
          <div style={{ marginTop: 8 }}>
            <MovieLookupForm
              user={user}
              wishlist={wishlist}
              onSaved={(kind) => {
                refresh();
                setShowAddPanel(false);
                // Scan/søgning her rammer også TMDb's TV-database, og en
                // valgt TV-serie havner i tv_shows — en collection denne
                // side aldrig viser. Uden beskeden nedenfor så det ud som
                // om serien forsvandt (BUGS.md #47).
                setSavedTvShow(kind === "tv");
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

        {showFilterPanel &&
          (allTags.length > 0 ||
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
                      active={selectedTags.includes(tag)}
                      onClick={() => setSelectedTags((prev) => toggleValue(prev, tag))}
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
                      onClick={() =>
                        setSelectedAudioTypes((prev) => toggleValue(prev, audioType))
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
                      active={selectedMediaTypes.includes(mediaType)}
                      onClick={() =>
                        setSelectedMediaTypes((prev) => toggleValue(prev, mediaType))
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
                  onClick={() => setWatchedFilter((prev) => (prev === true ? null : true))}
                />
                <Chip
                  label={t("lib.notWatched")}
                  active={watchedFilter === false}
                  onClick={() => setWatchedFilter((prev) => (prev === false ? null : false))}
                />
              </div>
            </div>

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
        <div className="banner banner-error">{t("lib.loadError")}</div>
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
        <ul className={`movie-grid movie-grid--${user.settings.card_size ?? "medium"}`}>
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
                  <img src={movie.poster_url} alt={movie.title} loading="lazy" />
                ) : (
                  "🎬"
                )}
                {visibleFields.rating && movie.rating != null && (
                  <div className="movie-rating-badge">★ {movie.rating.toFixed(1)}</div>
                )}
                <div className="movie-badge-stack">
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
                </div>
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
  onClose,
  onChanged,
  onFilterByPerson,
}) {
  const t = useT();
  const locale = useLocale();
  const [tagsInput, setTagsInput] = useState(movie.tags.join(", "));
  const [format, setFormat] = useState(movie.format ?? "");
  const [audioTypes, setAudioTypes] = useState(movie.audio_types);
  const [mediaType, setMediaType] = useState(movie.media_type ?? "");
  const [serialNumberInput, setSerialNumberInput] = useState(
    movie.serial_number != null ? String(movie.serial_number) : ""
  );
  const [location, setLocation] = useState(movie.location ?? "");
  const [owner, setOwner] = useState(movie.owner ?? "");
  const [personalRating, setPersonalRating] = useState(
    movie.personal_rating != null ? String(movie.personal_rating) : ""
  );
  const [personalNote, setPersonalNote] = useState(movie.personal_note ?? "");
  const isGuest = user.role === "guest";

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
        personal_rating: personalRating ? Number(personalRating) : null,
        personal_note: personalNote.trim() || null,
        watched,
        watched_at: watched && watchedAt ? watchedAt : null,
      };
      if (movie.id) {
        const nextSerial = Number(serialNumberInput);
        if (canEditSerial && nextSerial > 0 && nextSerial !== movie.serial_number) {
          payload.serial_number = nextSerial;
        }
        await api.updateMovie(movie.id, payload);
      } else {
        // "Kladde"-tilstand (feature #79) — intet er oprettet endnu, dette
        // ER selve oprettelsen. movie er her et forhåndsvist TMDb-objekt
        // (se MovieLookupForm.jsx), ikke en gemt film.
        await api.createMovie({
          ...payload,
          tmdb_id: movie.tmdb_id,
          barcode: movie.barcode,
          barcode_source: movie.barcode_source,
          is_wishlist: movie.is_wishlist,
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
            {movie.genres.length > 0 && <p className="muted">{movie.genres.join(", ")}</p>}
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

          {movie.id && <PlexPlayLink availability={plexAvailability} plex={plex} />}

          {isGuest ? (
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

        {isGuest ? (
          // Feature #72's later refinement: guests may still request a
          // screening (their one allowed write action) even though the
          // rest of the footer (save/delete/move) stays hidden for them.
          <div className="modal-footer">
            {movie.id && <ScreeningRequestButton mediaKind="movie" id={movie.id} username={user.username} />}
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
    setAddingId(part.tmdb_id);
    try {
      await api.createMovie({ tmdb_id: part.tmdb_id });
      load();
      onChanged();
    } catch {
      // fejlen vises ikke separat her — brugeren kan se delen stadig mangler
      // og prøve igen; hovedfilmens egen gem-flow har sin egen fejlvisning.
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
                    {t(addingId === part.tmdb_id ? "collection.adding" : "collection.add")}
                  </button>
                )}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
