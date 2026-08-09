import { LANGUAGES } from "../i18n";
import "./LanguagePicker.css";

/**
 * Feature #97 — sprogvalget på de skærme der kommer før man er logget ind
 * (login-boksen og den offentlige /bio).
 *
 * Bevidst to knapper frem for en dropdown: der er kun to sprog, og en
 * dropdown ville kræve et klik for overhovedet at afsløre at valget findes.
 * Her kan man se begge muligheder og sit nuværende valg på én gang.
 */
export default function LanguagePicker({ language, onChange }) {
  return (
    <div className="language-picker" role="group" aria-label="Sprog / Language">
      {LANGUAGES.map((option) => (
        <button
          key={option.code}
          type="button"
          className={option.code === language ? "active" : ""}
          aria-pressed={option.code === language}
          onClick={() => onChange(option.code)}
        >
          {option.short}
        </button>
      ))}
    </div>
  );
}
