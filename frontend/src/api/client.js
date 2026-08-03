const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...options,
  });

  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      // ignore — no JSON body
    }
    const error = new Error(detail ?? `API request failed: ${response.status} ${path}`);
    error.status = response.status;
    throw error;
  }

  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  health: () => request("/health"),
  register: (username, password) =>
    request("/auth/register", { method: "POST", body: JSON.stringify({ username, password }) }),
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
  updateUserRole: (userId, role) =>
    request(`/users/${userId}/role`, { method: "PATCH", body: JSON.stringify({ role }) }),
  listMovies: (
    { q, tags, format, audioTypes, mediaTypes, sort, wishlist, watched, cast, director } = {}
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
    const query = params.toString();
    return request(`/movies${query ? `?${query}` : ""}`);
  },
  getMovie: (id) => request(`/movies/${id}`),
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
  checkDuplicate: (tmdbId) =>
    request(`/movies/check-duplicate?${new URLSearchParams({ tmdb_id: tmdbId })}`),
  getCollection: (collectionId) => request(`/movies/collections/${collectionId}`),
  getStats: () => request("/movies/stats"),
  getPlexAvailability: (movieId) => request(`/movies/${movieId}/plex`),
  getSerialNumberConfig: () => request("/settings/serial-number"),
  updateSerialNumberConfig: (payload) =>
    request("/settings/serial-number", { method: "PATCH", body: JSON.stringify(payload) }),
  scanLookup: (barcode) =>
    request("/scan/lookup", { method: "POST", body: JSON.stringify({ barcode }) }),
  tmdbSearch: (query) =>
    request(`/movies/tmdb-search?${new URLSearchParams({ query })}`),
  triggerDeploy: () => request("/system/deploy", { method: "POST" }),
  getSystemSettings: () => request("/settings/system"),
  updateSystemSettings: (payload) =>
    request("/settings/system", { method: "PATCH", body: JSON.stringify(payload) }),
  exportLibrary: () => request("/library/export"),
  importLibrary: (payload) =>
    request("/library/import", { method: "POST", body: JSON.stringify(payload) }),
  getSystemBackup: () => request("/system/backup"),
  restoreSystemBackup: (payload) =>
    request("/system/restore", { method: "POST", body: JSON.stringify(payload) }),

  // Voldby BIO (feature #62/#63/#64)
  requestScreening: (mediaKind, id) =>
    request("/screening-requests", {
      method: "POST",
      body: JSON.stringify(
        mediaKind === "movie" ? { media_kind: "movie", movie_id: id } : { media_kind: "tv", tv_show_id: id }
      ),
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
  createScreening: (payload) =>
    request("/screenings", { method: "POST", body: JSON.stringify(payload) }),
  updateScreening: (id, payload) =>
    request(`/screenings/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteScreening: (id) => request(`/screenings/${id}`, { method: "DELETE" }),

  // TV-serier (feature #47) — egen ressource, samme kontrakt-form som film.
  listTvShows: ({ q, tags, format, audioTypes, mediaTypes, sort, wishlist, watched } = {}) => {
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
  checkTvDuplicate: (tmdbId) =>
    request(`/tv-shows/check-duplicate?${new URLSearchParams({ tmdb_id: tmdbId })}`),
  tvTmdbSearch: (query) =>
    request(`/tv-shows/tmdb-search?${new URLSearchParams({ query })}`),
  tvTmdbPreview: (tmdbId) => request(`/tv-shows/tmdb-preview/${tmdbId}`),
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
