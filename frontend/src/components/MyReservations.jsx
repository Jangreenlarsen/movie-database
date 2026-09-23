import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api/client";
import { useLocale, useT } from "../i18n";
import { formatDateHeading, formatTime } from "../utils/cinemaFormat";
import { groupReservationsByScreening } from "../utils/reservationGroups";
import {
  RESERVATIONS_CHANGED_EVENT,
  announceReservationsChanged,
} from "../utils/reservationEvents";
import "./MyReservations.css";

/**
 * Feature #227 — "Mine pladser": knap i hovedet (ved siden af Log ud) med et
 * tal for antal kommende pladser, og et vindue hvor man kan melde fra.
 * For alle roller — også gæster, der jo kan booke.
 */
export default function MyReservationsButton() {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(0);

  const refreshCount = useCallback(() => {
    api
      .myReservations()
      .then((rows) => setCount(rows.length))
      // Tallet er en bekvemmelighed i hovedet; fejler hentningen, vises
      // bare intet tal. Selve vinduet viser fejlen, hvis man åbner det.
      .catch(() => setCount(0));
  }, []);

  useEffect(() => {
    refreshCount();
    window.addEventListener(RESERVATIONS_CHANGED_EVENT, refreshCount);
    return () => window.removeEventListener(RESERVATIONS_CHANGED_EVENT, refreshCount);
  }, [refreshCount]);

  // Stabil identitet: vinduets `load` afhænger af den, så en ny inline-
  // funktion ved hver render ville hente listen igen i en uendelig løkke.
  const handleChanged = useCallback((rows) => setCount(rows.length), []);
  const handleClose = useCallback(() => setOpen(false), []);

  const label =
    count > 0 ? t("myReservations.buttonAria", { count }) : t("myReservations.button");

  return (
    <>
      <button
        type="button"
        className="btn header-my-seats"
        onClick={() => setOpen(true)}
        title={t("myReservations.button")}
        aria-label={label}
      >
        <span aria-hidden="true">🎟️</span>
        <span className="header-btn-label">{t("myReservations.button")}</span>
        {count > 0 && (
          <span className="header-my-seats-badge" aria-hidden="true">
            {count}
          </span>
        )}
      </button>
      {/* Portal til <body>: knappen bor i .app-header, hvis `backdrop-filter`
          gør hovedet til containing block for `position: fixed` — uden
          portalen blev vinduet klippet til hovedets egen højde (fundet ved
          visuel verifikation, regel 18; build/lint/tests så det ikke). */}
      {open &&
        createPortal(
          <MyReservationsModal onClose={handleClose} onChanged={handleChanged} />,
          document.body
        )}
    </>
  );
}

export function MyReservationsModal({ onClose, onChanged }) {
  const t = useT();
  const locale = useLocale();
  const [status, setStatus] = useState("loading");
  const [reservations, setReservations] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const rows = await api.myReservations();
      setReservations(rows);
      setStatus("ready");
      onChanged?.(rows);
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, [onChanged]);

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

  async function cancel(rows, busyKey, confirmText) {
    if (!window.confirm(confirmText)) return;
    setBusyId(busyKey);
    setError(null);
    try {
      // Én ad gangen: stopper ved første fejl, så brugeren kan se præcis
      // hvilken plads der ikke blev meldt fra (resten står stadig i listen
      // efter genindlæsningen nedenfor).
      for (const reservation of rows) {
        await api.cancelReservation(reservation.id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
      await load();
      announceReservationsChanged();
    }
  }

  const groups = groupReservationsByScreening(reservations);

  return (
    <div className="my-seats-overlay" role="presentation" onClick={onClose}>
      <div
        className="my-seats-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="my-seats-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="my-seats-header">
          <div>
            <span className="my-seats-eyebrow">🎬 Voldby BIO</span>
            <h2 id="my-seats-title">{t("myReservations.title")}</h2>
            <p className="muted">{t("myReservations.intro")}</p>
          </div>
          <button
            type="button"
            className="btn my-seats-close"
            onClick={onClose}
            aria-label={t("common.close")}
          >
            ✕
          </button>
        </header>

        {error && <div className="banner banner-error">{error}</div>}
        {status === "loading" && <p className="muted">{t("common.loading")}</p>}
        {status === "ready" && groups.length === 0 && (
          <p className="my-seats-empty muted">{t("myReservations.empty")}</p>
        )}

        <div className="my-seats-groups">
          {groups.map((group) => {
            const title = group.title ?? t("cinema.unknownTitle");
            return (
              <section className="my-seats-group" key={group.screeningId}>
                <div className="my-seats-group-head">
                  <strong>{title}</strong>
                  {group.at && (
                    <span className="muted">
                      {formatDateHeading(group.at, locale)} · {formatTime(group.at, locale)}
                    </span>
                  )}
                  <span className="my-seats-group-count muted">
                    {t("myReservations.seatCount", { count: group.reservations.length })}
                  </span>
                </div>

                {group.reservations.map((reservation) => (
                  <div className="my-seats-row" key={reservation.id}>
                    <span className="my-seats-number" aria-hidden="true">
                      {reservation.seat_number}
                    </span>
                    <span className="my-seats-label">
                      {t("seat.seatLabel", { number: reservation.seat_number })}
                    </span>
                    <span
                      className={`my-seats-pill ${
                        reservation.status === "approved"
                          ? "my-seats-pill--approved"
                          : "my-seats-pill--pending"
                      }`}
                    >
                      {t(
                        reservation.status === "approved"
                          ? "myReservations.approved"
                          : "myReservations.pending"
                      )}
                    </span>
                    <button
                      type="button"
                      className="btn my-seats-cancel"
                      disabled={busyId !== null}
                      onClick={() =>
                        cancel(
                          [reservation],
                          reservation.id,
                          t("myReservations.confirmOne", {
                            number: reservation.seat_number,
                            title,
                          })
                        )
                      }
                    >
                      {busyId === reservation.id
                        ? t("myReservations.cancelling")
                        : t("myReservations.cancel")}
                    </button>
                  </div>
                ))}

                {group.reservations.length > 1 && (
                  <div className="my-seats-group-foot">
                    <button
                      type="button"
                      className="btn my-seats-cancel-all"
                      disabled={busyId !== null}
                      onClick={() =>
                        cancel(
                          group.reservations,
                          group.screeningId,
                          t("myReservations.confirmAll", {
                            count: group.reservations.length,
                            title,
                          })
                        )
                      }
                    >
                      {busyId === group.screeningId
                        ? t("myReservations.cancelling")
                        : t("myReservations.cancelAll", { count: group.reservations.length })}
                    </button>
                  </div>
                )}
              </section>
            );
          })}
        </div>

        {status === "ready" && groups.length > 0 && (
          <p className="my-seats-footnote muted">{t("myReservations.footnote")}</p>
        )}
      </div>
    </div>
  );
}
