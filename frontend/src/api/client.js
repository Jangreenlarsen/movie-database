const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

/**
 * BUGS.md #54 — gør backendens fejl læsbar for et menneske.
 *
 * Vores egne `HTTPException`-svar har `detail` som en streng, men FastAPIs
 * indbyggede validering (422) sender en *liste* af `{loc, msg, type}`.
 * Den blev før givet direkte til `new Error(...)`, hvor JavaScript gør
 * arrayet til teksten "[object Object]" — så en bruger der fx skrev sin
 * e-mail som brugernavn fik en uforståelig fejl i stedet for at få at vide
 * hvad der var galt. CLAUDE.md regel 16 kræver netop den specifikke besked.
 *
 * Pydantics "Value error, "-præfiks fjernes: det er en implementeringsdetalje
 * fra valideringslaget, ikke noget der giver mening for den der læser den.
 */
function readableDetail(detail) {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail) || detail.length === 0) return null;
  const messages = detail
    .map((item) => item?.msg)
    .filter(Boolean)
    .map((msg) => msg.replace(/^Value error, /, ""));
  // Flere fejl på én gang samles med punktum-adskiller frem for kun at vise
  // den første — en formular kan sagtens have to felter galt.
  return messages.length > 0 ? messages.join(" · ") : null;
}

// Feature #148 — global "session udløbet"-handler. En 401 midt i en session
// (efter 8 timers idle-timeout) skal føre pænt tilbage til login frem for at
// vise en rå fejl. App.jsx registrerer den (setUser(null)).
let onSessionExpired = null;
export function setOnSessionExpired(handler) {
  onSessionExpired = handler;
}

