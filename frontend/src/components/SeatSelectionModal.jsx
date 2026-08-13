import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useT } from "../i18n";
import "./SeatSelectionModal.css";

// Feature #133 — sæde-vælgeren. Selve salens layout (sofa-fløje, rækker, dør)
// er ren præsentation og bor her i frontend; backend leverer kun hvert sædes
// tilstand (free/mine/pending/taken) via GET /api/screenings/{id}/seats.
// Nummereringen 1–14 og tilstandene kommer fra sædekortet, ikke fra dette array.
const LAYOUT = [
  {
    kind: "sofa",
    units: [
      { pos: "left", seatIds: ["N1-1"] },
      { pos: "mid", seatIds: ["N1-2", "N1-3"] },
      { pos: "right", seatIds: ["N1-4"] },
    ],
  },
  { kind: "chairs", seatIds: ["N2-1", "N2-2", "N2-3", "N2-4", "N2-5"] },
  { kind: "chairs", seatIds: ["N3-1", "N3-2", "N3-3", "N3-4", "N3-5"] },
];

export default function SeatSelectionModal({ screeningId, screeningTitle, onClose }) {
  const t = useT();
  const [status, setStatus] = useState("loading");
  const [seats, setSeats] = useState([]);
  const [selected, setSelected] = useState(() => new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await api.getSeatMap(screeningId);
      setSeats(data.seats);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, [screeningId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const byId = new Map(seats.map((s) => [s.seat_id, s]));

  function toggleSeat(seat) {
    setError(null);
    setMessage(null);
    if (seat.status === "free") {
      setSelected((prev) => {
        const next = new Set(prev);
        if (next.has(seat.seat_id)) next.delete(seat.seat_id);
        else next.add(seat.seat_id);
        return next;
      });
    } else if (seat.status === "mine") {
      cancelMine(seat);
    }
  }

  async function cancelMine(seat) {
    if (!seat.reservation_id) return;
    if (!window.confirm(t("seat.cancelConfirm", { number: seat.number }))) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.cancelReservation(seat.reservation_id);
      await load();
    } catch (err) {
      // Vis den specifikke backend-fejl (CLAUDE.md regel 16).
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function reserve() {
    if (selected.size === 0) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.reserveSeats(screeningId, [...selected]);
      setSelected(new Set());
      await load();
      setMessage(t("seat.reserveSuccess"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function seatClass(seat) {
    if (selected.has(seat.seat_id)) return "seat seat--selected";
    if (seat.status === "mine") return `seat seat--mine${seat.approved ? " seat--approved" : ""}`;
    if (seat.status === "taken") return "seat seat--taken";
    if (seat.status === "pending") return "seat seat--pending";
    return "seat seat--free";
  }

  function seatStateText(seat) {
    if (selected.has(seat.seat_id)) return t("seat.legend.selected");
    if (seat.status === "mine") return t(seat.approved ? "seat.mineApproved" : "seat.minePending");
    if (seat.status === "taken") return t("seat.legend.taken");
    if (seat.status === "pending") return t("seat.legend.pending");
    return t("seat.legend.free");
  }

  function renderSeat(seatId, wide) {
    const seat = byId.get(seatId);
    if (!seat) return null;
    const disabled = busy || seat.status === "taken" || seat.status === "pending";
    return (
      <button
        key={seatId}
        type="button"
        className={seatClass(seat) + (wide ? " seat--wide" : "")}
        disabled={disabled}
        aria-pressed={selected.has(seatId)}
        aria-label={`${t("seat.seatLabel", { number: seat.number })} – ${seatStateText(seat)}`}
        onClick={() => toggleSeat(seat)}
      >
        {seat.number}
      </button>
    );
  }

  const selectedNumbers = [...selected]
    .map((id) => byId.get(id)?.number)
    .filter((n) => n != null)
    .sort((a, b) => a - b);

  return (
    <div className="seat-modal-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="seat-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="seat-modal-close" onClick={onClose} aria-label={t("common.close")}>
          ✕
        </button>
        <header className="seat-modal-header">
          <span className="seat-eyebrow">🎬 Voldby BIO · {t("seat.title")}</span>
          {screeningTitle && <h2>{screeningTitle}</h2>}
          <p className="seat-intro">{t("seat.intro")}</p>
        </header>

        {status === "loading" && <p className="muted">{t("common.loading")}</p>}
        {status === "error" && <div className="banner banner-error">{t("seat.loadError")}</div>}

        {status === "ready" && (
          <div className="seat-modal-body">
            <div className="seat-room" role="group" aria-label={t("seat.roomAria")}>
              <div className="seat-screen">
                <div className="seat-screen-bar" aria-hidden="true" />
                <span className="seat-screen-label">{t("seat.screen")}</span>
              </div>
              <div className="seat-gap" aria-hidden="true" />

              {LAYOUT.map((row, i) =>
                row.kind === "sofa" ? (
                  <div className="seat-row" key={i}>
                    <div className="seat-sofa">
                      {row.units.map((u) => (
                        <div className={`seat-sofa-unit seat-sofa-unit--${u.pos}`} key={u.pos}>
                          {u.seatIds.map((id) => renderSeat(id, true))}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="seat-row" key={i}>
                    <div className="seat-chairs">{row.seatIds.map((id) => renderSeat(id, false))}</div>
                  </div>
                )
              )}

              <div className="seat-door" aria-label={t("seat.door")}>
                {t("seat.door")}
              </div>
            </div>

            <aside className="seat-side">
              <div className="seat-panel">
                <h3>{t("seat.chosen")}</h3>
                <div className="seat-chips">
                  {selectedNumbers.length === 0 ? (
                    <span className="muted">{t("seat.noneChosen")}</span>
                  ) : (
                    selectedNumbers.map((n) => (
                      <span className="seat-chip" key={n}>
                        {t("seat.seatLabel", { number: n })}
                      </span>
                    ))
                  )}
                </div>
                <button
                  type="button"
                  className="btn btn-primary seat-reserve"
                  disabled={busy || selected.size === 0}
                  onClick={reserve}
                >
                  {busy ? t("seat.reserving") : t("seat.reserveCount", { count: selected.size })}
                </button>
                <p className="seat-hint">{t("seat.hint")}</p>
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
                  <li>
                    <span className="seat-sw seat-sw--mine" aria-hidden="true" />
                    {t("seat.legend.mine")}
                  </li>
                </ul>
              </div>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
