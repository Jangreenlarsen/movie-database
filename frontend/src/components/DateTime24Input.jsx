import DateField from "./DateField";

const HOURS = Array.from({ length: 24 }, (_, h) => String(h).padStart(2, "0"));
const MINUTES = Array.from({ length: 60 }, (_, m) => String(m).padStart(2, "0"));

/**
 * A plain `<input type="datetime-local">`'s time portion renders in
 * whatever 12h/AM-PM-or-24h format the browser/OS locale happens to use —
 * there's no HTML attribute to force 24-hour display, and Jans Windows
 * locale shows AM/PM (2026-08-04, BUGS.md #38). Hour/minute `<select>`s
 * render exactly the labels we write ourselves, so they're 24-hour
 * regardless of locale. `value`/`onChange` speak the same
 * "YYYY-MM-DDTHH:MM" string the API already uses for `scheduled_at`.
 *
 * Lives here rather than in Cinema.jsx (where it started) because feature
 * #85 lets the *requester* suggest a time too — same widget, same string
 * format, so a suggestion drops straight into admins planlægnings-felt.
 */
export default function DateTime24Input({ value, onChange }) {
  const [datePart, timePart] = value ? value.split("T") : ["", ""];
  const [hour, minute] = timePart ? timePart.split(":") : ["", ""];

  function emit(nextDate, nextHour, nextMinute) {
    onChange(nextDate && nextHour && nextMinute ? `${nextDate}T${nextHour}:${nextMinute}` : "");
  }

  return (
    <span className="datetime24-input">
      <DateField value={datePart} onChange={(e) => emit(e.target.value, hour || "00", minute || "00")} />
      <select value={hour} onChange={(e) => emit(datePart, e.target.value, minute || "00")}>
        <option value="" disabled>
          Time
        </option>
        {HOURS.map((h) => (
          <option key={h} value={h}>
            {h}
          </option>
        ))}
      </select>
      <span aria-hidden="true">:</span>
      <select value={minute} onChange={(e) => emit(datePart, hour || "00", e.target.value)}>
        <option value="" disabled>
          Min
        </option>
        {MINUTES.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
    </span>
  );
}
