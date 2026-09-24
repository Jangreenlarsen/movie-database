import { useT } from "../i18n";
import "./SeatSelectionModal.css";

// Feature #133 — salens layout (sofa-fløje, rækker, lærred, dør). Ren
// præsentation: nummereringen 1–14 og hvert sædes tilstand kommer fra
// kalderen via `renderSeat`. Feature #231 — trukket ud af SeatSelectionModal,
// så admins for-reservér-vindue viser præcis samme sal.
const SEAT_LAYOUT = [
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

/** `renderSeat(seatId, wide)` → knappen for ét sæde (wide = sofa-plads). */
export default function SeatRoom({ renderSeat }) {
  const t = useT();
  return (
    <div className="seat-room" role="group" aria-label={t("seat.roomAria")}>
      <div className="seat-screen">
        <div className="seat-screen-bar" aria-hidden="true" />
        <span className="seat-screen-label">{t("seat.screen")}</span>
      </div>
      <div className="seat-gap" aria-hidden="true" />

      {SEAT_LAYOUT.map((row, i) =>
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
  );
}
