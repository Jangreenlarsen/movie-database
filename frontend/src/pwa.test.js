/**
 * Feature #190 — PWA'en skal selv tjekke periodisk for en ny version, i
 * stedet for kun at stole på browserens tjek ved en rigtig sideindlæsning
 * (Jan: "hvordan sikker vi os også at folk ikke sider med cache version af
 * site"). Det testværdige: `registerServiceWorker` skal rent faktisk sætte
 * et periodisk `registration.update()`-kald op via `onRegisteredSW`, ikke
 * bare registrere og stoppe der.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const registerSWMock = vi.fn();
vi.mock("virtual:pwa-register", () => ({
  registerSW: (...args) => registerSWMock(...args),
}));

describe("registerServiceWorker (feature #190)", () => {
  beforeEach(() => {
    registerSWMock.mockClear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("registrerer med immediate:true og sætter et periodisk update()-tjek op", async () => {
    const { registerServiceWorker } = await import("./pwa.js");
    registerServiceWorker();

    expect(registerSWMock).toHaveBeenCalledTimes(1);
    const options = registerSWMock.mock.calls[0][0];
    expect(options.immediate).toBe(true);
    expect(typeof options.onRegisteredSW).toBe("function");

    const update = vi.fn().mockResolvedValue(undefined);
    const registration = { update };
    options.onRegisteredSW("sw.js", registration);

    // Intet kald endnu — kun selve intervallet er sat op.
    expect(update).not.toHaveBeenCalled();

    vi.advanceTimersByTime(20 * 60 * 1000);
    expect(update).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(20 * 60 * 1000);
    expect(update).toHaveBeenCalledTimes(2);
  });

  it("gør intet ved onRegisteredSW hvis der ikke er nogen registrering", async () => {
    const { registerServiceWorker } = await import("./pwa.js");
    registerServiceWorker();

    const options = registerSWMock.mock.calls[0][0];
    // Skal ikke kaste, selvom registration er null (fx registrering fejlede).
    expect(() => options.onRegisteredSW("sw.js", null)).not.toThrow();
  });
});

describe("opdatering når appen kommer i forgrunden (BUGS.md #102)", () => {
  beforeEach(() => {
    registerSWMock.mockClear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function setVisibility(state) {
    Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
  }

  it("tjekker når siden bliver synlig igen, men ikke oftere end hvert minut", async () => {
    const { registerServiceWorker } = await import("./pwa.js");
    registerServiceWorker();
    const update = vi.fn().mockResolvedValue(undefined);
    registerSWMock.mock.calls[0][0].onRegisteredSW("sw.js", { update });

    // Lige efter registreringen: for tæt på, intet ekstra tjek.
    setVisibility("visible");
    expect(update).not.toHaveBeenCalled();

    vi.advanceTimersByTime(5 * 60 * 1000);
    setVisibility("hidden");
    expect(update).not.toHaveBeenCalled();
    setVisibility("visible");
    expect(update).toHaveBeenCalledTimes(1);

    // Straks igen: droslet.
    setVisibility("visible");
    expect(update).toHaveBeenCalledTimes(1);
  });
});

describe("vite.config.js — service workeren skal selv tage over (BUGS.md #102)", () => {
  // En ren kilde-vagt: med `injectRegister: false` sætter vite-plugin-pwa
  // IKKE skipWaiting/clientsClaim af sig selv, og uden dem lå hver ny
  // version i "waiting" til alle faner var lukket. Fjernes de, skal det
  // være et bevidst valg, ikke et uheld.
  const config = readFileSync(resolve(process.cwd(), "vite.config.js"), "utf-8");

  it("sætter skipWaiting og clientsClaim eksplicit", () => {
    expect(config).toMatch(/skipWaiting:\s*true/);
    expect(config).toMatch(/clientsClaim:\s*true/);
  });
});
