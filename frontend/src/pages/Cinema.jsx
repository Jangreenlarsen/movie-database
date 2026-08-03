import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./Cinema.css";

function dateKey(iso) {
  return iso.slice(0, 10);
}

function formatDateHeading(iso) {
  const date = new Date(iso);
  const label = date.toLocaleDateString("da-DK", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString("da-DK", { hour: "2-digit", minute: "2-digit" });
}

function groupByDate(screenings) {
  const groups = [];
  let currentKey = null;
  for (const screening of screenings) {
    const key = dateKey(screening.scheduled_at);
    if (key !== currentKey) {
      groups.push({ key, date: screening.scheduled_at, screenings: [] });
      currentKey = key;
    }
    groups[groups.length - 1].screenings.push(screening);
  }
  return groups;
}

export default function Cinema({ user }) {
  const isAdmin = user.role === "admin";
  const [screenings, setScreenings] = useState([]);
  const [status, setStatus] = useState("loading");

  function refresh() {
    return api
      .listScreenings(true)
      .then((data) => {
        setScreenings(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }

  useEffect(() => {
    refresh();
  }, []);

  const groups = groupByDate(screenings);

  return (
    <section>
      <div className="page-header">
        <h1>🎬 Voldby BIO</h1>
      </div>

      {isAdmin && <AdminScreeningTools onChanged={refresh} />}

      <div className="cinema-program">
        {status === "loading" && <p className="muted">Indlæser program...</p>}
        {status === "error" && <div className="banner banner-error">Kunne ikke hente programmet.</div>}
        {status === "ready" && groups.length === 0 && (
          <p className="muted">Ingen kommende visninger er planlagt endnu.</p>
        )}

        {groups.map((group) => (
          <div key={group.key} className="cinema-day">
            <h2 className="cinema-day-heading">{formatDateHeading(group.date)}</h2>
            <div className="cinema-cards">
              {group.screenings.map((screening) => (
                <ScreeningCard
                  key={screening.id}
                  screening={screening}
                  isAdmin={isAdmin}
                  onChanged={refresh}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ScreeningCard({ screening, isAdmin, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [scheduledAt, setScheduledAt] = useState(screening.scheduled_at.slice(0, 16));
  const [note, setNote] = useState(screening.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function saveEdit() {
    setBusy(true);
    setError(null);
    try {
      await api.updateScreening(screening.id, { scheduled_at: scheduledAt, note: note || null });
      setEditing(false);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeScreening() {
    if (!window.confirm(`Fjern "${screening.title}" fra programmet?`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteScreening(screening.id);
      onChanged();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="cinema-card">
      <div className="cinema-card-poster">
        {screening.poster_url ? (
          <img src={screening.poster_url} alt={screening.title ?? ""} loading="lazy" />
        ) : (
          <span>{screening.media_kind === "movie" ? "🎬" : "📺"}</span>
        )}
      </div>
      <div className="cinema-card-body">
        <div className="cinema-card-time">{formatTime(screening.scheduled_at)}</div>
        <h3 className="cinema-card-title">
          {screening.title ?? "Ukendt titel"}
          {screening.year ? ` (${screening.year})` : ""}
        </h3>
        {screening.genres?.length > 0 && (
          <div className="cinema-card-genres">{screening.genres.join(", ")}</div>
        )}
        {screening.overview && <p className="cinema-card-overview">{screening.overview}</p>}
        {screening.note && <p className="cinema-card-note">📝 {screening.note}</p>}
        <div className="cinema-card-links">
          {screening.trailer_url && (
            <a href={screening.trailer_url} target="_blank" rel="noreferrer">
              ▶ Se trailer
            </a>
          )}
          {screening.imdb_url && (
            <a href={screening.imdb_url} target="_blank" rel="noreferrer">
              IMDb
            </a>
          )}
        </div>

        {isAdmin && !editing && (
          <div className="cinema-card-admin-actions">
            <button type="button" className="btn" onClick={() => setEditing(true)}>
              Redigér
            </button>
            <button type="button" className="btn" onClick={removeScreening} disabled={busy}>
              Fjern
            </button>
          </div>
        )}

        {isAdmin && editing && (
          <div className="cinema-card-admin-actions cinema-card-edit-form">
            <input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
            />
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Note (valgfri)"
            />
            <button type="button" className="btn btn-primary" onClick={saveEdit} disabled={busy}>
              {busy ? "Gemmer..." : "Gem"}
            </button>
            <button type="button" className="btn" onClick={() => setEditing(false)} disabled={busy}>
              Annullér
            </button>
          </div>
        )}

        {error && <div className="banner banner-error" style={{ marginTop: 8 }}>{error}</div>}
      </div>
    </div>
  );
}

function AdminScreeningTools({ onChanged }) {
  const [requests, setRequests] = useState([]);
  const [status, setStatus] = useState("loading");

  function refreshRequests() {
    return api
      .listScreeningRequests("pending")
      .then((data) => {
        setRequests(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }

  useEffect(() => {
    refreshRequests();
  }, []);

  function handleChanged() {
    refreshRequests();
    onChanged();
  }

  return (
    <div className="card cinema-panel">
      <h2>Anmodninger</h2>
      <p className="muted">Titler brugerne har ønsket vist — planlæg en dato/tid, eller afvis dem.</p>

      {status === "loading" && <p className="muted">Indlæser...</p>}
      {status === "error" && <div className="banner banner-error">Kunne ikke hente anmodninger.</div>}
      {status === "ready" && requests.length === 0 && (
        <p className="muted">Ingen ventende anmodninger.</p>
      )}

      <div className="cinema-requests">
        {requests.map((request) => (
          <RequestRow key={request.id} request={request} onChanged={handleChanged} />
        ))}
      </div>

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <DirectAddSection onChanged={handleChanged} />
    </div>
  );
}

function RequestRow({ request, onChanged }) {
  const [scheduling, setScheduling] = useState(false);
  const [scheduledAt, setScheduledAt] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function schedule() {
    if (!scheduledAt) return;
    setBusy(true);
    setError(null);
    try {
      await api.createScreening({
        media_kind: request.media_kind,
        movie_id: request.movie_id,
        tv_show_id: request.tv_show_id,
        scheduled_at: scheduledAt,
        note: note || null,
        request_id: request.id,
      });
      onChanged();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  async function decline() {
    setBusy(true);
    setError(null);
    try {
      await api.declineScreeningRequest(request.id);
      onChanged();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="cinema-request-row">
      <div className="cinema-request-poster">
        {request.poster_url ? (
          <img src={request.poster_url} alt={request.title ?? ""} />
        ) : (
          <span>{request.media_kind === "movie" ? "🎬" : "📺"}</span>
        )}
      </div>
      <div className="cinema-request-info">
        <strong>
          {request.title ?? "Ukendt"} {request.year ? `(${request.year})` : ""}
        </strong>
        <div className="muted">
          Ønsket af: {request.requested_by.map((r) => r.username).join(", ")}
        </div>
      </div>

      {!scheduling ? (
        <div className="cinema-request-actions">
          <button type="button" className="btn btn-primary" onClick={() => setScheduling(true)}>
            Planlæg
          </button>
          <button type="button" className="btn" onClick={decline} disabled={busy}>
            Afvis
          </button>
        </div>
      ) : (
        <div className="cinema-request-actions cinema-card-edit-form">
          <input
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
          />
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (valgfri)" />
          <button type="button" className="btn btn-primary" onClick={schedule} disabled={!scheduledAt || busy}>
            {busy ? "Planlægger..." : "Bekræft"}
          </button>
          <button type="button" className="btn" onClick={() => setScheduling(false)} disabled={busy}>
            Annullér
          </button>
        </div>
      )}
      {error && <div className="banner banner-error" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  );
}

function DirectAddSection({ onChanged }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [scheduledAt, setScheduledAt] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function search(event) {
    event.preventDefault();
    if (!query.trim()) return;
    const [movies, shows] = await Promise.all([
      api.listMovies({ q: query.trim() }),
      api.listTvShows({ q: query.trim() }),
    ]);
    setResults([
      ...movies.map((m) => ({ media_kind: "movie", id: m.id, title: m.title, year: m.year, poster_url: m.poster_url })),
      ...shows.map((s) => ({ media_kind: "tv", id: s.id, title: s.name, year: s.year, poster_url: s.poster_url })),
    ]);
  }

  async function addDirectly() {
    if (!selected || !scheduledAt) return;
    setBusy(true);
    setError(null);
    try {
      await api.createScreening({
        media_kind: selected.media_kind,
        movie_id: selected.media_kind === "movie" ? selected.id : null,
        tv_show_id: selected.media_kind === "tv" ? selected.id : null,
        scheduled_at: scheduledAt,
        note: note || null,
      });
      setSelected(null);
      setResults([]);
      setQuery("");
      setScheduledAt("");
      setNote("");
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h3 style={{ marginTop: 0 }}>+ Tilføj visning direkte</h3>
      <p className="muted">
        Sæt en film/TV-serie fra biblioteket direkte på programmet, uden en forudgående anmodning.
      </p>
      <form className="cinema-search-form" onSubmit={search}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Søg i biblioteket..."
        />
        <button type="submit" className="btn">Søg</button>
      </form>

      {results.length > 0 && !selected && (
        <div className="cinema-search-results">
          {results.map((result) => (
            <button
              type="button"
              key={`${result.media_kind}-${result.id}`}
              className="cinema-search-result"
              onClick={() => setSelected(result)}
            >
              {result.poster_url ? <img src={result.poster_url} alt="" /> : <span>{result.media_kind === "movie" ? "🎬" : "📺"}</span>}
              <span>
                {result.title} {result.year ? `(${result.year})` : ""}
              </span>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="cinema-card-edit-form" style={{ marginTop: 10 }}>
          <strong>{selected.title}</strong>
          <input
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
          />
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (valgfri)" />
          <button
            type="button"
            className="btn btn-primary"
            onClick={addDirectly}
            disabled={!scheduledAt || busy}
          >
            {busy ? "Tilføjer..." : "Tilføj til programmet"}
          </button>
          <button type="button" className="btn" onClick={() => setSelected(null)} disabled={busy}>
            Annullér
          </button>
        </div>
      )}
      {error && <div className="banner banner-error" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  );
}
