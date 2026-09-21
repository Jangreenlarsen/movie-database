/**
 * BUGS.md #95 — `isIOS()` afgør om `DateField` skal tegne sin egen
 * "Vælg dato"-hjælpetekst. En fejl her rammer enten alle iPhone-brugere
 * (hvis den forkert siger "nej") eller viser hjælpeteksten forkert oven i
 * en allerede-fungerende native placeholder på desktop (hvis den forkert
 * siger "ja") — begge er værd at låse fast (regel 19).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { isIOS } from "./platform";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("isIOS", () => {
  it("genkender en iPhone på dens user-agent", () => {
    vi.stubGlobal("navigator", {
      userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15",
      platform: "iPhone",
      maxTouchPoints: 5,
    });
    expect(isIOS()).toBe(true);
  });

  it("genkender en iPad, selvom dens user-agent udgiver sig for en Mac", () => {
    vi.stubGlobal("navigator", {
      userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15",
      platform: "MacIntel",
      maxTouchPoints: 5,
    });
    expect(isIOS()).toBe(true);
  });

  it("afviser en almindelig desktop-Mac uden touch", () => {
    vi.stubGlobal("navigator", {
      userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15",
      platform: "MacIntel",
      maxTouchPoints: 0,
    });
    expect(isIOS()).toBe(false);
  });

  it("afviser Windows/Android", () => {
    vi.stubGlobal("navigator", {
      userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      platform: "Win32",
      maxTouchPoints: 0,
    });
    expect(isIOS()).toBe(false);
  });
});
