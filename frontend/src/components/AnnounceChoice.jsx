import { useT } from "../i18n";
import "./AnnounceChoice.css";

// Feature #228 — erstatter #222's ene flueben ("Send besked til alle") med
// tre valg. Standarden er den samlede opdatering (DEFAULT_ANNOUNCE i
// utils/announcements.js), så ti film registreret på en aften ikke længere
// giver ti beskeder til alle. Værdierne matcher backendens `announce`.
const ANNOUNCE_OPTIONS = ["queue", "now", "none"];

/**
 * `isMove` = titlen flyttes ind fra ønskelisten (i stedet for at blive
 * oprettet direkte i biblioteket) — kun overskriften skifter ordlyd.
 */
export default function AnnounceChoice({ value, onChange, isMove = false, name = "announce" }) {
  const t = useT();
  return (
    <fieldset className="announce-choice">
      <legend>{t(isMove ? "announce.legendMove" : "announce.legendCreate")}</legend>
      {ANNOUNCE_OPTIONS.map((option) => (
        <label key={option} className="announce-choice-option">
          <input
            type="radio"
            name={name}
            value={option}
            checked={value === option}
            onChange={() => onChange(option)}
          />
          <span>
            {t(`announce.option.${option}`)}
            <span className="announce-choice-hint">{t(`announce.hint.${option}`)}</span>
          </span>
        </label>
      ))}
    </fieldset>
  );
}
