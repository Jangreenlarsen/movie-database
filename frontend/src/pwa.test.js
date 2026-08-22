/**
 * Feature #190 — PWA'en skal selv tjekke periodisk for en ny version, i
 * stedet for kun at stole på browserens tjek ved en rigtig sideindlæsning
 * (Jan: "hvordan sikker vi os også at folk ikke sider med cache version af
 * site"). Det testværdige: `registerServiceWorker` skal rent faktisk sætte
 * et periodisk `registration.update()`-kald op via `onRegisteredSW`, ikke
 * bare registrere og stoppe der.
 */
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
