/**
 * Feature #125 — de rene hjælpere bag besøgs-sektionen. Formatering og
 * oversætter-opslag der ellers kunne gå galt uden at nogen opdager det
 * (regel 19): en forkert dato-slice eller en manglende fallback ville vise
 * brugeren noget forkert i statistikken.
 */

import { describe, expect, it } from "vitest";
import { pageLabel, shortDay } from "./Statistics";

// Fake-oversætter: returnerer nøglen selv, så vi kan se hvilken der blev slået op.
const t = (key) => `T(${key})`;

describe("Statistics besøgs-hjælpere", () => {
  it("shortDay klipper ISO-dato til DD/MM", () => {
    expect(shortDay("2026-08-12")).toBe("12/08");
    expect(shortDay("2026-01-05")).toBe("05/01");
  });

  it("pageLabel oversætter kendte side-nøgler til nav-etiketterne", () => {
    expect(pageLabel(t, "library")).toBe("T(app.nav.movies)");
    expect(pageLabel(t, "tv")).toBe("T(app.nav.tv)");
    expect(pageLabel(t, "stats")).toBe("T(app.nav.stats)");
  });

  it("pageLabel giver /bio sin egen etikette, adskilt fra cinema-fanen", () => {
    expect(pageLabel(t, "bio")).toBe("T(stats.visits.pageBio)");
    expect(pageLabel(t, "cinema")).toBe("T(app.nav.cinema)");
  });

  it("pageLabel falder tilbage til nøglen selv for ukendte sider", () => {
    expect(pageLabel(t, "noget-nyt")).toBe("noget-nyt");
  });
});
