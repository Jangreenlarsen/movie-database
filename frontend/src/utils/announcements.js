// Feature #228 — "Samlet opdatering". Egen fil frem for i komponenterne:
// en komponent-fil der også eksporterer konstanter/funktioner, bryder Vites
// fast refresh (oxlint: only-export-components).

// Standardvalget ved tilføjelse: læg titlen i den samlede opdatering.
export const DEFAULT_ANNOUNCE = "queue";

// Sendes når køen kan have ændret sig (en titel lagt i kø, fjernet eller
// sendt), så påmindelsen på Film/TV-siden følger med uden genindlæsning.
export const ANNOUNCEMENTS_CHANGED_EVENT = "announcements:changed";

export function announceQueueChanged() {
  window.dispatchEvent(new Event(ANNOUNCEMENTS_CHANGED_EVENT));
}