async function request(path, options = {}) {
  const { headers: extraHeaders, ...rest } = options;
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...extraHeaders },
    credentials: "include",
    ...rest,
  });

  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      // ignore — no JSON body
    }
    // Feature #148 — 401 på et almindeligt endpoint = sessionen er udløbet;
    // nulstil til login. Undtag selve auth-/session-tjekkene, hvor en 401 er en
    // normal "ikke logget ind"-tilstand (og har egen håndtering).
    if (
      response.status === 401 &&
      onSessionExpired &&
      !path.startsWith("/auth") &&
      path !== "/users/me"
    ) {
      onSessionExpired();
    }
    const error = new Error(
      readableDetail(detail) ?? `API request failed: ${response.status} ${path}`
    );
    error.status = response.status;
    throw error;
  }

  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  health: () => request("/health"),
  // Feature #115 — oversigts-tabellen fra FEATURES.md, til Nyheder-fanen.
  getFeatureList: () => request("/system/feature-list"),
  // Feature #97 — `language` er valgfri: den sætter startsproget på den nye
  // konto, så et valg truffet i login-boksen gælder fra første indlogning.
  register: (username, password, language, fullName) =>
    request("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        username,
        password,
        ...(fullName ? { full_name: fullName } : {}),
        ...(language ? { language } : {}),
      }),
    }),
  login: (username, password) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request("/users/me"),
  updateMySettings: (payload) =>
    request("/users/me/settings", { method: "PATCH", body: JSON.stringify(payload) }),
  changeMyPassword: (currentPassword, newPassword) =>
    request("/users/me/password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
  listUsers: () => request("/users"),
  listAuditLog: ({ skip = 0, limit = 50 } = {}) =>
    request(`/audit-log?${new URLSearchParams({ skip, limit })}`),
  updateUserRole: (userId, role) =>
    request(`/users/${userId}/role`, { method: "PATCH", body: JSON.stringify({ role }) }),
  updateUserStatus: (userId, status) =>
    request(`/users/${userId}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  deleteUser: (userId) => request(`/users/${userId}`, { method: "DELETE" }),
  listMovies: (
    {
      q,
      tags,
      format,
      audioTypes,
      mediaTypes,
      sort,
      wishlist,
      watched,
      cast,
      director,
      page,
      pageSize,
      genres,
    } = {}
  ) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (tags?.length) params.set("tags", tags.join(","));
    if (format?.length) params.set("format", format.join(","));
    if (audioTypes?.length) params.set("audio_types", audioTypes.join(","));
    if (mediaTypes?.length) params.set("media_types", mediaTypes.join(","));
    // `sort` is either a ready-made "field:direction,..." string, or an
    // array of { field, direction } levels (up to 3, see Library.jsx).
    const sortParam = Array.isArray(sort)
      ? sort.map((level) => `${level.field}:${level.direction}`).join(",")
      : sort;
    if (sortParam) params.set("sort", sortParam);
    if (wishlist) params.set("wishlist", "true");
    if (watched != null) params.set("watched", String(watched));
    if (cast) params.set("cast", cast);
    if (director) params.set("director", director);
    // Omitting page/pageSize (feature #15) fetches every match, unpaginated
    // — used by Print/Voldby BIO, which need the whole filtered set.
    if (page != null) params.set("page", String(page));
    if (pageSize != null) params.set("page_size", String(pageSize));
    if (genres?.length) params.set("genres", genres.join(","));
    const query = params.toString();
    return request(`/movies${query ? `?${query}` : ""}`);
  },
  getMovie: (id) => request(`/movies/${id}`),
  // BUGS.md #56 — hvem holder et serienummer i samme serie som denne film?
  // Bruges til byt-plads-bekræftelsen før et serienummer ændres.
  getSerialSwapTarget: (id, serialNumber) =>
    request(`/movies/${id}/serial-holder?${new URLSearchParams({ serial_number: serialNumber })}`),
  createMovie: (payload) =>
    request("/movies", { method: "POST", body: JSON.stringify(payload) }),
  updateMovie: (id, payload) =>
    request(`/movies/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteMovie: (id) => request(`/movies/${id}`, { method: "DELETE" }),
  listDeletedMovies: () => request("/movies/deleted"),
  syncMoviesFromTmdb: () => request("/movies/sync-tmdb", { method: "POST" }),
  syncTvShowsFromTmdb: () => request("/tv-shows/sync-tmdb", { method: "POST" }),
  listTags: () => request("/tags"),
  listOwners: () => request("/owners"),
  listLocations: () => request("/locations"),
  attributeOptions: () => request("/movies/attribute-options"),
  listMovieGenres: () => request("/movies/genres"),
  checkDuplicate: (tmdbId) =>
    request(`/movies/check-duplicate?${new URLSearchParams({ tmdb_id: tmdbId })}`),
  getCollection: (collectionId) => request(`/movies/collections/${collectionId}`),
  getStats: () => request("/movies/stats"),
  // Feature #125 — besøgs-statistik. `recordVisit` er fire-and-forget: kaldes
  // med `.catch(() => {})` på kaldstederne, så en fejlet registrering aldrig
  // forstyrrer navigationen. Endpointet er offentligt (også /bio uden login).
  recordVisit: (payload) =>
    request("/analytics/visit", { method: "POST", body: JSON.stringify(payload) }),
  getVisitStats: () => request("/analytics/summary"),
  // Feature #88 — ét kald dækker hele fanens bibliotek. Erstattede den
  // gamle "Tjek Plex"-knap, der lavede ét kald pr. film, manuelt udløst.
  getPlexAvailability: (kind) => request(`/plex/availability?kind=${kind}`),
  refreshPlexAvailability: (kind) => request(`/plex/refresh?kind=${kind}`, { method: "POST" }),
  getPlexDiagnostics: () => request("/plex/diagnostics"),
  // Feature #90 — samme endpoint til forhåndsvisning og udførelse, styret af
  // `dry_run`, så det viste og det udførte ikke kan drive fra hinanden.
  importFromPlex: (payload) =>
    request("/plex/import", { method: "POST", body: JSON.stringify(payload) }),
  getSerialNumberConfig: () => request("/settings/serial-number"),
  updateSerialNumberConfig: (payload) =>
    request("/settings/serial-number", { method: "PATCH", body: JSON.stringify(payload) }),
  scanLookup: (barcode) =>
    request("/scan/lookup", { method: "POST", body: JSON.stringify({ barcode }) }),
  tmdbSearch: (query) =>
    request(`/movies/tmdb-search?${new URLSearchParams({ query })}`),
  movieTmdbPreview: (tmdbId) => request(`/movies/tmdb-preview/${tmdbId}`),
  triggerDeploy: () => request("/system/deploy", { method: "POST" }),
  getDeployStatus: () => request("/system/deploy/status"),
  getSystemSettings: () => request("/settings/system"),
  updateSystemSettings: (payload) =>
    request("/settings/system", { method: "PATCH", body: JSON.stringify(payload) }),
  testSystemSetting: (key) => request(`/settings/system/test/${key}`, { method: "POST" }),
  // Feature #100 — beskeder fra admin.
  // Feature #148 — besked-pollen (hvert 20. sek, #135) markeres som baggrund,
  // så den ikke tæller som aktivitet og holder en uovervåget session i live.
  getInbox: () => request("/messages/inbox", { headers: { "X-Background-Poll": "1" } }),
  markMessageRead: (id) => request(`/messages/${id}/read`, { method: "POST" }),
  listMessages: () => request("/messages"),
  sendMessage: (payload) =>
    request("/messages", { method: "POST", body: JSON.stringify(payload) }),
  deleteMessage: (id) => request(`/messages/${id}`, { method: "DELETE" }),
  // Feature #94 — samlet optælling til app-hovedet.
  getLibraryCounts: () => request("/library/counts"),
  exportLibrary: () => request("/library/export"),
  importLibrary: (payload) =>
    request("/library/import", { method: "POST", body: JSON.stringify(payload) }),
  getSystemBackup: () => request("/system/backup"),
  restoreSystemBackup: (payload) =>
    request("/system/restore", { method: "POST", body: JSON.stringify(payload) }),
  resetDatabase: (currentPassword) =>
    request("/system/reset", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword }),
    }),

  // Systemovervågning (feature #154). `background: true` for det periodiske
  // auto-opdaterings-kald (feature #148 — en åben, uovervåget fane må ikke
  // alene holde en session kunstigt i live).
  getSystemHealth: (background) =>
    request(
      "/system/monitor",
      background ? { headers: { "X-Background-Poll": "1" } } : undefined
    ),
  restartService: () => request("/system/monitor/restart-service", { method: "POST" }),
  rebootServer: (currentPassword) =>
    request("/system/monitor/reboot", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword }),
    }),

  // TLS-certifikat-styring (feature #73)
  getCertStatus: () => request("/system/cert"),
  generateCsr: () => request("/system/cert/csr", { method: "POST" }),
  completeCsr: (certificatePem) =>
    request("/system/cert/csr/complete", {
      method: "POST",
      body: JSON.stringify({ certificate_pem: certificatePem }),
    }),
  importPkcs12: (pkcs12Base64, passphrase) =>
    request("/system/cert/pkcs12", {
      method: "POST",
      body: JSON.stringify({ pkcs12_base64: pkcs12Base64, passphrase }),
    }),
  installCert: (currentPassword) =>
    request("/system/cert/install", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword }),
    }),

  // Voldby BIO (feature #62/#63/#64)
  // `message`/`preferredAt` er feature #85's valgfri ønske-besked og
  // foreslåede tidspunkt. Begge udelades helt af payloaden når de er tomme,
  // så et ønske uden besked ser præcis ud som før #85.
  requestScreening: (mediaKind, id, { message, preferredAt } = {}) =>
    request("/screening-requests", {
      method: "POST",
      body: JSON.stringify({
        ...(mediaKind === "movie"
          ? { media_kind: "movie", movie_id: id }
          : { media_kind: "tv", tv_show_id: id }),
        ...(message?.trim() ? { message: message.trim() } : {}),
        ...(preferredAt ? { preferred_at: preferredAt } : {}),
      }),
    }),
  listScreeningRequests: (status) =>
    request(`/screening-requests${status ? `?status=${status}` : ""}`),
  myScreeningRequests: () => request("/screening-requests/mine"),
  declineScreeningRequest: (id) =>
    request(`/screening-requests/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "declined" }),
    }),
  listScreenings: (upcoming) => request(`/screenings${upcoming ? "?upcoming=true" : ""}`),
  // Feature #130 — afholdte fremvisninger (nyeste først) til biograf-historikken.
  listScreeningHistory: () => request("/screenings?past=true"),
  createScreening: (payload) =>
    request("/screenings", { method: "POST", body: JSON.stringify(payload) }),
  updateScreening: (id, payload) =>
    request(`/screenings/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteScreening: (id) => request(`/screenings/${id}`, { method: "DELETE" }),

  // Feature #133 — sæde-reservation til Voldby BIO.
  getSeatMap: (screeningId) => request(`/screenings/${screeningId}/seats`),
  reserveSeats: (screeningId, seatIds) =>
    request(`/screenings/${screeningId}/reservations`, {
      method: "POST",
      body: JSON.stringify({ seat_ids: seatIds }),
    }),
  listReservations: ({ status, screeningId } = {}) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (screeningId) params.set("screening_id", screeningId);
    const query = params.toString();
    return request(`/reservations${query ? `?${query}` : ""}`);
  },
  myReservations: () => request("/reservations/mine"),
  approveReservation: (id) =>
    request(`/reservations/${id}/approve`, { method: "POST" }),
  cancelReservation: (id) => request(`/reservations/${id}`, { method: "DELETE" }),
  holdSeat: (payload) =>
    request("/reservations/hold", { method: "POST", body: JSON.stringify(payload) }),

  // TV-serier (feature #47) — egen ressource, samme kontrakt-form som film.
  listTvShows: (
    { q, tags, format, audioTypes, mediaTypes, sort, wishlist, watched, page, pageSize, genres } = {}
  ) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (tags?.length) params.set("tags", tags.join(","));
    if (format?.length) params.set("format", format.join(","));
    if (audioTypes?.length) params.set("audio_types", audioTypes.join(","));
    if (mediaTypes?.length) params.set("media_types", mediaTypes.join(","));
    const sortParam = Array.isArray(sort)
      ? sort.map((level) => `${level.field}:${level.direction}`).join(",")
      : sort;
    if (sortParam) params.set("sort", sortParam);
    if (wishlist) params.set("wishlist", "true");
    if (watched != null) params.set("watched", String(watched));
    if (page != null) params.set("page", String(page));
    if (pageSize != null) params.set("page_size", String(pageSize));
    if (genres?.length) params.set("genres", genres.join(","));
    const query = params.toString();
    return request(`/tv-shows${query ? `?${query}` : ""}`);
  },
  getTvShow: (id) => request(`/tv-shows/${id}`),
  createTvShow: (payload) =>
    request("/tv-shows", { method: "POST", body: JSON.stringify(payload) }),
  updateTvShow: (id, payload) =>
    request(`/tv-shows/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTvShow: (id) => request(`/tv-shows/${id}`, { method: "DELETE" }),
  listDeletedTvShows: () => request("/tv-shows/deleted"),
  tvAttributeOptions: () => request("/tv-shows/attribute-options"),
  listTvGenres: () => request("/tv-shows/genres"),
  checkTvDuplicate: (tmdbId) =>
    request(`/tv-shows/check-duplicate?${new URLSearchParams({ tmdb_id: tmdbId })}`),
  tvTmdbSearch: (query) =>
    request(`/tv-shows/tmdb-search?${new URLSearchParams({ query })}`),
  tvTmdbPreview: (tmdbId) => request(`/tv-shows/tmdb-preview/${tmdbId}`),
  tvTmdbFullPreview: (tmdbId) => request(`/tv-shows/tmdb-full-preview/${tmdbId}`),
  setSeasonOwned: (tvShowId, seasonNumber, owned) =>
    request(`/tv-shows/${tvShowId}/seasons/${seasonNumber}`, {
      method: "PATCH",
      body: JSON.stringify({ owned }),
    }),
  setEpisodeWatched: (tvShowId, seasonNumber, episodeNumber, watched, watchedAt) =>
    request(`/tv-shows/${tvShowId}/seasons/${seasonNumber}/episodes/${episodeNumber}`, {
      method: "PATCH",
      body: JSON.stringify({ watched, watched_at: watchedAt }),
    }),
};
