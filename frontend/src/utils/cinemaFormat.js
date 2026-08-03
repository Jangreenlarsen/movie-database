// Shared by Cinema.jsx (in-app, authenticated tab) and CinemaPublic.jsx
// (feature #70's public /bio page) — both render the same date-grouped
// screening calendar, just with different surrounding chrome/actions.

export function dateKey(iso) {
  return iso.slice(0, 10);
}

export function formatDateHeading(iso) {
  const date = new Date(iso);
  const label = date.toLocaleDateString("da-DK", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function formatTime(iso) {
  return new Date(iso).toLocaleTimeString("da-DK", { hour: "2-digit", minute: "2-digit" });
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
