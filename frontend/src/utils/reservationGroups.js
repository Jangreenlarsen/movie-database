// Feature #227 — "Mine pladser" og admins "Tilmeldte pr. visning" viser
// begge reservationer samlet pr. visning, ikke én linje pr. sæde: har man
// to sæder til samme film, hører de sammen (og kan meldes fra samlet).
//
// Rækkefølgen følger det første forekomst af hver visning i input — backend
// sorterer allerede /reservations/mine efter visningstidspunkt. Inden for en
// visning sorteres sæderne efter nummer. En reservation uden screening_id
// (et globalt admin-hold) tilhører ingen visning og springes over.
export function groupReservationsByScreening(reservations) {
  const groups = new Map();
  for (const reservation of reservations ?? []) {
    const screeningId = reservation.screening_id;
    if (!screeningId) continue;
    if (!groups.has(screeningId)) {
      groups.set(screeningId, {
        screeningId,
        title: reservation.screening_title ?? null,
        at: reservation.screening_at ?? null,
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
