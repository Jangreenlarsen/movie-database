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

// Feature #125 — side-nøgler fra backend oversættes til nav-etiketterne, så
// "hvad de besøger" læses i samme sprog som fanerne. "bio" er den offentlige
// Voldby BIO-side (uden login) og får sin egen etikette, adskilt fra den
// indloggede cinema-fane.
const PAGE_LABEL_KEYS = {
  library: "app.nav.movies",
  tv: "app.nav.tv",
  wishlist: "app.nav.wishlist",
  cinema: "app.nav.cinema",
  print: "app.nav.print",
  stats: "app.nav.stats",
  settings: "app.nav.settings",
};

const GUEST_SENTINEL = "__guest__";

export function pageLabel(t, key) {
  if (key === "bio") return t("stats.visits.pageBio");
  return PAGE_LABEL_KEYS[key] ? t(PAGE_LABEL_KEYS[key]) : key;
}

// "YYYY-MM-DD" → "DD/MM" (rent tekst-slice, ingen Date-parsing/locale-afhæng).
export function shortDay(iso) {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
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
  // Feature #125 — besøgs-statistik hentes for sig, så en fejl her ikke skjuler
  // biblioteks-statistikken (og omvendt).
  const [visits, setVisits] = useState(null);
  const [visitsStatus, setVisitsStatus] = useState("loading");

  useEffect(() => {
    api
      .getStats()
      .then((data) => {
        setStats(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
    api
      .getVisitStats()
      .then((data) => {
        setVisits(data);
        setVisitsStatus("ready");
      })
      .catch(() => setVisitsStatus("error"));
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

      {/* Feature #125 — besøgs-statistik. Egen sektion, uafhængig af
          biblioteks-statistikken ovenfor. */}
      <h2 className="stat-visits-heading">{t("stats.visits.title")}</h2>

      {visitsStatus === "loading" && <p className="muted">{t("common.loading")}</p>}
      {visitsStatus === "error" && (
        <div className="banner banner-error">{t("stats.visits.loadError")}</div>
      )}

      {visitsStatus === "ready" && visits && (
        <>
          <div className="stat-summary-grid">
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{visits.total_visits}</div>
              <div className="stat-summary-label">{t("stats.visits.total")}</div>
            </div>
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{visits.visits_today}</div>
              <div className="stat-summary-label">{t("stats.visits.today")}</div>
            </div>
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{visits.unique_users}</div>
              <div className="stat-summary-label">{t("stats.visits.uniqueUsers")}</div>
            </div>
            <div className="card stat-summary-card">
              <div className="stat-summary-value">{visits.guest_visits}</div>
              <div className="stat-summary-label">{t("stats.visits.guests")}</div>
            </div>
          </div>

          {visits.total_visits === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">👣</div>
              <p>{t("stats.visits.empty")}</p>
            </div>
          ) : (
            <div className="stat-sections-grid">
              <div className="card stat-section">
                <h2>{t("stats.visits.perDay")}</h2>
                <BarList
                  items={visits.per_day.map((d) => ({ name: shortDay(d.name), count: d.count }))}
                />
              </div>

              {visits.per_page.length > 0 && (
                <div className="card stat-section">
                  <h2>{t("stats.visits.perPage")}</h2>
                  <BarList
                    items={visits.per_page.map((p) => ({ name: pageLabel(t, p.name), count: p.count }))}
                  />
                </div>
              )}

              {visits.top_titles.length > 0 && (
                <div className="card stat-section">
                  <h2>{t("stats.visits.topTitles")}</h2>
                  <BarList items={visits.top_titles} />
                </div>
              )}

              {visits.per_user.length > 0 && (
                <div className="card stat-section">
                  <h2>{t("stats.visits.perUser")}</h2>
                  <BarList
                    items={visits.per_user.map((u) => ({
                      name: u.name === GUEST_SENTINEL ? t("stats.visits.guest") : u.name,
                      count: u.count,
                    }))}
                  />
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
