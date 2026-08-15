/**
 * Feature #154 — oppetids-formateringen bag systemovervågnings-sektionen.
 * En forkert enheds-afrunding eller en glemt null-håndtering ville vise
 * brugeren en forkert eller crashende oppetid uden at nogen opdager det
 * (regel 19).
 */

import { describe, expect, it } from "vitest";
import { formatUptime } from "./Settings";

describe("formatUptime", () => {
  it("viser tankestreg når oppetiden ikke kendes endnu", () => {
    expect(formatUptime(null)).toBe("—");
    expect(formatUptime(undefined)).toBe("—");
  });

  it("viser kun minutter under en time", () => {
    expect(formatUptime(0)).toBe("0m");
    expect(formatUptime(59)).toBe("0m");
    expect(formatUptime(90)).toBe("1m");
  });

  it("viser timer og minutter under et døgn", () => {
    expect(formatUptime(3600)).toBe("1t 0m");
    expect(formatUptime(3660)).toBe("1t 1m");
    expect(formatUptime(86399)).toBe("23t 59m");
  });

  it("viser dage og timer fra et døgn og opefter, uden minutter", () => {
    expect(formatUptime(86400)).toBe("1d 0t");
    expect(formatUptime(90000)).toBe("1d 1t");
    expect(formatUptime(200000)).toBe("2d 7t");
  });
});
