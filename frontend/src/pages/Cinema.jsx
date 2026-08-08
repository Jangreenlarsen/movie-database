import { useEffect, useState } from "react";
import { api } from "../api/client";
import CinemaShowcase from "../components/CinemaShowcase";
import DateTime24Input from "../components/DateTime24Input";
import { formatDateHeading, formatShortDate, formatTime, groupByDate } from "../utils/cinemaFormat";
import { useLocale, useT } from "../i18n";
import "./Cinema.css";

export default function Cinema({ user }) {
  const t = useT();
  const locale = useLocale();
  const isAdmin = user.role === "admin";
  const [screenings, setScreenings] = useState([]);
  const [status, setStatus] = useState("loading");
  const [linkCopied, setLinkCopied] = useState(false);

  function copyPublicLink() {
    const url = `${window.location.origin}/bio`;
    navigator.clipboard
      .writeText(url)
      .then(() => {
        setLinkCopied(true);
        setTimeout(() => setLinkCopied(false), 2000);
      })
      .catch(() => {});
  }

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
        <h1>{t("cinema.title")}</h1>
        <button type="button" className="btn" onClick={copyPublicLink}>
          {t(linkCopied ? "cinema.linkCopied" : "cinema.shareLink")}
        </button>
      </div>

      <CinemaShowcase />

      {isAdmin && <AdminScreeningTools onChanged={refresh} />}

      <div className="cinema-program">
        {status === "loading" && <p className="muted">{t("cinema.loadingProgram")}</p>}
        {status === "error" && (
          <div className="banner banner-error">{t("cinema.programLoadError")}</div>
        )}
        {status === "ready" && groups.length === 0 && (
          <p className="muted">{t("cinema.noScreenings")}</p>
        )}

        {groups.map((group) => (
          <div key={group.key} className="cinema-day">
            <h2 className="cinema-day-heading">{formatDateHeading(group.date, locale)}</h2>
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
  const t = useT();
  const locale = useLocale();
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
    if (!window.confirm(t("cinema.confirmRemove", { title: screening.title }))) return;
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
        <div className="cinema-card-time">{formatTime(screening.scheduled_at, locale)}</div>
        <h3 className="cinema-card-title">
          {screening.title ?? t("cinema.unknownTitle")}
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
              {t("cinema.watchTrailer")}
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
              {t("cinema.edit")}
            </button>
            <button type="button" className="btn" onClick={removeScreening} disabled={busy}>
              {t("cinema.remove")}
            </button>
          </div>
        )}

        {isAdmin && editing && (
          <div className="cinema-card-admin-actions cinema-card-edit-form">
            <DateTime24Input value={scheduledAt} onChange={setScheduledAt} />
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t("cinema.notePlaceholder")}
            />
            <button type="button" className="btn btn-primary" onClick={saveEdit} disabled={busy}>
              {t(busy ? "common.saving" : "common.save")}
            </button>
            <button type="button" className="btn" onClick={() => setEditing(false)} disabled={busy}>
              {t("common.cancel")}
            </button>
          </div>
        )}

        {error && <div className="banner banner-error" style={{ marginTop: 8 }}>{error}</div>}
      </div>
    </div>
  );
}

