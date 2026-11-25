// Shared by Cinema.jsx (in-app, authenticated tab) and CinemaPublic.jsx
// (feature #70's public /bio page) — both render the same date-grouped
// screening calendar, just with different surrounding chrome/actions.

export function dateKey(iso) {
  return iso.slice(0, 10);
}

// Feature #89 — locale er en parameter, ikke et hook-opslag: disse er rene
// funktioner, ikke komponenter. Standarden er dansk, fordi den offentlige
// /bio-side kalder dem uden en indlogget bruger at læse sproget fra.
export function formatDateHeading(iso, locale = "da-DK") {
  const date = new Date(iso);
  const label = date.toLocaleDateString(locale, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function formatTime(iso, locale = "da-DK") {
  // hour12: false — 24-timers ur uanset sprog. en-GB ville ellers give
  // AM/PM på nogle platforme, og hele appen (inkl. DateTime24Input) regner
  // med 24-timers format.
  return new Date(iso).toLocaleTimeString(locale, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

// Compact "1. sep" form — used on the public /bio page's poster-grid cards
// (feature #70 v2), which show every upcoming screening side by side in one
// flat grid instead of grouped under a full per-day heading.
export function formatShortDate(iso, locale = "da-DK") {
  return new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "short" });
}

// Feature #233 — backendens egne tidsstempler (fx `requested_at`) gemmes i
// UTC, men kommer ud af MongoDB uden tidszone ("2026-11-25T21:32:27").
// `new Date()` ville læse dem som lokal tid og vise klokkeslættet en time
// (sommertid: to) forkert. En værdi UDEN tidszone læses derfor som UTC; en
// værdi med "Z" eller "+01:00" bruges som den er.
const HAS_TIMEZONE = /(?:Z|[+-]\d{2}:?\d{2})$/i;

export function parseServerTimestamp(iso) {
  if (!iso) return null;
  const date = new Date(HAS_TIMEZONE.test(iso) ? iso : `${iso}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

// Feature #233 — "24. nov. 2026" + "19:30" for et server-tidsstempel. Med
// år, fordi en anmodning kan være mange måneder gammel.
export function formatServerTimestamp(iso, locale = "da-DK") {
  const date = parseServerTimestamp(iso);
  if (!date) return null;
  return {
    date: date.toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" }),
    time: date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", hour12: false }),
  };
}

export function groupByDate(screenings) {
  const groups = [];
  let currentKey = null;
  for (const screening of screenings) {
    const key = dateKey(screening.scheduled_at);
    if (key !== currentKey) {
      groups.push({ key, date: screening.scheduled_at, screenings: [] });
      currentKey = key;
    }
    groups[groups.length - 1].screenings.push(screening);
  }
  return groups;
}
