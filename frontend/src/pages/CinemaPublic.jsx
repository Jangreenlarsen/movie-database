import { useEffect, useState } from "react";
import { api } from "../api/client";
import CinemaShowcase from "../components/CinemaShowcase";
import { formatShortDate, formatTime } from "../utils/cinemaFormat";
import "./CinemaPublic.css";

// Feature #70 — public, no-login page at /bio. Read-only: no admin tools,
// no "ønsk visning"/anmeldelses-knapper, just the showcase section + the
// upcoming program. Deliberately a separate component from Cinema.jsx
// rather than a "publicOnly" prop on it — Cinema.jsx assumes a logged-in
// `user` throughout (role checks, screening-request actions), and keeping
// the public route as its own simple component avoids having to thread a
// "no user" case through all of that.
//
// v2 (Jans feedback 2026-08-03): "Om Voldby BIO" moved back above the
// program, and every upcoming screening now sits in one flat side-by-side
// poster grid instead of being grouped under full per-day headings — with
// mostly one screening per day, date-grouping just produced a long single
// column of near-empty rows.
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

  return (
    <div className="cinema-public-page">
      <header className="cinema-public-hero">
        <h1>🎬 Voldby BIO</h1>
        <p className="cinema-public-tagline">Hjemmebiografen — se hvad der går i bio herunder.</p>
      </header>

      <main className="cinema-public-main">
        <section>
          <h2 className="cinema-public-section-heading">Om Voldby BIO</h2>
          <CinemaShowcase />
        </section>

        <section>
          <h2 className="cinema-public-section-heading">Hvad går i bio</h2>
          {status === "loading" && <p className="muted">Indlæser program...</p>}
          {status === "error" && (
            <div className="banner banner-error">Kunne ikke hente programmet.</div>
          )}
          {status === "ready" && screenings.length === 0 && (
            <p className="muted">Ingen kommende visninger er planlagt endnu.</p>
          )}

          {screenings.length > 0 && (
            <div className="bio-poster-grid">
              {screenings.map((screening) => (
                <PublicScreeningCard key={screening.id} screening={screening} />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function PublicScreeningCard({ screening }) {
  return (
    <div className="bio-poster-card">
      <div className="bio-poster-card-poster">
        {screening.poster_url ? (
          <img src={screening.poster_url} alt={screening.title ?? ""} loading="lazy" />
        ) : (
          <span>{screening.media_kind === "movie" ? "🎬" : "📺"}</span>
        )}
        <div className="bio-poster-card-datetime">
          {formatShortDate(screening.scheduled_at)} · {formatTime(screening.scheduled_at)}
        </div>
      </div>
      <div className="bio-poster-card-body">
        <h3 className="bio-poster-card-title">
          {screening.title ?? "Ukendt titel"}
          {screening.year ? ` (${screening.year})` : ""}
        </h3>
        {screening.genres?.length > 0 && (
          <div className="bio-poster-card-genres">{screening.genres.join(", ")}</div>
        )}
      </div>
    </div>
  );
}
