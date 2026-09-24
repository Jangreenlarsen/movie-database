// Feature #227 — "Mine pladser" og admins "Tilmeldte pr. visning" viser
// begge reservationer samlet pr. visning, ikke én linje pr. sæde: har man
// to sæder til samme film, hører de sammen (og kan meldes fra samlet).
//
// Rækkefølgen følger det første forekomst af hver visning i input — backend
// sorterer allerede /reservations/mine efter visningstidspunkt. Inden for en
// visning sorteres sæderne efter nummer. En reservation uden screening_id
// (et globalt admin-hold) tilhører ingen visning og springes over — medmindre
// `includeGlobal` er sat ("Mine pladser", BUGS.md #100): så samles de i én
// gruppe med `global: true` og screeningId GLOBAL_GROUP_ID.
export const GLOBAL_GROUP_ID = "global";

export function groupReservationsByScreening(reservations, { includeGlobal = false } = {}) {
  const groups = new Map();
  for (const reservation of reservations ?? []) {
    const isGlobal = !reservation.screening_id;
    if (isGlobal && !includeGlobal) continue;
    const screeningId = isGlobal ? GLOBAL_GROUP_ID : reservation.screening_id;
    if (!groups.has(screeningId)) {
      groups.set(screeningId, {
        screeningId,
        global: isGlobal,
        title: isGlobal ? null : reservation.screening_title ?? null,
        at: isGlobal ? null : reservation.screening_at ?? null,
        reservations: [],
      });
    }
    groups.get(screeningId).reservations.push(reservation);
  }
  for (const group of groups.values()) {
    group.reservations.sort((a, b) => a.seat_number - b.seat_number);
  }
  return [...groups.values()];
}

// Sæder 1–14 der ikke allerede er taget på en visning — til admins
// "tilføj tilmeldt"-vælger. Globale hold blokerer sædet på ALLE visninger,
// så de tæller med selvom de ikke hører til `screeningId`.
export function freeSeatNumbers(allSeats, reservations, screeningId) {
  const taken = new Set(
    (reservations ?? [])
      .filter((r) => r.screening_id === screeningId || r.scope === "global")
      .map((r) => r.seat_id)
  );
  return allSeats.filter((seat) => !taken.has(seat.id));
}

// Feature #231 — hvilke sæder kan IKKE for-reserveres? Samme regler som
// backend (`reservation_service.create_hold`): et globalt hold konflikter
// med enhver reservation på sædet; et hold på én visning med visningens egne
// og med globale hold. Afventende tæller med — de er stadig nogens plads.
export function holdBlockedSeatIds(reservations, scope, screeningId) {
  const blocked = new Set();
  for (const r of reservations ?? []) {
    if (scope === "global" || r.scope === "global" || r.screening_id === screeningId) {
      blocked.add(r.seat_id);
    }
  }
  return blocked;
}
