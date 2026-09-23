// Feature #227 — sendes når en plads er booket eller meldt fra et sted i
// appen (sædevælgeren, admins tilmeldte-liste), så tallet på "Mine pladser"
// i hovedet følger med uden en genindlæsning. Egen fil frem for i
// MyReservations.jsx: en komponent-fil der også eksporterer funktioner,
// bryder Vites fast refresh (oxlint: only-export-components).
export const RESERVATIONS_CHANGED_EVENT = "reservations:changed";

export function announceReservationsChanged() {
  window.dispatchEvent(new Event(RESERVATIONS_CHANGED_EVENT));
}
