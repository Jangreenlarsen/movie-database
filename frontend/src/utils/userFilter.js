// Feature #234 — søgning og status-filter i brugerstyringen. Ren funktion,
// så den kan testes uden at rendere hele Indstillinger-siden.

export const USER_STATUS_FILTERS = ["all", "pending", "active", "disabled", "rejected"];

function normalize(value) {
  return (value ?? "").toString().trim().toLocaleLowerCase("da-DK");
}

/**
 * Brugere hvis brugernavn, fulde navn eller e-mail indeholder `query`
 * (uden forskel på store/små bogstaver), og hvis status matcher `status`
 * ("all" = alle). En tom eller whitespace-only søgning matcher alle.
 */
export function filterUsers(users, query, status = "all") {
  const needle = normalize(query);
  return users.filter((user) => {
    if (status !== "all" && user.status !== status) return false;
    if (!needle) return true;
    return [user.username, user.full_name, user.email].some((field) => normalize(field).includes(needle));
  });
}

/** Antal brugere pr. status-filter, til tallene på filter-knapperne. */
export function countByStatus(users) {
  const counts = Object.fromEntries(USER_STATUS_FILTERS.map((key) => [key, 0]));
  counts.all = users.length;
  for (const user of users) {
    if (counts[user.status] !== undefined) counts[user.status] += 1;
  }
  return counts;
}
