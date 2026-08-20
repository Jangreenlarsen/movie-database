import { useEffect, useState } from "react";
import { api } from "../api/client";
import CinemaShowcase from "../components/CinemaShowcase";
import DateTime24Input from "../components/DateTime24Input";
import SeatSelectionModal from "../components/SeatSelectionModal";
import { formatDateHeading, formatShortDate, formatTime, groupByDate } from "../utils/cinemaFormat";
import { posterSrc } from "../utils/posterUrl";
import { useLocale, useT } from "../i18n";
// Feature #185 — RequestDetailModal genbruger .modal-backdrop/.modal-card/
// .modal-footer, defineret i Library.css (samme grund til TvShows.jsx også
// importerer den) — uden denne import ville modalen stå ustylet ved en kold
// navigation direkte til /cinema, uden at Library.jsx nogensinde er indlæst.
import "./Library.css";
import "./Cinema.css";

// Feature #133/#134 — lille biografstole-ikon på seat-valg-knappen. (Det
// tidligere `Seat valg.png` var et screenshot af HELE modulet, så knappen så
// "udfoldet" ud; sædekortet folder først ud i modalen ved klik — Jan 2026-08-13.)
const SEAT_BUTTON_IMG = "/cinema/movie-seat.png";

// Feature #133 — de 14 faste sæder (samme katalog som backendens
// models/reservation.py), til admin-hold-vælgeren.
const SEAT_OPTIONS = [
  { id: "N1-1", number: 1 }, { id: "N1-2", number: 2 }, { id: "N1-3", number: 3 },
  { id: "N1-4", number: 4 }, { id: "N2-1", number: 5 }, { id: "N2-2", number: 6 },
  { id: "N2-3", number: 7 }, { id: "N2-4", number: 8 }, { id: "N2-5", number: 9 },
  { id: "N3-1", number: 10 }, { id: "N3-2", number: 11 }, { id: "N3-3", number: 12 },
  { id: "N3-4", number: 13 }, { id: "N3-5", number: 14 },
];

