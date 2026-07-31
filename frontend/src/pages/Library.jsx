import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import Chip from "../components/Chip";
import "./Library.css";

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

export default function Library() {
  const [query, setQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState([]);
  const [selectedFormats, setSelectedFormats] = useState([]);
  const [selectedAudioTypes, setSelectedAudioTypes] = useState([]);
  const [movies, setMovies] = useState([]);
  const [status, setStatus] = useState("loading");
  const [allTags, setAllTags] = useState([]);
  const [attributeOptions, setAttributeOptions] = useState({ formats: [], audio_types: [] });
  const [activeMovie, setActiveMovie] = useState(null);

  useEffect(() => {
    api.listTags().then(setAllTags).catch(() => {});
    api.attributeOptions().then(setAttributeOptions).catch(() => {});
  }, []);

  useEffect(() => {
    setStatus("loading");
    api
      .listMovies({
        q: query || undefined,
        tags: selectedTags,
        format: selectedFormats,
        audioTypes: selectedAudioTypes,
      })
      .then((data) => {
        setMovies(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, [query, selectedTags, selectedFormats, selectedAudioTypes]);

  const hasActiveFilters =
    selectedTags.length > 0 || selectedFormats.length > 0 || selectedAudioTypes.length > 0;

  function refresh() {
    api
      .listMovies({
        q: query || undefined,
        tags: selectedTags,
        format: selectedFormats,
        audioTypes: selectedAudioTypes,
      })
      .then(setMovies)
      .catch(() => {});
  }

  return (
    <section>
      <div className="page-header">
        <h1>Filmbibliotek</h1>
        <span className="muted">
          {status === "ready" ? `${movies.length} film` : " "}
        </span>
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
        </div>

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
              <div className="movie-serial">#{movie.serial_number}</div>
              {movie.format && <div className="movie-format-badge">{movie.format}</div>}
              <div className="movie-poster">
                {movie.poster_url ? (
                  <img src={movie.poster_url} alt={movie.title} loading="lazy" />
                ) : (
                  "🎬"
                )}
              </div>
              <div className="movie-info">
                <div className="movie-title">{movie.title}</div>
                {movie.year && <div className="movie-year">{movie.year}</div>}
                {movie.tags.length > 0 && (
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

function MovieDetailModal({ movie, attributeOptions, onClose, onChanged }) {
  const [tagsInput, setTagsInput] = useState(movie.tags.join(", "));
  const [format, setFormat] = useState(movie.format ?? "");
  const [audioTypes, setAudioTypes] = useState(movie.audio_types);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const dirty = useMemo(() => {
    const tagsChanged =
      tagsInput.split(",").map((t) => t.trim()).filter(Boolean).join(",") !==
      movie.tags.join(",");
    return tagsChanged || format !== (movie.format ?? "") || audioTypes.join(",") !== movie.audio_types.join(",");
  }, [tagsInput, format, audioTypes, movie]);

  async function save() {
    setSaving(true);
    try {
      await api.updateMovie(movie.id, {
        tags: tagsInput.split(",").map((t) => t.trim()).filter(Boolean),
        format: format || null,
        audio_types: audioTypes,
      });
      onChanged();
      onClose();
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
              {movie.year ?? "År ukendt"} · Serienr. #{movie.serial_number}
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
