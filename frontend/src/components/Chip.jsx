// Feature #156 — `negated` er filtrets tredje tilstand ("må ikke have
// denne"), adskilt fra `active` ("skal have denne") frem for at overloade
// samme boolean, så en fremtidig fjerde tilstand ikke skal genfortolke et
// eksisterende felt.
export default function Chip({ label, active, negated, onClick }) {
  const stateClass = negated ? " chip-negated" : active ? " chip-active" : "";
  return (
    <button
      type="button"
      className={`chip${stateClass}`}
      onClick={onClick}
      aria-pressed={Boolean(active || negated)}
    >
      {label}
    </button>
  );
}