export default function Cinema({ user }) {
  const t = useT();
  const locale = useLocale();
  const isAdmin = user.role === "admin";
  // Feature #170 — private arrangementer skjuler sæde-knappen for gæster.
  const isGuest = user.role === "guest";
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
      {isAdmin && <ReservationAdmin screenings={screenings} />}

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
                  isGuest={isGuest}
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

function ScreeningCard({ screening, isAdmin, isGuest, onChanged }) {
  const t = useT();
  const locale = useLocale();
  const [editing, setEditing] = useState(false);
  const [scheduledAt, setScheduledAt] = useState(screening.scheduled_at.slice(0, 16));
  const [note, setNote] = useState(screening.note ?? "");
  // Feature #170 — Jan: admin skal kunne markere en visning som et privat
  // arrangement, som gæst-rollen ikke kan booke sæder på.
  const [isPrivate, setIsPrivate] = useState(screening.is_private ?? false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [seatOpen, setSeatOpen] = useState(false);
  const blockedForGuest = screening.is_private && isGuest;

  async function saveEdit() {
    setBusy(true);
    setError(null);
    try {
      await api.updateScreening(screening.id, {
        scheduled_at: scheduledAt,
        note: note || null,
        is_private: isPrivate,
      });
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
      {/* Feature #133 — film-ikon + seat-valg-knap i en lodret media-kolonne,
          så knappen står UNDER ikonet og titlen/teksten får fuld bredde i
          boksen (Jans ønske 2026-08-13). */}
      <div className="cinema-card-media">
        <div className="cinema-card-poster">
          {screening.poster_url ? (
            <img src={posterSrc(screening.poster_url, "w342")} alt={screening.title ?? ""} loading="lazy" />
          ) : (
            <span>{screening.media_kind === "movie" ? "🎬" : "📺"}</span>
          )}
        </div>
        {blockedForGuest ? (
          // Feature #170 — sæde-knappen skjules helt for gæster på et privat
          // arrangement i stedet for at lade dem åbne sædekortet og først
          // fejle ved selve reservationen; backend håndhæver det samme
          // uafhængigt (reservation_service.reserve_seats), dette er kun UX.
          <div
            className="cinema-card-seat cinema-card-seat-blocked"
            title={t("cinema.privateEventGuestBlocked")}
          >
            <span aria-hidden="true">🔒</span>
            <span>{t("cinema.privateEventGuestBlocked")}</span>
          </div>
        ) : (
          <button
            type="button"
            className="cinema-card-seat"
            onClick={() => setSeatOpen(true)}
            title={t("seat.button")}
          >
            <img src={SEAT_BUTTON_IMG} alt="" />
            <span>{t("seat.button")}</span>
          </button>
        )}
      </div>
      {seatOpen && (
        <SeatSelectionModal
          screeningId={screening.id}
          screeningTitle={screening.title ?? t("cinema.unknownTitle")}
          onClose={() => setSeatOpen(false)}
        />
      )}
      <div className="cinema-card-body">
        <div className="cinema-card-time">{formatTime(screening.scheduled_at, locale)}</div>
        {screening.is_private && (
          <div className="cinema-card-private-badge" title={t("cinema.privateEventHint")}>
            🔒 {t("cinema.privateEvent")}
          </div>
        )}
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
            <label className="cinema-private-toggle">
              <input
                type="checkbox"
                checked={isPrivate}
                onChange={(e) => setIsPrivate(e.target.checked)}
              />
              {t("cinema.privateEvent")}
            </label>
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

export function RequestRow({ request, onChanged }) {
  const t = useT();
  const locale = useLocale();
  const suggestion = earliestUpcomingSuggestion(request.requested_by);
  const [scheduling, setScheduling] = useState(false);
  const [scheduledAt, setScheduledAt] = useState(suggestion);
  const [note, setNote] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // Feature #185 (Jan: "i voldby bio kort vil det være fint hvis man kan
  // trykke på de film der er under Anmodninger så man kan se detajler")
  const [showDetail, setShowDetail] = useState(false);

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
        is_private: isPrivate,
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
      <div
        className="cinema-request-poster cinema-request-clickable"
        onClick={() => setShowDetail(true)}
        title={t("cinema.viewDetails")}
      >
        {request.poster_url ? (
          <img src={posterSrc(request.poster_url, "w185")} alt={request.title ?? ""} />
        ) : (
          <span>{request.media_kind === "movie" ? "🎬" : "📺"}</span>
        )}
      </div>
      <div className="cinema-request-info">
        <strong
          className="cinema-request-clickable"
          onClick={() => setShowDetail(true)}
          title={t("cinema.viewDetails")}
        >
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
          <label className="cinema-private-toggle">
            <input
              type="checkbox"
              checked={isPrivate}
              onChange={(e) => setIsPrivate(e.target.checked)}
            />
            {t("cinema.privateEvent")}
          </label>
          <button type="button" className="btn btn-primary" onClick={schedule} disabled={!scheduledAt || busy}>
            {t(busy ? "cinema.scheduling" : "cinema.confirm")}
          </button>
          <button type="button" className="btn" onClick={() => setScheduling(false)} disabled={busy}>
            {t("common.cancel")}
          </button>
        </div>
      )}
      {error && <div className="banner banner-error" style={{ marginTop: 8 }}>{error}</div>}

      {showDetail && (
        <RequestDetailModal
          mediaKind={request.media_kind}
          id={request.media_kind === "movie" ? request.movie_id : request.tv_show_id}
          onClose={() => setShowDetail(false)}
        />
      )}
    </div>
  );
}

/**
 * Feature #185 — let, read-only visning af det en anmodning peger på (poster,
 * spilletid, genrer, rating, plot). Anmodningen selv har kun titel/år/poster
 * (øjebliksbillede taget ved anmodningstidspunktet); resten hentes friskt via
 * `movie_id`/`tv_show_id`. Bevidst IKKE en genbrug af Library.jsx/TvShows.jsx's
 * fulde `MovieDetailModal`/`TvShowDetailModal` — de kræver tags/ejere/
 * lokationer/attribut-lister til redigering, som slet ikke er relevante her;
 * dette er kun "se hvad det er", ikke en redigerings-genvej.
 */
export function RequestDetailModal({ mediaKind, id, onClose }) {
  const t = useT();
  const [item, setItem] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetcher = mediaKind === "movie" ? api.getMovie(id) : api.getTvShow(id);
    fetcher.then(setItem).catch((err) => setError(err.message));
  }, [mediaKind, id]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card cinema-request-detail-card" onClick={(e) => e.stopPropagation()}>
        {error && <div className="banner banner-error">{error}</div>}
        {!item && !error && <p className="muted">{t("common.loading")}</p>}
        {item && (
          <div className="cinema-request-detail-body">
            {item.poster_url ? (
              <img
                src={posterSrc(item.poster_url, "w342")}
                alt=""
                className="cinema-request-detail-poster"
              />
            ) : (
              <div className="cinema-request-detail-poster cinema-request-detail-poster-fallback">
                {mediaKind === "movie" ? "🎬" : "📺"}
              </div>
            )}
            <div className="cinema-request-detail-info">
              <h3>
                {(item.title ?? item.name) ?? t("cinema.unknown")} {item.year ? `(${item.year})` : ""}
              </h3>
              <dl className="cinema-request-detail-grid">
                {mediaKind === "movie" && item.runtime != null && (
                  <>
                    <dt>{t("field.runtime")}</dt>
                    <dd>{t("lib.minutes", { minutes: item.runtime })}</dd>
                  </>
                )}
                {mediaKind === "tv" && item.number_of_seasons != null && (
                  <>
                    <dt>{t("field.numberOfSeasons")}</dt>
                    <dd>{item.number_of_seasons}</dd>
                  </>
                )}
                {item.genres?.length > 0 && (
                  <>
                    <dt>{t("field.genres")}</dt>
                    <dd>{item.genres.join(", ")}</dd>
                  </>
                )}
                {item.rating != null && (
                  <>
                    <dt>{t("field.rating")}</dt>
                    <dd>{item.rating.toFixed(1)}</dd>
                  </>
                )}
              </dl>
              {item.overview && <p className="muted">{item.overview}</p>}
            </div>
          </div>
        )}
        <div className="modal-footer">
          <button type="button" className="btn" onClick={onClose}>
            {t("common.close")}
          </button>
        </div>
      </div>
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
  const [isPrivate, setIsPrivate] = useState(false);
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
        is_private: isPrivate,
      });
      setSelected(null);
      setResults([]);
      setQuery("");
      setScheduledAt("");
      setNote("");
      setIsPrivate(false);
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
              {result.poster_url ? <img src={posterSrc(result.poster_url, "w185")} alt="" /> : <span>{result.media_kind === "movie" ? "🎬" : "📺"}</span>}
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
          <label className="cinema-private-toggle">
            <input
              type="checkbox"
              checked={isPrivate}
              onChange={(e) => setIsPrivate(e.target.checked)}
            />
            {t("cinema.privateEvent")}
          </label>
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

