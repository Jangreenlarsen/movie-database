import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./Statistics.css";

function formatRuntime(totalMinutes) {
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours.toLocaleString("da-DK")} timer ${minutes} min`;
}

function BarList({ items }) {
  const max = Math.max(1, ...items.map((item) => item.count));
  return (
    <ul className="stat-bar-list">
      {items.map((item) => (
        <li key={item.name} className="stat-bar-row">
          <span className="stat-bar-label">{item.name}</span>
          <span className="stat-bar-track">
            <span className="stat-bar-fill" style={{ width: `${(item.count / max) * 100}%` }} />
          </span>
          <span className="stat-bar-count">{item.count}</span>
        </li>
      ))}
    </ul>
  );
}

export default function Statistics() {
  const [stats, setStats] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    api
      .getStats()
      .then((data) => {
        setStats(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  return (
    <section>
      <div className="page-header">
        <h1>Statistik</h1>
      </div>

      {status === "loading" && <p className="muted">Indlæser...</p>}
      {status === "error" && (
        <div className="banner banner-error">Kunne ikke hente statistik.</div>
      )}

      {status === "ready" && stats && (
        <>
          <div className="stat-summary-grid">
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{stats.total_movies}</div>
              <div className="stat-summary-label">Film i biblioteket</div>
            </div>
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{formatRuntime(stats.total_runtime_minutes)}</div>
              <div className="stat-summary-label">Samlet spilletid</div>
            </div>
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{stats.watched_count}</div>
              <div className="stat-summary-label">Set</div>
            </div>
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{stats.unwatched_count}</div>
              <div className="stat-summary-label">Ikke set</div>
            </div>
          </div>

          <div className="stat-sections-grid">
            {stats.genre_breakdown.length > 0 && (
              <div className="card stat-section">
                <h2>Genrer</h2>
                <BarList items={stats.genre_breakdown} />
              </div>
            )}

            {stats.decade_breakdown.length > 0 && (
              <div className="card stat-section">
                <h2>Årtier</h2>
                <BarList items={stats.decade_breakdown} />
              </div>
            )}

            {stats.format_breakdown.length > 0 && (
              <div className="card stat-section">
                <h2>Format</h2>
                <BarList items={stats.format_breakdown} />
              </div>
            )}

            {stats.top_directors.length > 0 && (
              <div className="card stat-section">
                <h2>Mest forekommende instruktører</h2>
                <BarList items={stats.top_directors} />
              </div>
            )}

            {stats.top_actors.length > 0 && (
              <div className="card stat-section">
                <h2>Mest forekommende skuespillere</h2>
                <BarList items={stats.top_actors} />
              </div>
            )}
          </div>

          {stats.total_movies === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon">📊</div>
              <p>Biblioteket er tomt endnu — der er ikke noget at vise statistik for.</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
