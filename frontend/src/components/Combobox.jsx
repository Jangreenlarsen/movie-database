import { useEffect, useRef, useState } from "react";
import "./Combobox.css";

/**
 * Text input with a suggestion dropdown of values already in use, while
 * still allowing free typing of a brand new value (feature #58). Built as
 * a plain, self-contained dropdown instead of native `<datalist>` — iOS
 * Safari's `<datalist>` support is historically weak/inconsistent, and this
 * app's primary use case is an installed iPhone PWA, so the suggestion list
 * must actually work there. Closes on outside click/tap rather than
 * `onBlur`, so a tap on a suggestion always registers instead of racing a
 * blur-triggered close.
 */
export default function Combobox({ id, value, onChange, options, placeholder, style }) {
  const [open, setOpen] = useState(false);
  // Focusing a field that already has a value (e.g. re-opening an existing
  // movie's "Ejer" field) should show the *full* suggestion list first —
  // filtering it by whatever's already there would usually show nothing
  // useful. Filtering only kicks in once the user actively types.
  const [filterActive, setFilterActive] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    function handleOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("touchstart", handleOutside);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("touchstart", handleOutside);
    };
  }, []);

  const query = value.trim().toLowerCase();
  const filtered = (
    filterActive && query ? options.filter((o) => o.toLowerCase().includes(query)) : options
  ).slice(0, 8);
  const nothingLeftToPick = filtered.length === 1 && filtered[0].toLowerCase() === query;
  const showMenu = open && filtered.length > 0 && !nothingLeftToPick;

  return (
    <div className="combobox" ref={containerRef}>
      <input
        id={id}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
          setFilterActive(true);
        }}
        onFocus={() => {
          setOpen(true);
          setFilterActive(false);
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
        }}
        placeholder={placeholder}
        style={style}
        autoComplete="off"
      />
      {showMenu && (
        <ul className="combobox-menu">
          {filtered.map((option) => (
            <li key={option}>
              <button
                type="button"
                className="combobox-option"
                onClick={() => {
                  onChange(option);
                  setOpen(false);
                }}
              >
                {option}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
