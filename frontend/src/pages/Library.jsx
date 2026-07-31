import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function Library() {
  const [query, setQuery] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [movies, setMovies] = useState([]);
  const [status, setStatus] = useState("idle");

  useEffect(() => {
    const tags = tagFilter
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    setStatus("loading");
    api
      .listMovies({ q: query || undefined, tags })
      .then((data) => {
        setMovies(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, [query, tagFilter]);

  return (
    <section>
      <h1>Filmbibliotek</h1>
      <div className="filters">
        <input
          type="search"
          placeholder="Søg på titel, skuespiller, genre..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <input
          type="text"
          placeholder="Filtrér på tags (kommasepareret)"
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
        />
      </div>

      {status === "loading" && <p>Indlæser...</p>}
      {status === "error" && (
        <p role="alert">
          Kunne ikke hente film. Kør backend'en (se README/CLAUDE.md), og sørg for at
          `/api/movies` er implementeret.
        </p>
      )}
      {status === "ready" && movies.length === 0 && <p>Ingen film fundet.</p>}

      <ul className="movie-grid">
        {movies.map((movie) => (
          <li key={movie.id}>
            {movie.poster_url && <img src={movie.poster_url} alt={movie.title} />}
            <strong>{movie.title}</strong>
            <div className="tags">
              {(movie.tags ?? []).map((tag) => (
                <span key={tag} className="tag">
                  {tag}
                </span>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
