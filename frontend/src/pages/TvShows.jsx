import { useEffect, useState } from "react";
import { api } from "../api/client";
import Chip from "../components/Chip";
import Combobox from "../components/Combobox";
import MovieLookupForm from "../components/MovieLookupForm";
import Pagination from "../components/Pagination";
import ScreeningRequestButton from "../components/ScreeningRequestButton";
import "../pages/Library.css";
import "./TvShows.css";

const SORT_OPTIONS = [
  { value: "serial_number", label: "Serienummer" },
  { value: "created_at", label: "Tilføjet" },
  { value: "name", label: "Navn" },
  { value: "year", label: "År" },
  { value: "rating", label: "Rating" },
  { value: "personal_rating", label: "Din rating" },
  { value: "watched_at", label: "Set-dato" },
  { value: "format", label: "Format" },
  { value: "audio_types", label: "Lyd-type" },
  { value: "media_type", label: "Medietype" },
  { value: "location", label: "Lokation" },
  { value: "owner", label: "Ejer" },
  { value: "registered_by", label: "Registreret af" },
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
  { key: "year", label: "År" },
  { key: "tags", label: "Tags" },
  { key: "format", label: "Format" },
  { key: "audioTypes", label: "Lyd-type" },
  { key: "mediaType", label: "Medietype" },
  { key: "rating", label: "Rating" },
];

const DEFAULT_VISIBLE_FIELDS = {
  year: true,
  tags: true,
  format: false,
  audioTypes: false,
  mediaType: false,
  rating: false,
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
  };
}

function toggleValue(list, value) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function formatSerial(serialNumber, paddingWidth) {
  return `#${String(serialNumber).padStart(paddingWidth, "0")}`;
}

/**
 * `onGoToMovies` (valgfri) — spejlbilledet af `Library`s `onGoToTvShows`:
 * genvej til film-visningen når add-panelets scan/søgning endte med en film,
 * som denne side aldrig kan vise (BUGS.md #47).
 */
