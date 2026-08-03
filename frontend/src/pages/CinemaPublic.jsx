import { useEffect, useState } from "react";
import { api } from "../api/client";
import CinemaShowcase from "../components/CinemaShowcase";
import { formatDateHeading, formatTime, groupByDate } from "../utils/cinemaFormat";
import "./Cinema.css";
import "./CinemaPublic.css";

// Feature #70 — public, no-login page at /bio. Read-only: no admin tools,
// no "ønsk visning"/anmeldelses-knapper, just the showcase section + the
// upcoming program. Deliberately a separate component from Cinema.jsx
// rather than a "publicOnly" prop on it — Cinema.jsx assumes a logged-in
// `user` throughout (role checks, screening-request actions), and keeping
// the public route as its own simple component avoids having to thread a
// "no user" case through all of that.
export default function CinemaPublic() {
  const [screenings, setScreenings] = useState([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    api
      .listScreenings(true)
      .then((data) => {
        setScreenings(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  const groups = groupByDate(screenings);

  return (
    <div className="cinema-public-page">
      <header className="cinema-public-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            🎬
          </span>
          Voldby BIO
        </div>
      </header>

      <main className="cinema-public-main">
        <CinemaShowcase />

        <div className="cinema-program">
          {status === "loading" && <p className="muted">Indlæser program...</p>}
          {status === "error" && (
            <div className="banner banner-error">Kunne ikke hente programmet.</div>
          )}
          {status === "ready" && groups.length === 0 && (
            <p className="muted">Ingen kommende visninger er planlagt endnu.</p>
          )}

          {groups.map((group) => (
            <div key={group.key} className="cinema-day">
              <h2 className="cinema-day-heading">{formatDateHeading(group.date)}</h2>
              <div className="cinema-cards">
                {group.screenings.map((screening) => (
                  <PublicScreeningCard key={screening.id} screening={screening} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

function PublicScreeningCard({ screening }) {
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
      </div>
    </div>
  );
}
