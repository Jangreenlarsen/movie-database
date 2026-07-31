import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import Chip from "../components/Chip";
import "./Library.css";

const SORT_OPTIONS = [
  { value: "serial_number", label: "Tilføjet" },
  { value: "title", label: "Titel" },
  { value: "year", label: "År" },
  { value: "rating", label: "Rating" },
];

const VISIBLE_FIELD_OPTIONS = [
  { key: "year", label: "År" },
  { key: "tags", label: "Tags" },
  { key: "format", label: "Format" },
  { key: "audioTypes", label: "Lyd-type" },
  { key: "rating", label: "Rating" },
];

function visibleFieldsFromSettings(settings) {
  const vf = settings?.visible_fields ?? {};
  return {
    year: vf.year ?? true,
    tags: vf.tags ?? true,
    format: vf.format ?? false,
    audioTypes: vf.audio_types ?? false,
    rating: vf.rating ?? false,
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

export default function Library({ user, onSettingsChanged }) {
  const [query, setQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState([]);
  const [selectedFormats, setSelectedFormats] = useState([]);
  const [selectedAudioTypes, setSelectedAudioTypes] = useState([]);
  const [sortField, setSortField] = useState(user.settings.sort_field ?? "serial_number");
  const [sortDirection, setSortDirection] = useState(user.settings.sort_direction ?? "desc");
  const [movies, setMovies] = useState([]);
  const [status, setStatus] = useState("loading");
  const [allTags, setAllTags] = useState([]);
  const [attributeOptions, setAttributeOptions] = useState({ formats: [], audio_types: [] });
  const [activeMovie, setActiveMovie] = useState(null);
  const [visibleFields, setVisibleFields] = useState(() => visibleFieldsFromSettings(user.settings));
  const [showFieldPanel, setShowFieldPanel] = useState(false);
  const [serialPaddingWidth, setSerialPaddingWidth] = useState(0);

  function persistSettings({ sortField: nextSort, sortDirection: nextDirection, visibleFields: nextVisible }) {
    api
      .updateMySettings({
        sort_field: nextSort,
        sort_direction: nextDirection,
        visible_fields: {
          year: nextVisible.year,
          tags: nextVisible.tags,
          format: nextVisible.format,
          audio_types: nextVisible.audioTypes,
          rating: nextVisible.rating,
        },
      })
      .then(onSettingsChanged)
      .catch(() => {});
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
      sort: sortField,
      direction: sortDirection,
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
  }, [query, selectedTags, selectedFormats, selectedAudioTypes, sortField, sortDirection]);

  function refresh() {
    fetchMovies().then(setMovies).catch(() => {});
  }

  function updateVisibleField(key, value) {
    setVisibleFields((prev) => {
      const next = { ...prev, [key]: value };
      persistSettings({ sortField, sortDirection, visibleFields: next });
      return next;
    });
  }

  function updateSortField(nextField) {
    setSortField(nextField);
    persistSettings({ sortField: nextField, sortDirection, visibleFields });
  }

  function toggleSortDirection() {
    const nextDirection = sortDirection === "asc" ? "desc" : "asc";
    setSortDirection(nextDirection);
    persistSettings({ sortField, sortDirection: nextDirection, visibleFields });
  }

  const hasActiveFilters =
    selectedTags.length > 0 || selectedFormats.length > 0 || selectedAudioTypes.length > 0;

  return (
    <section>
      <div className="page-header">
        <h1>Filmbibliotek</h1>
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

          <select value={sortField} onChange={(e) => updateSortField(e.target.value)}>
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                Sortér: {opt.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn"
            title={sortDirection === "asc" ? "Stigende" : "Faldende"}
            onClick={toggleSortDirection}
          >
            {sortDirection === "asc" ? "↑" : "↓"}
          </button>

          <button type="button" className="btn" onClick={() => setShowFieldPanel((v) => !v)}>
            Vis felter ▾
          </button>
        </div>

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

        {(allTags.length > 0 || attributeOptions.formats.length > 0) && (
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
            {hasActiveFilters && (
              <button
                type="button"
                className="btn"
                style={{ alignSelf: "flex-start" }}
                onClick={() => {
                  setSelectedTags([]);
                  setSelectedFormats([]);
                  setSelectedAudioTypes([]);
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
              : "Biblioteket er tomt endnu — scan et cover for at komme i gang."}
          </p>
        </div>
      )}

      {status === "ready" && movies.length > 0 && (
        <ul className="movie-grid">
          {movies.map((movie) => (
            <li key={movie.id} className="movie-card" onClick={() => setActiveMovie(movie)}>
              <div className="movie-serial">{formatSerial(movie.serial_number, serialPaddingWidth)}</div>
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
                {visibleFields.year && movie.year && (
                  <div className="movie-year">{movie.year}</div>
                )}
                {visibleFields.format && movie.format && (
                  <div className="movie-year">{movie.format}</div>
                )}
                {visibleFields.audioTypes && movie.audio_types.length > 0 && (
                  <div className="movie-year">{movie.audio_types.join(", ")}</div>
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

      {activeMovie && (
        <MovieDetailModal
          movie={activeMovie}
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

function MovieDetailModal({ movie, attributeOptions, serialPaddingWidth, onClose, onChanged }) {
  const [tagsInput, setTagsInput] = useState(movie.tags.join(", "));
  const [format, setFormat] = useState(movie.format ?? "");
  const [audioTypes, setAudioTypes] = useState(movie.audio_types);
  const [serialNumberInput, setSerialNumberInput] = useState(String(movie.serial_number));
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);

  const dirty = useMemo(() => {
    const tagsChanged =
      tagsInput.split(",").map((t) => t.trim()).filter(Boolean).join(",") !==
      movie.tags.join(",");
    const serialChanged =
      Number(serialNumberInput) > 0 && Number(serialNumberInput) !== movie.serial_number;
    return (
      tagsChanged ||
      format !== (movie.format ?? "") ||
      audioTypes.join(",") !== movie.audio_types.join(",") ||
      serialChanged
    );
  }, [tagsInput, format, audioTypes, serialNumberInput, movie]);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        tags: tagsInput.split(",").map((t) => t.trim()).filter(Boolean),
        format: format || null,
        audio_types: audioTypes,
      };
      const nextSerial = Number(serialNumberInput);
      if (nextSerial > 0 && nextSerial !== movie.serial_number) {
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
              {movie.year ?? "År ukendt"} · Serienr.{" "}
              {formatSerial(movie.serial_number, serialPaddingWidth)}
              {movie.rating != null && <> · ★ {movie.rating.toFixed(1)}</>}
            </p>
            {movie.genres.length > 0 && <p className="muted">{movie.genres.join(", ")}</p>}
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

          <div>
            <div className="modal-section-label">Serienummer</div>
            <input
              type="number"
              min="1"
              value={serialNumberInput}
              onChange={(e) => setSerialNumberInput(e.target.value)}
              style={{ width: 100 }}
            />
            <p className="muted" style={{ marginTop: 4 }}>
              Er nummeret allerede i brug af en anden film, bytter de to film
              automatisk plads.
            </p>
          </div>

          <div>
            <div className="modal-section-label">Tags</div>
            <input value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} />
          </div>

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
          <button type="button" className="btn btn-primary" onClick={save} disabled={!dirty || saving}>
            {saving ? "Gemmer..." : "Gem ændringer"}
          </button>
        </div>
      </div>
    </div>
  );
}