export default function TvShows({ user, onSettingsChanged, wishlist = false, onGoToMovies }) {
  const isGuest = user.role === "guest";
  const [query, setQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState([]);
  const [selectedFormats, setSelectedFormats] = useState([]);
  const [selectedAudioTypes, setSelectedAudioTypes] = useState([]);
  const [selectedMediaTypes, setSelectedMediaTypes] = useState([]);
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
  const [showFieldPanel, setShowFieldPanel] = useState(false);
  const [showSortPanel, setShowSortPanel] = useState(false);
  const [showFilterPanel, setShowFilterPanel] = useState(false);
  const [showAddPanel, setShowAddPanel] = useState(false);
  const [serialPaddingWidth, setSerialPaddingWidth] = useState(0);
  const [settingsError, setSettingsError] = useState(null);
  const [savedMovie, setSavedMovie] = useState(false);

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

  function persistVisibleFields(nextVisible) {
    persistSettings({
      tv_visible_fields: {
        year: nextVisible.year,
        tags: nextVisible.tags,
        format: nextVisible.format,
        audio_types: nextVisible.audioTypes,
        media_type: nextVisible.mediaType,
        rating: nextVisible.rating,
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
    sortLevels,
    watchedFilter,
    page,
    pageSize,
  ]);

  function persistPageSize(nextPageSize) {
    persistSettings({ page_size: nextPageSize });
  }

  function refresh() {
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
    setWatchedFilter(null);
  }

  function resetVisibleFieldsToDefault() {
    setVisibleFields(DEFAULT_VISIBLE_FIELDS);
    persistVisibleFields(DEFAULT_VISIBLE_FIELDS);
  }

  return (
    <section>
      <div className="page-header">
        <h1>{wishlist ? "TV-ønsker" : "TV-serier"}</h1>
        <span className="muted">{status === "ready" ? `${shows.length} serier` : " "}</span>
      </div>

      <div className="library-toolbar">
        <div className="search-row">
          <div className="search-input-wrap">
            <input
              type="search"
              placeholder="Søg på navn, skuespiller, genre..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {!isGuest && (
            <button type="button" className="btn btn-primary" onClick={() => setShowAddPanel((v) => !v)}>
              {showAddPanel ? "Luk" : wishlist ? "+ Tilføj ønske" : "+ Tilføj serie"} ▾
            </button>
          )}

          <button
            type="button"
            className={`btn${sortIsDefault ? "" : " btn-modified"}`}
            title={sortIsDefault ? "Standard-sortering" : "Sorteringen er ændret fra standard"}
            onClick={() => setShowSortPanel((v) => !v)}
          >
            Sortér {sortIsDefault ? "" : "● "}▾
          </button>

          <button
            type="button"
            className={`btn${hasActiveFilters ? " btn-modified" : ""}`}
            title={hasActiveFilters ? `${activeFilterCount} aktive filtre` : "Ingen filtre valgt"}
            onClick={() => setShowFilterPanel((v) => !v)}
          >
            Filtrér {hasActiveFilters ? `(${activeFilterCount}) ` : ""}▾
          </button>

          <button
            type="button"
            className={`btn${changedFieldCount > 0 ? " btn-modified" : ""}`}
            title={
              changedFieldCount > 0
                ? "Viste felter er ændret fra standard"
                : "Standard-felter vises"
            }
            onClick={() => setShowFieldPanel((v) => !v)}
          >
            Vis felter {changedFieldCount > 0 ? "● " : ""}▾
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
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn"
                    title={level.direction === "asc" ? "Stigende" : "Faldende"}
                    onClick={() => toggleSortLevelDirection(index)}
                  >
                    {level.direction === "asc" ? "↑" : "↓"}
                  </button>
                  {sortLevels.length > 1 && (
                    <button
                      type="button"
                      className="btn"
                      title="Fjern niveau"
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
                    + Tilføj sorteringsniveau
                  </button>
                )}
                <button
                  type="button"
                  className="btn"
                  onClick={resetSortToDefault}
                  disabled={sortIsDefault}
                >
                  Nulstil sortering
                </button>
              </div>
            </div>

            <div className="filter-group sort-preset-row">
              <span className="filter-group-label">Gemte visninger</span>
              <select value="" onChange={(e) => e.target.value && applyPreset(e.target.value)}>
                <option value="">Vælg gemt visning...</option>
                {presets.map((preset) => (
                  <option key={preset.name} value={preset.name}>
                    {preset.name}
                  </option>
                ))}
              </select>
              <input
                placeholder="Navngiv visning..."
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
                Gem nuværende visning
              </button>
            </div>
            <p className="muted" style={{ margin: 0 }}>
              En gemt visning husker søgetekst, alle filtre og sortering — ikke kun rækkefølgen.
            </p>

            {presets.length > 0 && (
              <div className="sort-preset-list">
                {presets.map((preset) => (
                  <span key={preset.name} className="sort-preset-item">
                    {preset.name}
                    <button
                      type="button"
                      className="sort-preset-remove"
                      title={`Slet preset "${preset.name}"`}
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
              <span className="filter-group-label">Vis på kort</span>
              <div className="chip-row">
                {VISIBLE_FIELD_OPTIONS.map((opt) => (
                  <Chip
                    key={opt.key}
                    label={opt.label}
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
                Nulstil viste felter
              </button>
            </div>
          </div>
        )}

        {showFilterPanel && (
          <div className="filter-panel">
            {allTags.length > 0 && (
              <div className="filter-group">
                <span className="filter-group-label">Tags</span>
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
                <span className="filter-group-label">Format</span>
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
                <span className="filter-group-label">Lyd</span>
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
                <span className="filter-group-label">Medietype</span>
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
              <span className="filter-group-label">Set-status</span>
              <div className="chip-row">
                <Chip
                  label="Set"
                  active={watchedFilter === true}
                  onClick={() => setWatchedFilter((prev) => (prev === true ? null : true))}
                />
                <Chip
                  label="Ikke set"
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
                Ryd filtre
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
          Dine visningsindstillinger blev ikke gemt: {settingsError}
        </div>
      )}

      {savedMovie && (
        <div className="banner banner-info" style={{ marginBottom: 16 }}>
          <span style={{ flex: 1 }}>
            Det du gemte er en film — den ligger derfor under{" "}
            <strong>{wishlist ? "film-ønsker" : "Filmbibliotek"}</strong>, ikke her blandt{" "}
            {wishlist ? "TV-ønskerne" : "TV-serierne"}.
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
              Vis {wishlist ? "film-ønsker" : "filmbiblioteket"}
            </button>
          )}
          <button type="button" className="btn" onClick={() => setSavedMovie(false)}>
            ✕
          </button>
        </div>
      )}

      {status === "error" && (
        <div className="banner banner-error">Kunne ikke hente TV-serier.</div>
      )}

      {status === "ready" && shows.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">📺</div>
          <p>
            {hasActiveFilters || query
              ? "Ingen serier matcher dine filtre."
              : wishlist
                ? "Ingen TV-ønsker endnu."
                : "Ingen TV-serier endnu — scan et cover eller søg for at komme i gang."}
          </p>
        </div>
      )}

      {status === "ready" && shows.length > 0 && (
        <ul className={`movie-grid movie-grid--${user.settings.card_size ?? "medium"}`}>
          {shows.map((show) => (
            <li key={show.id} className="movie-card" onClick={() => setActiveShow(show)}>
              {!show.is_wishlist && (
                <div className="movie-serial">{formatSerial(show.serial_number, serialPaddingWidth)}</div>
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
                {show.watched && (
                  <div className="movie-watched-badge" title="Set">
                    ✓ Set
                  </div>
                )}
                {show.number_of_seasons > 0 && (
                  <div className="movie-seasons-badge" title="Ejede sæsoner ud af serien totalt">
                    {show.seasons.filter((s) => s.owned).length}/{show.number_of_seasons} sæsoner
                  </div>
                )}
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
  onClose,
  onChanged,
}) {
  const [tagsInput, setTagsInput] = useState(show.tags.join(", "));
  const [format, setFormat] = useState(show.format ?? "");
  const [audioTypes, setAudioTypes] = useState(show.audio_types);
  const [mediaType, setMediaType] = useState(show.media_type ?? "");
  const [location, setLocation] = useState(show.location ?? "");
  const [owner, setOwner] = useState(show.owner ?? "");
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

  function addTag(tag) {
    const current = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
    if (current.some((t) => t.toLowerCase() === tag.toLowerCase())) return;
    setTagsInput([...current, tag].join(", "));
  }

  const canEditSerial = user.role === "admin" || user.username === show.registered_by;

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
              {show.year ?? "År ukendt"}
              {show.end_year && show.end_year !== show.year ? `–${show.end_year}` : ""}
              {show.status && <> · {show.status}</>}
              {!show.is_wishlist && show.id && (
                <> · Serienr. {formatSerial(show.serial_number, serialPaddingWidth)}</>
              )}
              {!show.id && <> · Ikke oprettet endnu</>}
              {show.rating != null && <> · ★ {show.rating.toFixed(1)}</>}
              {show.personal_rating != null && <> · Din: {show.personal_rating}/10</>}
              {show.watched && <> · ✓ Set</>}
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
          {show.overview && <p>{show.overview}</p>}
          {show.creators.length > 0 && (
            <p className="muted">
              <strong>Skabt af:</strong> {show.creators.join(", ")}
            </p>
          )}
          {show.cast.length > 0 && (
            <p className="muted">
              <strong>Medvirkende:</strong> {show.cast.join(", ")}
            </p>
          )}

          {isGuest ? (
            <>
              {/* Feature #87 — samme gruppering som i film-vinduet: korte
                  felter to og to, kun de brede står alene. */}
              <div className="modal-field-row">
                {!show.is_wishlist && (
                  <div>
                    <div className="modal-section-label">Serienummer</div>
                    <p>{formatSerial(show.serial_number, serialPaddingWidth)}</p>
                  </div>
                )}
                <div>
                  <div className="modal-section-label">Set-status (hele serien)</div>
                  <p>
                    {show.watched
                      ? `✓ Set${show.watched_at ? ` d. ${new Date(show.watched_at).toLocaleDateString("da-DK")}` : ""}`
                      : "Ikke set"}
                  </p>
                </div>
              </div>
              <div>
                <div className="modal-section-label">Tags</div>
                <p>{show.tags.length > 0 ? show.tags.join(", ") : "Ingen tags"}</p>
              </div>
              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">Lokation</div>
                  <p>{show.location || "—"}</p>
                </div>
                <div>
                  <div className="modal-section-label">Ejer</div>
                  <p>{show.owner || "—"}</p>
                </div>
              </div>
              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">Format</div>
                  <p>{show.format || "Ikke angivet"}</p>
                </div>
                <div>
                  <div className="modal-section-label">Medietype</div>
                  <p>{show.media_type || "Ikke angivet"}</p>
                </div>
              </div>
              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">Din rating</div>
                  <p>{show.personal_rating != null ? `${show.personal_rating}/10` : "—"}</p>
                </div>
                {show.registered_by && (
                  <div>
                    <div className="modal-section-label">Registreret af</div>
                    <p>{show.registered_by}</p>
                  </div>
                )}
              </div>
              <div>
                <div className="modal-section-label">Lyd-type</div>
                <p>{show.audio_types.length > 0 ? show.audio_types.join(", ") : "—"}</p>
              </div>
              <div>
                <div className="modal-section-label">Din note</div>
                <p>{show.personal_note || "—"}</p>
              </div>
            </>
          ) : (
            <>
              {!show.id && (
                <p className="muted">
                  Ikke oprettet endnu — tryk "Opret" nedenfor for at gemme i biblioteket.
                  Serienummer tildeles automatisk ved oprettelse.
                </p>
              )}
              {/* Feature #87 — se den identiske gruppering i Library.jsx. */}
              <div className="modal-field-row">
                {!show.is_wishlist && show.id && (
                  <div>
                    <div className="modal-section-label">Serienummer</div>
                    <p className="muted" style={{ margin: 0 }}>
                      {canEditSerial
                        ? "Redigér serienummeret via API'et om nødvendigt."
                        : `Kun en admin eller ${show.registered_by ?? "den der registrerede serien"} kan ændre serienummeret.`}
                    </p>
                  </div>
                )}

                <div>
                  <div className="modal-section-label">Set-status (hele serien)</div>
                  <label className="watched-toggle">
                    <input type="checkbox" checked={watched} onChange={toggleWatched} />
                    Set
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
                <div className="modal-section-label">Tags</div>
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
                  <div className="modal-section-label">Lokation</div>
                  <Combobox
                    value={location}
                    onChange={setLocation}
                    options={allLocations}
                    placeholder="Stue, reol 2..."
                  />
                </div>

                <div>
                  <div className="modal-section-label">Ejer</div>
                  <Combobox value={owner} onChange={setOwner} options={allOwners} placeholder="Hvem ejer den..." />
                </div>
              </div>

              <div className="modal-field-row">
                <div>
                  <div className="modal-section-label">Format</div>
                  <select value={format} onChange={(e) => setFormat(e.target.value)}>
                    <option value="">Ikke angivet</option>
                    {attributeOptions.formats.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <div className="modal-section-label">Medietype</div>
                  <select value={mediaType} onChange={(e) => setMediaType(e.target.value)}>
                    <option value="">Ikke angivet</option>
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
                  <div className="modal-section-label">Din rating (1-10)</div>
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
                    <div className="modal-section-label">Registreret af</div>
                    <p className="muted" style={{ margin: 0 }}>
                      {show.registered_by}
                    </p>
                  </div>
                )}
              </div>

              <div>
                <div className="modal-section-label">Lyd-type</div>
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
                <div className="modal-section-label">Din note</div>
                <textarea
                  value={personalNote}
                  onChange={(e) => setPersonalNote(e.target.value)}
                  placeholder="Egne tanker om serien..."
                  rows={3}
                  style={{ width: "100%", resize: "vertical" }}
                />
              </div>
            </>
          )}

          {seasons.length > 0 && (
            <div>
              <div className="modal-section-label">Sæsoner</div>
              <div className="season-list">
                {seasons.map((season) => (
                  <SeasonRow
                    key={season.season_number}
                    season={season}
                    // I "kladde"-tilstand (intet show.id endnu) er sæson-valget
                    // allerede låst fast fra det forudgående trin i
                    // MovieLookupForm.jsx — vises read-only her, ligesom for
                    // en guest, i stedet for at kalde et API der kræver et id.
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
        </div>

        {isGuest ? (
          <div className="modal-footer">
            {show.id && <ScreeningRequestButton mediaKind="tv" id={show.id} username={user.username} />}
          </div>
        ) : (
          <div className="modal-footer">
            {show.id && (
              <button type="button" className="btn" onClick={remove} disabled={deleting}>
                {deleting ? "Sletter..." : "Slet serie"}
              </button>
            )}
            {show.id && show.is_wishlist && (
              <button type="button" className="btn" onClick={moveToLibrary} disabled={moving}>
                {moving ? "Flytter..." : "Flyt til bibliotek"}
              </button>
            )}
            {show.id && <ScreeningRequestButton mediaKind="tv" id={show.id} username={user.username} />}
            <button type="button" className="btn btn-primary" onClick={save} disabled={saving}>
              {saving ? "Gemmer..." : show.id ? "Gem ændringer" : "Opret"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function SeasonRow({ season, isGuest, onToggleOwned, onToggleEpisode }) {
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
          {season.name ?? `Sæson ${season.season_number}`} ({season.episode_count} episoder)
        </label>
        {season.episodes.length > 0 && (
          <>
            <span className="muted">
              {watchedCount}/{season.episodes.length} set
            </span>
            <button type="button" className="btn" onClick={() => setExpanded((v) => !v)}>
              {expanded ? "Skjul episoder" : "Vis episoder"}
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
                {episode.episode_number}. {episode.name ?? `Episode ${episode.episode_number}`}
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
