import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./Settings.css";

export default function Settings({ user }) {
  const [movies, setMovies] = useState([]);
  const [status, setStatus] = useState("loading");
  const [edits, setEdits] = useState({});
  const [savingId, setSavingId] = useState(null);
  const [error, setError] = useState(null);

  function load() {
    setStatus("loading");
    api
      .listMovies({ sort: "serial_number", direction: "asc" })
      .then((data) => {
        setMovies(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }

  useEffect(load, []);

  function clearEdit(movieId) {
    setEdits((prev) => {
      const next = { ...prev };
      delete next[movieId];
      return next;
    });
  }

  async function saveSerial(movie) {
    const draft = edits[movie.id];
    const next = Number(draft);
    if (!Number.isInteger(next) || next <= 0 || next === movie.serial_number) {
      clearEdit(movie.id);
      return;
    }

    setSavingId(movie.id);
    setError(null);
    try {
      await api.updateMovie(movie.id, { serial_number: next });
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingId(null);
      clearEdit(movie.id);
    }
  }

  return (
    <section>
      <div className="page-header">
        <h1>Indstillinger</h1>
      </div>

      <div className="card settings-account">
        <div className="modal-section-label">Konto</div>
        <p>
          Logget ind som <strong>{user.username}</strong>
        </p>
      </div>

      <div className="card settings-section">
        <h2>Film-serienumre</h2>
        <p className="muted">
          Ret en films serienummer for at omorganisere biblioteket. Er nummeret allerede
          i brug af en anden film, bytter de to film automatisk plads.
        </p>

        {error && (
          <div className="banner banner-error" style={{ marginTop: 10 }}>
            {error}
          </div>
        )}

        {status === "loading" && <p className="muted">Indlæser...</p>}
        {status === "error" && (
          <div className="banner banner-error">Kunne ikke hente film.</div>
        )}

        {status === "ready" && (
          <ul className="serial-list">
            {movies.map((movie) => {
              const draft = edits[movie.id];
              const isDirty = draft !== undefined && Number(draft) !== movie.serial_number;
              return (
                <li key={movie.id} className="serial-row">
                  <input
                    type="number"
                    min="1"
                    className="serial-input"
                    value={draft ?? movie.serial_number}
                    onChange={(e) =>
                      setEdits((prev) => ({ ...prev, [movie.id]: e.target.value }))
                    }
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveSerial(movie);
                    }}
                  />
                  <span className="serial-title">
                    {movie.title} {movie.year ? `(${movie.year})` : ""}
                  </span>
                  <button
                    type="button"
                    className="btn"
                    disabled={!isDirty || savingId === movie.id}
                    onClick={() => saveSerial(movie)}
                  >
                    {savingId === movie.id ? "Gemmer..." : "Gem"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
