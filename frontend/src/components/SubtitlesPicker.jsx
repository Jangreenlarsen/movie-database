import { useEffect, useRef, useState } from "react";
import Chip from "./Chip";
import { useT } from "../i18n";

/**
 * Feature #123 — undertekst-vælger: chips for de faste valg (Eng/DK, leveret
 * via `options` fra attribute-options) plus en "Andet"-chip der åbner et
 * fritekst-felt til alt andet (fx "Fastbrændt DA", "Norsk"). Værdien er en
 * liste af strenge: de faste valg gemmes verbatim ("Eng"/"DK"), og
 * "Andet"-feltets komma-separerede tekst bliver til yderligere liste-poster.
 *
 * Kontrolleret komponent: `value` (liste) er sandheden. "Andet"-feltets åben-
 * tilstand og rå tekst er lokal UI-state, fordi den ikke kan udledes 1:1 af
 * listen (man kan slå "Andet" til før man har skrevet noget). `seedRef` sikrer
 * at vi kun re-seeder den lokale tekst når forælderen skifter til et *andet*
 * objekt (fx en anden film i modalen), ikke ved vores egne emits.
 */
export default function SubtitlesPicker({ value, onChange, options }) {
  const t = useT();
  const std = options && options.length ? options : ["Eng", "DK"];
  const selected = value ?? [];
  const selectedStd = std.filter((o) => selected.includes(o));
  const customList = selected.filter((o) => !std.includes(o));

  const [andetOpen, setAndetOpen] = useState(customList.length > 0);
  const [andetText, setAndetText] = useState(customList.join(", "));
  const seedRef = useRef(selected.join("|"));

  useEffect(() => {
    const key = selected.join("|");
    if (key !== seedRef.current) {
      seedRef.current = key;
      const custom = selected.filter((o) => !std.includes(o));
      setAndetOpen(custom.length > 0);
      setAndetText(custom.join(", "));
    }
    // selected er afledt af value hver render; join'et fanger reelle skift.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected.join("|")]);

  function parseCustom(text) {
    return text
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  function emit(nextStd, open, text) {
    const custom = open ? parseCustom(text) : [];
    const next = [...nextStd, ...custom];
    seedRef.current = next.join("|");
    onChange(next);
  }

  function toggleStd(opt) {
    const nextStd = selectedStd.includes(opt)
      ? selectedStd.filter((o) => o !== opt)
      : [...std.filter((o) => selectedStd.includes(o) || o === opt)];
    emit(nextStd, andetOpen, andetText);
  }

  function toggleAndet() {
    const open = !andetOpen;
    setAndetOpen(open);
    emit(selectedStd, open, andetText);
  }

  function changeAndetText(text) {
    setAndetText(text);
    emit(selectedStd, true, text);
  }

  return (
    <div>
      <div className="chip-row">
        {std.map((opt) => (
          <Chip
            key={opt}
            label={opt}
            active={selectedStd.includes(opt)}
            onClick={() => toggleStd(opt)}
          />
        ))}
        <Chip label={t("subtitles.other")} active={andetOpen} onClick={toggleAndet} />
      </div>
      {andetOpen && (
        <input
          style={{ marginTop: 8 }}
          value={andetText}
          onChange={(e) => changeAndetText(e.target.value)}
          placeholder={t("subtitles.otherPlaceholder")}
        />
      )}
    </div>
  );
}
