/**
 * Feature #156 — filter-badges' 3-trins cyklus (neutral → inkludér →
 * ekskludér → neutral). Delt af Library.jsx og TvShows.jsx; en fejl her
 * rammer begge sider på én gang uden at nogen ser det før et badge opfører
 * sig forkert midt i en session (regel 19).
 */

import { describe, expect, it } from "vitest";
import { cycleFilterValue, cycleTriState, EMPTY_FILTER_STATE } from "./filterCycle";

describe("cycleFilterValue", () => {
  it("går fra neutral til inkluderet ved første klik", () => {
    const next = cycleFilterValue(EMPTY_FILTER_STATE, "Julefilm");
    expect(next).toEqual({ included: ["Julefilm"], excluded: [] });
  });

  it("går fra inkluderet til ekskluderet ved andet klik", () => {
    const state = { included: ["Julefilm"], excluded: [] };
    const next = cycleFilterValue(state, "Julefilm");
    expect(next).toEqual({ included: [], excluded: ["Julefilm"] });
  });

  it("går fra ekskluderet tilbage til neutral ved tredje klik", () => {
    const state = { included: [], excluded: ["Julefilm"] };
    const next = cycleFilterValue(state, "Julefilm");
    expect(next).toEqual({ included: [], excluded: [] });
  });

  it("rører ikke andre værdier i samme filter", () => {
    const state = { included: ["Julefilm", "4K"], excluded: ["Gyser"] };
    const next = cycleFilterValue(state, "Julefilm");
    expect(next).toEqual({ included: ["4K"], excluded: ["Gyser", "Julefilm"] });
  });

  it("muterer aldrig input-state (bruges direkte i setState-opdateringer)", () => {
    const state = { included: ["Julefilm"], excluded: [] };
    cycleFilterValue(state, "Julefilm");
    expect(state).toEqual({ included: ["Julefilm"], excluded: [] });
  });
});

describe("cycleTriState", () => {
  it("går null → true → false → null", () => {
    expect(cycleTriState(null)).toBe(true);
    expect(cycleTriState(true)).toBe(false);
    expect(cycleTriState(false)).toBe(null);
  });
});
