import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLocale, useT } from "../i18n";
import "./Statistics.css";

// Feature #89 — locale og oversætter kommer ind som argumenter frem for
// via hooks: funktionen er ikke en komponent og må derfor ikke kalde dem.
function formatRuntime(totalMinutes, t, locale) {
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return t("stats.runtime", { hours: hours.toLocaleString(locale), minutes });
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
  const t = useT();
  const locale = useLocale();
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
        <h1>{t("stats.title")}</h1>
      </div>

      {status === "loading" && <p className="muted">{t("common.loading")}</p>}
      {status === "error" && (
        <div className="banner banner-error">{t("stats.loadError")}</div>
      )}

      {status === "ready" && stats && (
        <>
          <div className="stat-summary-grid">
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{stats.total_movies}</div>
              <div className="stat-summary-label">{t("stats.moviesInLibrary")}</div>
            </div>
            <div className="card stat-summary-card">
              <div className="stat-summary-value">
                {formatRuntime(stats.total_runtime_minutes, t, locale)}
              </div>
              <div className="stat-summary-label">{t("stats.totalRuntime")}</div>
            </div>
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{stats.watched_count}</div>
              <div className="stat-summary-label">{t("stats.watched")}</div>
            </div>
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{stats.unwatched_count}</div>
              <div className="stat-summary-label">{t("stats.unwatched")}</div>
            </div>
          </div>

          <div className="stat-sections-grid">
            {stats.genre_breakdown.length > 0 && (
              <div className="card stat-section">
                <h2>{t("stats.genres")}</h2>
                <BarList items={stats.genre_breakdown} />
              </div>
            )}

            {stats.decade_breakdown.length > 0 && (
              <div className="card stat-section">
                <h2>{t("stats.decades")}</h2>
                <BarList items={stats.decade_breakdown} />
              </div>
            )}

            {stats.format_breakdown.length > 0 && (
              <div className="card stat-section">
                <h2>{t("stats.format")}</h2>
                <BarList items={stats.format_breakdown} />
              </div>
            )}

            {stats.top_directors.length > 0 && (
              <div className="card stat-section">
                <h2>{t("stats.topDirectors")}</h2>
                <BarList items={stats.top_directors} />
              </div>
            )}

            {stats.top_actors.length > 0 && (
              <div className="card stat-section">
                <h2>{t("stats.topActors")}</h2>
                <BarList items={stats.top_actors} />
              </div>
            )}

            {stats.barcode_source_breakdown.length > 0 && (
              <div className="card stat-section">
                <h2>{t("stats.barcodeSource")}</h2>
                <p className="muted" style={{ marginTop: 0 }}>
                  {t("stats.barcodeSourceHint")}
                </p>
                <BarList items={stats.barcode_source_breakdown} />
              </div>
            )}
          </div>

          {stats.total_movies === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon">📊</div>
              <p>{t("stats.empty")}</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
