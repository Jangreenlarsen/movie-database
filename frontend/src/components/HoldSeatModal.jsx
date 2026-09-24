import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLocale, useT } from "../i18n";
import { formatShortDate } from "../utils/cinemaFormat";
import { announceReservationsChanged } from "../utils/reservationEvents";
import { holdBlockedSeatIds } from "../utils/reservationGroups";
import SeatRoom from "./SeatRoom";
import "./SeatSelectionModal.css";

/**
 * Feature #231 — admins "For-reservér et sæde" med samme grafiske sal som
 * gæsternes sædevalg. Optagede sæder beregnes ud fra de reservationer
 * admin-panelet allerede har hentet (samme regler som backend), og det
 * valgte omfang ("alle visninger" eller én visning) afgør hvad der er
 * optaget. Backend tjekker stadig selv ved oprettelsen.
 *
 * `seats` er det faste katalog [{ id, number }] (Cinema.jsx' SEAT_OPTIONS).
 */
export default function HoldSeatModal({ seats, screenings, reservations, onClose, onChanged }) {
  const t = useT();
  const locale = useLocale();
  const [scope, setScope] = useState("global");
  const [screeningId, setScreeningId] = useState("");
  const [selected, setSelected] = useState(() => new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const needsScreening = scope === "screening" && !screeningId;
  const blocked = needsScreening
    ? new Set()
    : holdBlockedSeatIds(reservations, scope, screeningId);
  // Et valgt sæde der siden er blevet optaget (skiftet omfang, eller lige
  // for-reserveret) tæller ikke længere med.
  const chosen = seats.filter((s) => selected.has(s.id) && !blocked.has(s.id));

  function changeScope(nextScope, nextScreening) {
    setScope(nextScope);
    setScreeningId(nextScreening);
    setMessage(null);
    setError(null);
  }

  function toggle(seatId) {
    setMessage(null);
    setError(null);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(seatId)) next.delete(seatId);
      else next.add(seatId);
      return next;
    });
  }

  async function submit() {
    if (chosen.length === 0 || needsScreening) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    let done = 0;
    let failure = null;
    // Én ad gangen: stopper ved første afvisning, så admin kan se præcis
    // hvilket sæde der ikke gik igennem (de øvrige står stadig valgt).
    for (const seat of chosen) {
      try {
        await api.holdSeat({
          seat_id: seat.id,
          scope,
          ...(scope === "screening" ? { screening_id: screeningId } : {}),
        });
      } catch (err) {
        failure = err.message;
        break;
      }
      done += 1;
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(seat.id);
        return next;
      });
    }
    // Hent de nye reservationer FØR vinduet frigives igen — ellers står et
    // netop for-reserveret sæde et øjeblik som ledigt og kan vælges igen.
    if (done > 0) {
      try {
        await onChanged();
      } catch {
        // Genindlæsningen er kun visning; holdene er gemt, og backend
        // afviser selv et dobbelt-hold, hvis sædet vælges igen.
      }
      // Holdet står i admins egne "Mine pladser" (BUGS.md #100).
      announceReservationsChanged();
    }
    if (failure) setError(failure);
    else setMessage(t("cinema.holdSuccessCount", { count: done }));
    setBusy(false);
  }

  function renderSeat(seatId, wide) {
    const seat = seats.find((s) => s.id === seatId);
    if (!seat) return null;
    const isBlocked = blocked.has(seatId);
    const isSelected = !isBlocked && selected.has(seatId);
    const state = isBlocked
      ? t("seat.legend.taken")
      : isSelected
        ? t("seat.legend.selected")
        : t("seat.legend.free");
    const cls = isBlocked ? "seat--taken" : isSelected ? "seat--selected" : "seat--free";
    return (
      <button
        key={seatId}
        type="button"
        className={`seat ${cls}${wide ? " seat--wide" : ""}`}
        disabled={busy || isBlocked || needsScreening}
        aria-pressed={isSelected}
        aria-label={`${t("seat.seatLabel", { number: seat.number })} – ${state}`}
        onClick={() => toggle(seatId)}
      >
        {seat.number}
      </button>
    );
  }

  const chosenNumbers = chosen.map((s) => s.number).sort((a, b) => a - b);

  return (
    <div className="seat-modal-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="seat-modal" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          className="seat-modal-close"
          onClick={onClose}
          aria-label={t("common.close")}
        >
          ✕
        </button>
        <header className="seat-modal-header">
          <span className="seat-eyebrow">🎬 Voldby BIO · {t("seat.title")}</span>
          <h2>{t("cinema.holdTitle")}</h2>
          <p className="seat-intro">{t("cinema.holdHint")}</p>
          <div className="cinema-hold-form seat-hold-scope">
            <label>
              {t("cinema.holdScope")}
              <select
                value={scope}
                onChange={(e) =>
                  changeScope(e.target.value, e.target.value === "global" ? "" : screeningId)
                }
              >
                <option value="global">{t("cinema.holdGlobal")}</option>
                <option value="screening">{t("cinema.holdScreening")}</option>
              </select>
            </label>
            {scope === "screening" && (
              <label>
                {t("cinema.holdPickScreening")}
                <select
                  value={screeningId}
                  onChange={(e) => changeScope("screening", e.target.value)}
                >
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
          </div>
        </header>

        <div className="seat-modal-body">
          <SeatRoom renderSeat={renderSeat} />

          <aside className="seat-side">
            <div className="seat-panel">
              <h3>{t("seat.chosen")}</h3>
              <div className="seat-chips">
                {chosenNumbers.length === 0 ? (
                  <span className="muted">
                    {needsScreening ? t("cinema.holdPickScreeningFirst") : t("seat.noneChosen")}
                  </span>
                ) : (
                  chosenNumbers.map((n) => (
                    <span className="seat-chip" key={n}>
                      {t("seat.seatLabel", { number: n })}
                    </span>
                  ))
                )}
              </div>
              <button
                type="button"
                className="btn btn-primary seat-reserve"
                disabled={busy || chosen.length === 0 || needsScreening}
                onClick={submit}
              >
                {busy ? t("cinema.holding") : t("cinema.holdSubmitCount", { count: chosen.length })}
              </button>
              {message && <div className="banner banner-info">{message}</div>}
              {error && <div className="banner banner-error">{error}</div>}
            </div>

            <div className="seat-panel">
              <h3>{t("seat.legendTitle")}</h3>
              <ul className="seat-legend">
                <li>
                  <span className="seat-sw seat-sw--free" aria-hidden="true" />
                  {t("seat.legend.free")}
                </li>
                <li>
                  <span className="seat-sw seat-sw--selected" aria-hidden="true" />
                  {t("seat.legend.selected")}
                </li>
                <li>
                  <span className="seat-sw seat-sw--taken" aria-hidden="true" />
                  {t("seat.legend.taken")}
                </li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
