/**
 * Feature #143/#153 — poster-cache-omskrivning. Det testværdige (regel 19): en
 * forkert regex ville enten ødelægge ALLE billed-URL'er (broken img) eller slet
 * ikke pege på vores egen cache. Og en manuelt angivet (ikke-TMDb) poster-URL
 * må aldrig røres.
 */

import { describe, expect, it } from "vitest";

import { cardPosterSize, posterSrc } from "./posterUrl";

describe("posterSrc (feature #143/#153)", () => {
  it("omskriver en TMDb-URL til vores egen cache-endpoint i den ønskede størrelse", () => {
    expect(posterSrc("https://image.tmdb.org/t/p/w500/abc123.jpg", "w185")).toBe(
      "/api/posters/w185/abc123.jpg"
    );
    expect(posterSrc("https://image.tmdb.org/t/p/w500/abc123.jpg", "w342")).toBe(
      "/api/posters/w342/abc123.jpg"
    );
  });

  it("bruger w342 som standard", () => {
    expect(posterSrc("https://image.tmdb.org/t/p/w500/x.jpg")).toBe("/api/posters/w342/x.jpg");
  });

  it("bevarer stier med undermapper i TMDb-billedets path", () => {
    expect(posterSrc("https://image.tmdb.org/t/p/w500/nested/abc.jpg", "w185")).toBe(
      "/api/posters/w185/nested/abc.jpg"
    );
  });

  it("rører ikke en ikke-TMDb (manuel) poster-URL", () => {
    const custom = "https://minserver.dk/plakater/film.png";
    expect(posterSrc(custom, "w185")).toBe(custom);
  });

  it("returnerer null/undefined uændret", () => {
    expect(posterSrc(null, "w185")).toBe(null);
    expect(posterSrc(undefined, "w185")).toBe(undefined);
    expect(posterSrc("", "w185")).toBe("");
  });

  it("mapper kortstørrelse til TMDb-bredde (ukendt → w342)", () => {
    expect(cardPosterSize("small")).toBe("w185");
    expect(cardPosterSize("medium")).toBe("w342");
    expect(cardPosterSize("large")).toBe("w500");
    expect(cardPosterSize(undefined)).toBe("w342");
  });
});