function AdminScreeningTools({ onChanged }) {
  const t = useT();
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
      <h2>{t("cinema.requests")}</h2>
      <p className="muted">{t("cinema.requestsHint")}</p>

      {status === "loading" && <p className="muted">{t("common.loading")}</p>}
      {status === "error" && (
        <div className="banner banner-error">{t("cinema.requestsLoadError")}</div>
      )}
      {status === "ready" && requests.length === 0 && (
        <p className="muted">{t("cinema.noPendingRequests")}</p>
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

/**
 * Feature #85 — det tidligste foreslåede tidspunkt der stadig ligger i
 * fremtiden, som "YYYY-MM-DDTHH:MM" (samme streng-format som
 * DateTime24Input og API'et bruger). Bruges til at forudfylde
 * planlægnings-feltet: et forslag, ikke en binding — admin kan rette det
 * frit inden "Bekræft". Forslag der er overstået er bevidst sprunget over,
 * så en gammel anmodning ikke forudfylder en dato i fortiden.
 */
function earliestUpcomingSuggestion(requestedBy) {
  const now = Date.now();
  const upcoming = requestedBy
    .map((r) => r.preferred_at)
    .filter((value) => value && new Date(value).getTime() > now)
    .sort();
  return upcoming.length > 0 ? upcoming[0].slice(0, 16) : "";
}

function RequestRow({ request, onChanged }) {
  const t = useT();
  const locale = useLocale();
  const suggestion = earliestUpcomingSuggestion(request.requested_by);
  const [scheduling, setScheduling] = useState(false);
  const [scheduledAt, setScheduledAt] = useState(suggestion);
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
          {request.title ?? t("cinema.unknown")} {request.year ? `(${request.year})` : ""}
        </strong>
        <div className="muted">
          {t("cinema.requestedBy", {
            names: request.requested_by.map((r) => r.username).join(", "),
          })}
        </div>
        {/* Feature #85 — kun de ønskere der faktisk skrev noget får en
            linje, så en anmodning uden beskeder ser ud som før. */}
        {request.requested_by
          .filter((r) => r.message || r.preferred_at)
          .map((r) => (
            <div key={r.username} className="cinema-request-wish">
              <strong>{r.username}</strong>
              {r.message && <> „{r.message}“</>}
              {r.preferred_at && (
                <>
                  {" "}
                  {t("request.at", {
                    date: formatShortDate(r.preferred_at, locale),
                    time: formatTime(r.preferred_at, locale),
                  })}
                </>
              )}
            </div>
          ))}
      </div>

      {!scheduling ? (
        <div className="cinema-request-actions">
          <button type="button" className="btn btn-primary" onClick={() => setScheduling(true)}>
            {t("cinema.schedule")}
          </button>
          <button type="button" className="btn" onClick={decline} disabled={busy}>
            {t("cinema.decline")}
          </button>
        </div>
      ) : (
        <div className="cinema-request-actions cinema-card-edit-form">
          {suggestion && (
            <span className="muted cinema-request-suggestion-hint">
              {t("cinema.suggestionHint")}
            </span>
          )}
          <DateTime24Input value={scheduledAt} onChange={setScheduledAt} />
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t("cinema.notePlaceholder")}
          />
          <button type="button" className="btn btn-primary" onClick={schedule} disabled={!scheduledAt || busy}>
            {t(busy ? "cinema.scheduling" : "cinema.confirm")}
          </button>
          <button type="button" className="btn" onClick={() => setScheduling(false)} disabled={busy}>
            {t("common.cancel")}
          </button>
        </div>
      )}
      {error && <div className="banner banner-error" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  );
}

function DirectAddSection({ onChanged }) {
  const t = useT();
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
      ...movies.items.map((m) => ({ media_kind: "movie", id: m.id, title: m.title, year: m.year, poster_url: m.poster_url })),
      ...shows.items.map((s) => ({ media_kind: "tv", id: s.id, title: s.name, year: s.year, poster_url: s.poster_url })),
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
      <h3 style={{ marginTop: 0 }}>{t("cinema.addDirectly")}</h3>
      <p className="muted">{t("cinema.addDirectlyHint")}</p>
      <form className="cinema-search-form" onSubmit={search}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("cinema.searchLibraryPlaceholder")}
        />
        <button type="submit" className="btn">
          {t("scan.search")}
        </button>
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
          <DateTime24Input value={scheduledAt} onChange={setScheduledAt} />
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t("cinema.notePlaceholder")}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={addDirectly}
            disabled={!scheduledAt || busy}
          >
            {t(busy ? "cinema.adding" : "cinema.addToProgram")}
          </button>
          <button type="button" className="btn" onClick={() => setSelected(null)} disabled={busy}>
            {t("common.cancel")}
          </button>
        </div>
      )}
      {error && <div className="banner banner-error" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  );
}
