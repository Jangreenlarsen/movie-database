const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${path}`);
  }

  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  health: () => request("/health"),
  listMovies: ({ q, tags } = {}) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (tags?.length) params.set("tags", tags.join(","));
    const query = params.toString();
    return request(`/movies${query ? `?${query}` : ""}`);
  },
  getMovie: (id) => request(`/movies/${id}`),
  createMovie: (payload) =>
    request("/movies", { method: "POST", body: JSON.stringify(payload) }),
  updateMovie: (id, payload) =>
    request(`/movies/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteMovie: (id) => request(`/movies/${id}`, { method: "DELETE" }),
  listTags: () => request("/tags"),
  scanLookup: (barcode) =>
    request("/scan/lookup", { method: "POST", body: JSON.stringify({ barcode }) }),
};
