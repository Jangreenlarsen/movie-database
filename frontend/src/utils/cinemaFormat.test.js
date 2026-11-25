/**
 * Feature #233 — server-tidsstempler gemmes i UTC men kommer ud uden
 * tidszone. Læst som lokal tid ville klokkeslættet være forkert.
 */
import { describe, expect, it } from "vitest";

import { formatServerTimestamp, parseServerTimestamp } from "./cinemaFormat";

describe("parseServerTimestamp", () => {
  it("læser en værdi uden tidszone som UTC", () => {
    expect(parseServerTimestamp("2026-11-25T18:30:00").getTime()).toBe(
      Date.UTC(2026, 10, 25, 18, 30, 0)
    );
    expect(parseServerTimestamp("2026-11-25T18:30:00.602000").getTime()).toBe(
      Date.UTC(2026, 10, 25, 18, 30, 0, 602)
    );
  });

  it("bruger en eksplicit tidszone som den er", () => {
    expect(parseServerTimestamp("2026-11-25T18:30:00Z").getTime()).toBe(Date.UTC(2026, 10, 25, 18, 30));
    expect(parseServerTimestamp("2026-11-25T19:30:00+01:00").getTime()).toBe(
      Date.UTC(2026, 10, 25, 18, 30)
    );
  });

  it("giver null for tomt eller ugyldigt", () => {
    expect(parseServerTimestamp(null)).toBeNull();
    expect(parseServerTimestamp("")).toBeNull();
    expect(parseServerTimestamp("ikke en dato")).toBeNull();
    expect(formatServerTimestamp(undefined)).toBeNull();
  });

  it("formaterer med år og 24-timers ur", () => {
    const result = formatServerTimestamp("2026-11-25T18:30:00Z", "da-DK");
    expect(result.date).toMatch(/2026/);
    expect(result.time).toMatch(/^\d{2}[.:]\d{2}$/);
  });
});
