import { useT } from "../i18n";
import { isIOS } from "../utils/platform";
import "./DateField.css";

/**
 * Thin wrapper around `<input type="date">` (BUGS.md #95). iOS Safari
 * renders an EMPTY date input completely blank — no "dd-mm-åååå" digits, no
 * calendar icon, unlike every other engine — so nothing tells a first-time
 * user the box is tappable. Draws a plain-text hint on top in that one case;
 * `pointer-events: none` on the hint lets the tap fall straight through to
 * the native input underneath, which still opens the OS picker.
 */
export default function DateField({ value, onChange, className }) {
  const t = useT();
  return (
    <span className={className ? `date-field ${className}` : "date-field"}>
      <input type="date" value={value} onChange={onChange} />
      {isIOS() && !value && (
        <span className="date-field-hint" aria-hidden="true">
          {t("common.pickDate")}
        </span>
      )}
    </span>
  );
}
