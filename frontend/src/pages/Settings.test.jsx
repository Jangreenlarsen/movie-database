/**
 * Feature #154 — oppetids-formateringen bag systemovervågnings-sektionen.
 * En forkert enheds-afrunding eller en glemt null-håndtering ville vise
 * brugeren en forkert eller crashende oppetid uden at nogen opdager det
 * (regel 19).
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { UsersSection, formatUptime } from "./Settings";

/**
 * Feature #171 — admin-assisteret adgangskode-nulstilling. Det testværdige
 * (regel 19, "tilstands-skift i et vindue"): bekræft-dialogen skal reelt
 * forhindre kaldet ved annullering, og den viste adgangskode/kopiér-tilstand
 * skal både dukke op og forsvinde korrekt igen — ellers kan en admin komme
 * til at nulstille ved et fejlklik, eller stå med et "Kopieret!" der aldrig
 * refererede til den rigtige værdi.
 */
describe("UsersSection — adgangskode-nulstilling (feature #171)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function mockOneActiveUser() {
    vi.spyOn(api, "listUsers").mockResolvedValue([
      {
        id: "u1",
        username: "resetme",
        full_name: null,
        role: "standard",
        status: "active",
        settings: {},
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
  }

  it("viser og kopierer den nye adgangskode efter bekræftelse", async () => {
    mockOneActiveUser();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const resetSpy = vi
      .spyOn(api, "resetUserPassword")
      .mockResolvedValue({ username: "resetme", new_password: "Ab3dEfGh9Jkm" });
    const user = userEvent.setup();
    // @testing-library/user-event installs sin egen clipboard-stub ved
    // setup() (en getter-baseret erstatning af navigator.clipboard) — den
    // skal spies på *efter* setup(), ellers overskriver user-event vores
    // egen mock og "skrevet til udklipsholder"-assertet nedenfor kan aldrig
    // se kaldet.
    const writeTextSpy = vi.spyOn(navigator.clipboard, "writeText");

    render(<UsersSection currentUserId="admin1" />);

    const resetButton = await screen.findByRole("button", { name: "Nulstil adgangskode" });
    await user.click(resetButton);

    expect(resetSpy).toHaveBeenCalledWith("u1");
    expect(await screen.findByText("Ny adgangskode til resetme:")).toBeInTheDocument();
    expect(screen.getByText("Ab3dEfGh9Jkm")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Kopiér" }));
    expect(writeTextSpy).toHaveBeenCalledWith("Ab3dEfGh9Jkm");
    expect(await screen.findByRole("button", { name: "Kopieret!" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Luk" }));
    await waitFor(() =>
      expect(screen.queryByText("Ny adgangskode til resetme:")).not.toBeInTheDocument()
    );
  });

  it("annulleret bekræftelse kalder aldrig API'et", async () => {
    mockOneActiveUser();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const resetSpy = vi.spyOn(api, "resetUserPassword");
    const user = userEvent.setup();

    render(<UsersSection currentUserId="admin1" />);

    const resetButton = await screen.findByRole("button", { name: "Nulstil adgangskode" });
    await user.click(resetButton);

    expect(resetSpy).not.toHaveBeenCalled();
    expect(screen.queryByText(/Ny adgangskode til/)).not.toBeInTheDocument();
  });
});

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
