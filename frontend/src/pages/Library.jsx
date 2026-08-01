import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import Chip from "../components/Chip";
import MovieLookupForm from "../components/MovieLookupForm";
import "./Library.css";

const SORT_OPTIONS = [
  { value: "serial_number", label: "Serienummer" },
  { value: "created_at", label: "Tilføjet" },
  { value: "title", label: "Titel" },
  { value: "year", label: "År" },
  { value: "rating", label: "Rating" },
  { value: "runtime", label: "Spilletid" },
  { value: "format", label: "Format" },
  { value: "audio_types", label: "Lyd-type" },
  { value: "media_type", label: "Medietype" },
  { value: "location", label: "Lokation" },
  { value: "owner", label: "Ejer" },
  { value: "registered_by", label: "Registreret af" },
];
const MAX_SORT_LEVELS = 3;

function initialSortLevels(settings) {
  if (settings?.sort_levels?.length) return settings.sort_levels;
  return [{ field: settings?.sort_field ?? "serial_number", direction: settings?.sort_direction ?? "desc" }];
}

const VISIBLE_FIELD_OPTIONS = [
  { key: "year", label: "År" },
  { key: "tags", label: "Tags" },
  { key: "format", label: "Format" },
  { key: "audioTypes", label: "Lyd-type" },
  { key: "mediaType", label: "Medietype" },
  { key: "rating", label: "Rating" },
  { key: "runtime", label: "Spilletid" },
];