// Feature #133 — konduktør-modulet: kø over ventende sæde-reservationer
// (godkend/afvis) + værktøj til at for-reservere et bestemt sæde (global eller
// film-specifik). Kun admin (renderes bag isAdmin i Cinema).
function ReservationAdmin({ screenings }) {
  const t = useT();
  const [pending, setPending] = useState([]);
  const [approved, setApproved] = useState([]);
  const [status, setStatus] = useState("loading");

  function refresh() {
    // Feature #133/#137 — både ventende (til godkendelse) og godkendte/hold
    // (til tilbagetrækning). Godkendte gæste-reservationer OG admin-hold har
    // begge status "approved" i backenden, så én ?status=approved-hentning
    // dækker begge.
    return Promise.all([
      api.listReservations({ status: "pending" }),
      api.listReservations({ status: "approved" }),
    ])
      .then(([pendingRows, approvedRows]) => {
        setPending(pendingRows);
        setApproved(approvedRows);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="card cinema-panel">
      <h2>{t("cinema.reservations")}</h2>
      <p className="muted">{t("cinema.reservationsHint")}</p>

      {status === "loading" && <p className="muted">{t("common.loading")}</p>}
      {status === "error" && (
        <div className="banner banner-error">{t("cinema.reservationsLoadError")}</div>
      )}
      {status === "ready" && pending.length === 0 && (
        <p className="muted">{t("cinema.noPendingReservations")}</p>
      )}

      <div className="cinema-reservations">
        {pending.map((reservation) => (
          <ReservationRow key={reservation.id} reservation={reservation} onChanged={refresh} />
        ))}
      </div>

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      {/* Feature #137 — godkendte + for-reserverede sæder, med tilbagetrækning
          (gælder også globale admin-hold, Jans ønske 2026-08-13). */}
      <h3 style={{ marginTop: 0 }}>{t("cinema.approvedSeats")}</h3>
      <p className="muted">{t("cinema.approvedSeatsHint")}</p>
      {status === "ready" && approved.length === 0 && (
        <p className="muted">{t("cinema.noApprovedSeats")}</p>
      )}
      <div className="cinema-reservations">
        {approved.map((reservation) => (
          <ApprovedRow key={reservation.id} reservation={reservation} onChanged={refresh} />
        ))}
      </div>

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <HoldTool screenings={screenings} onChanged={refresh} />
    </div>
  );
}

function ApprovedRow({ reservation, onChanged }) {
  const t = useT();
  const locale = useLocale();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function retract() {
    if (!window.confirm(t("cinema.retractConfirm", { seat: reservation.seat_number }))) return;
    setBusy(true);
    setError(null);
    try {
      await api.cancelReservation(reservation.id);
      onChanged();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const descriptor = reservation.is_hold
    ? reservation.scope === "global"
      ? t("cinema.holdGlobalLabel")
      : t("cinema.holdScreeningLabel", {
          title: reservation.screening_title ?? t("cinema.unknownTitle"),
        })
    : reservation.screening_title ?? t("cinema.unknownTitle");

  return (
    <div className="cinema-reservation-row">
      <div className="cinema-reservation-info">
        <strong>{t("seat.seatLabel", { number: reservation.seat_number })}</strong>
        <div className="muted">
          {descriptor}
          {!reservation.is_hold && reservation.screening_at
            ? ` · ${formatShortDate(reservation.screening_at, locale)} ${formatTime(reservation.screening_at, locale)}`
            : ""}
        </div>
        <div className="muted">
          {reservation.is_hold
            ? t("cinema.heldBy", { name: reservation.reserved_by })
            : t("cinema.reservedBy", { name: reservation.reserved_by })}
        </div>
      </div>
      <div className="cinema-reservation-actions">
        <button type="button" className="btn" onClick={retract} disabled={busy}>
          {t("cinema.retract")}
        </button>
      </div>
      {error && <div className="banner banner-error" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  );
}

function ReservationRow({ reservation, onChanged }) {
  const t = useT();
  const locale = useLocale();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      await api.approveReservation(reservation.id);
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
      await api.cancelReservation(reservation.id);
      onChanged();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="cinema-reservation-row">
      <div className="cinema-reservation-info">
        <strong>{t("seat.seatLabel", { number: reservation.seat_number })}</strong>
        <div className="muted">
          {reservation.screening_title ?? t("cinema.unknownTitle")}
          {reservation.screening_at
            ? ` · ${formatShortDate(reservation.screening_at, locale)} ${formatTime(reservation.screening_at, locale)}`
            : ""}
        </div>
        <div className="muted">{t("cinema.reservedBy", { name: reservation.reserved_by })}</div>
      </div>
      <div className="cinema-reservation-actions">
        <button type="button" className="btn btn-primary" onClick={approve} disabled={busy}>
          {t("cinema.approve")}
        </button>
        <button type="button" className="btn" onClick={decline} disabled={busy}>
          {t("cinema.decline")}
        </button>
      </div>
      {error && <div className="banner banner-error" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  );
}

function HoldTool({ screenings, onChanged }) {
  const t = useT();
  const locale = useLocale();
  const [seatId, setSeatId] = useState("N1-1");
  const [scope, setScope] = useState("global");
  const [screeningId, setScreeningId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(false);

  const canSubmit = seatId && (scope === "global" || screeningId);

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    setOk(false);
    try {
      await api.holdSeat({
        seat_id: seatId,
        scope,
        ...(scope === "screening" ? { screening_id: screeningId } : {}),
      });
      setOk(true);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h3 style={{ marginTop: 0 }}>{t("cinema.holdTitle")}</h3>
      <p className="muted">{t("cinema.holdHint")}</p>
      <div className="cinema-hold-form">
        <label>
          {t("cinema.holdSeat")}
          <select value={seatId} onChange={(e) => setSeatId(e.target.value)}>
            {SEAT_OPTIONS.map((seat) => (
              <option key={seat.id} value={seat.id}>
                {t("seat.seatLabel", { number: seat.number })}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("cinema.holdScope")}
          <select
            value={scope}
            onChange={(e) => {
              setScope(e.target.value);
              setOk(false);
            }}
          >
            <option value="global">{t("cinema.holdGlobal")}</option>
            <option value="screening">{t("cinema.holdScreening")}</option>
          </select>
        </label>
        {scope === "screening" && (
          <label>
            {t("cinema.holdPickScreening")}
            <select value={screeningId} onChange={(e) => setScreeningId(e.target.value)}>
              <option value="">{t("cinema.holdChoose")}</option>
              {screenings.map((screening) => (
                <option key={screening.id} value={screening.id}>
                  {(screening.title ?? t("cinema.unknownTitle")) +
                    " · " +
                    formatShortDate(screening.scheduled_at, locale)}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          type="button"
          className="btn btn-primary"
          onClick={submit}
          disabled={busy || !canSubmit}
        >
          {t(busy ? "cinema.holding" : "cinema.holdSubmit")}
        </button>
      </div>
      {ok && <div className="banner banner-info" style={{ marginTop: 8 }}>{t("cinema.holdSuccess")}</div>}
      {error && <div className="banner banner-error" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  );
}