function visibleFieldsFromSettings(settings) {
  const vf = settings?.visible_fields ?? {};
  return {
    year: vf.year ?? true,
    tags: vf.tags ?? true,
    format: vf.format ?? false,
    audioTypes: vf.audio_types ?? false,
    mediaType: vf.media_type ?? false,
    rating: vf.rating ?? false,
    runtime: vf.runtime ?? false,
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

function formatSerial(serialNumber, paddingWidth) {
  return `#${String(serialNumber).padStart(paddingWidth, "0")}`;
}

export default function Library({ user, onSettingsChanged, wishlist = false }) {
  const [query, setQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState([]);
  const [selectedFormats, setSelectedFormats] = useState([]);
  const [selectedAudioTypes, setSelectedAudioTypes] = useState([]);
  const [selectedMediaTypes, setSelectedMediaTypes] = useState([]);
  const [sortLevels, setSortLevels] = useState(() => initialSortLevels(user.settings));
  const [presets, setPresets] = useState(user.settings.sort_presets ?? []);
  const [presetNameInput, setPresetNameInput] = useState("");
  const [movies, setMovies] = useState([]);
  const [status, setStatus] = useState("loading");
  const [allTags, setAllTags] = useState([]);
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

  function persistVisibleFields(nextVisible) {
    api
      .updateMySettings({
        visible_fields: {
          year: nextVisible.year,
          tags: nextVisible.tags,
          format: nextVisible.format,
          audio_types: nextVisible.audioTypes,
          media_type: nextVisible.mediaType,
          rating: nextVisible.rating,
          runtime: nextVisible.runtime,
        },
      })
      .then(onSettingsChanged)
      .catch(() => {});
  }

  function persistSortLevels(nextLevels) {
    api.updateMySettings({ sort_levels: nextLevels }).then(onSettingsChanged).catch(() => {});
  }

  function persistSortPresets(nextPresets) {
    api.updateMySettings({ sort_presets: nextPresets }).then(onSettingsChanged).catch(() => {});
  }

  useEffect(() => {
    api.listTags().then(setAllTags).catch(() => {});
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
    });
  }

  useEffect(() => {
    setStatus("loading");
    fetchMovies()
      .then((data) => {
        setMovies(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, selectedTags, selectedFormats, selectedAudioTypes, selectedMediaTypes, sortLevels]);

  function refresh() {
    fetchMovies().then(setMovies).catch(() => {});
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
  }

  function saveCurrentAsPreset() {
    const name = presetNameInput.trim();
    if (!name) return;
    const next = [...presets.filter((p) => p.name !== name), { name, levels: sortLevels }];
    setPresets(next);
    persistSortPresets(next);
    setPresetNameInput("");
  }

  function deletePreset(name) {
    const next = presets.filter((p) => p.name !== name);
    setPresets(next);
    persistSortPresets(next);
  }

  const hasActiveFilters =
    selectedTags.length > 0 ||
    selectedFormats.length > 0 ||
    selectedAudioTypes.length > 0 ||
    selectedMediaTypes.length > 0;

  return (
    <section>
      <div className="page-header">
        <h1>{wishlist ? "Ønskeliste" : "Filmbibliotek"}</h1>
        <span className="muted">{status === "ready" ? `${movies.length} film` : " "}</span>
      </div>

      <div className="library-toolbar">
        <div className="search-row">
          <div className="search-input-wrap">
            <SearchIcon />
            <input
              type="search"
              placeholder="Søg på titel, skuespiller, genre..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {wishlist && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowAddPanel((v) => !v)}
            >
              {showAddPanel ? "Luk" : "+ Tilføj ønske"} ▾
            </button>
          )}

          <button type="button" className="btn" onClick={() => setShowSortPanel((v) => !v)}>
            Sortér ▾
          </button>

          <button type="button" className="btn" onClick={() => setShowFilterPanel((v) => !v)}>
            Filtrér {hasActiveFilters ? `(${selectedTags.length + selectedFormats.length + selectedAudioTypes.length + selectedMediaTypes.length}) ` : ""}▾
          </button>

          <button type="button" className="btn" onClick={() => setShowFieldPanel((v) => !v)}>
            Vis felter ▾
          </button>
        </div>

        {wishlist && showAddPanel && (
          <div style={{ marginTop: 8 }}>
            <MovieLookupForm
              user={user}
              wishlist
              onSaved={() => {
                refresh();
                setShowAddPanel(false);
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
              {sortLevels.length < MAX_SORT_LEVELS && (
                <button type="button" className="btn" onClick={addSortLevel}>
                  + Tilføj sorteringsniveau
                </button>
              )}
            </div>

            <div className="filter-group sort-preset-row">
              <span className="filter-group-label">Presets</span>
              <select value="" onChange={(e) => e.target.value && applyPreset(e.target.value)}>
                <option value="">Vælg gemt preset...</option>
                {presets.map((preset) => (
                  <option key={preset.name} value={preset.name}>
                    {preset.name}
                  </option>
                ))}
              </select>
              <input
                placeholder="Navngiv preset..."
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
                Gem som preset
              </button>
            </div>

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
          </div>
        )}

        {showFilterPanel &&
          (allTags.length > 0 ||
            attributeOptions.formats.length > 0 ||
            attributeOptions.media_types.length > 0) && (
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
                <span className="filter-group-label">Medietype</span>
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
            {hasActiveFilters && (
              <button
                type="button"
                className="btn"
                style={{ alignSelf: "flex-start" }}
                onClick={() => {
                  setSelectedTags([]);
                  setSelectedFormats([]);
                  setSelectedAudioTypes([]);
                  setSelectedMediaTypes([]);
                }}
              >
                Ryd filtre
              </button>
            )}
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

      {status === "error" && (
        <div className="banner banner-error">
          Kunne ikke hente film. Kør backend'en og sørg for at MongoDB kører.
        </div>
      )}

      {status === "ready" && movies.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">🎞️</div>
          <p>
            {hasActiveFilters || query
              ? "Ingen film matcher dine filtre."
              : wishlist
                ? "Ønskelisten er tom endnu."
                : "Biblioteket er tomt endnu — scan et cover for at komme i gang."}
          </p>
        </div>
      )}

      {status === "ready" && movies.length > 0 && (
        <ul className="movie-grid">
          {movies.map((movie) => (
            <li key={movie.id} className="movie-card" onClick={() => setActiveMovie(movie)}>
              {!movie.is_wishlist && (
                <div className="movie-serial">
                  {formatSerial(movie.serial_number, serialPaddingWidth)}
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
              </div>
              <div className="movie-info">
                <div className="movie-title">{movie.title}</div>
                <div className="movie-meta-grid">
                  {visibleFields.year && movie.year && (
                    <span className="movie-meta-item">{movie.year}</span>
                  )}
                  {visibleFields.runtime && movie.runtime && (
                    <span className="movie-meta-item">{movie.runtime} min</span>
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

      {activeMovie && (
        <MovieDetailModal
          movie={activeMovie}
          user={user}
          allTags={allTags}
          attributeOptions={attributeOptions}
          serialPaddingWidth={serialPaddingWidth}
          onClose={() => setActiveMovie(null)}
          onChanged={() => {
            refresh();
            api.listTags().then(setAllTags).catch(() => {});
          }}
        />
      )}
    </section>
  );
}

function MovieDetailModal({ movie, user, attributeOptions, serialPaddingWidth, onClose, onChanged }) {
  const [tagsInput, setTagsInput] = useState(movie.tags.join(", "));
  const [format, setFormat] = useState(movie.format ?? "");
  const [audioTypes, setAudioTypes] = useState(movie.audio_types);
  const [mediaType, setMediaType] = useState(movie.media_type ?? "");
  const [serialNumberInput, setSerialNumberInput] = useState(
    movie.serial_number != null ? String(movie.serial_number) : ""
  );
  const [location, setLocation] = useState(movie.location ?? "");
  const [owner, setOwner] = useState(movie.owner ?? "");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [moving, setMoving] = useState(false);
  const [error, setError] = useState(null);

  const canEditSerial = user.role === "admin" || user.username === movie.registered_by;

  const dirty = useMemo(() => {
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
    canEditSerial,
    movie,
  ]);

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
      };
      const nextSerial = Number(serialNumberInput);
      if (canEditSerial && nextSerial > 0 && nextSerial !== movie.serial_number) {
        payload.serial_number = nextSerial;
      }
      await api.updateMovie(movie.id, payload);
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
    try {
      await api.deleteMovie(movie.id);
      onChanged();
      onClose();
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
              {movie.year ?? "År ukendt"}
              {!movie.is_wishlist && (
                <> · Serienr. {formatSerial(movie.serial_number, serialPaddingWidth)}</>
              )}
              {movie.runtime != null && <> · {movie.runtime} min</>}
              {movie.rating != null && <> · ★ {movie.rating.toFixed(1)}</>}
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
          {movie.cast.length > 0 && (
            <p className="muted">
              <strong>Medvirkende:</strong> {movie.cast.join(", ")}
            </p>
          )}

          {!movie.is_wishlist && (
            <div>
              <div className="modal-section-label">Serienummer</div>
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
                  Er nummeret allerede i brug af en anden film, bytter de to film
                  automatisk plads.
                </p>
              ) : (
                <p className="muted" style={{ marginTop: 4 }}>
                  Kun en admin eller {movie.registered_by ?? "den der registrerede filmen"} kan ændre
                  serienummeret.
                </p>
              )}
            </div>
          )}

          <div>
            <div className="modal-section-label">Tags</div>
            <input value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} />
          </div>

          <div>
            <div className="modal-section-label">Lokation</div>
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Stue, reol 2..."
            />
          </div>

          <div>
            <div className="modal-section-label">Ejer</div>
            <input value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="Hvem ejer filmen..." />
          </div>

          {movie.registered_by && (
            <p className="muted">Registreret af: {movie.registered_by}</p>
          )}

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

          {error && <div className="banner banner-error">{error}</div>}
        </div>

        <div className="modal-footer">
          <button type="button" className="btn" onClick={remove} disabled={deleting}>
            {deleting ? "Sletter..." : "Slet film"}
          </button>
          {movie.is_wishlist && (
            <button type="button" className="btn" onClick={moveToLibrary} disabled={moving}>
              {moving ? "Flytter..." : "Flyt til bibliotek"}
            </button>
          )}
          <button type="button" className="btn btn-primary" onClick={save} disabled={!dirty || saving}>
            {saving ? "Gemmer..." : "Gem ændringer"}
          </button>
        </div>
      </div>
    </div>
  );
}
