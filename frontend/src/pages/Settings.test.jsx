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
import {
  PasswordPolicySection,
  PlexShieldSettingsRow,
  ScreeningRequestPolicySection,
  UsersSection,
  formatUptime,
} from "./Settings";

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
    // jsdom implementerer ikke scrollIntoView. BUGS.md #74 — banneret skal
    // scrolles i syne, så den skal kunne kaldes uden at kaste i alle tests
    // her, ikke kun det ene der selv asserter på den.
    Element.prototype.scrollIntoView = vi.fn();
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

  it("scroller resultat-banneret i syne (BUGS.md #74)", async () => {
    // Med en lang brugerliste kan admin være scrollet langt væk fra toppen
    // af sektionen (hvor banneret dukker op) når knappen klikkes — uden
    // auto-scroll så det aldrig ud af skærmen, som skete for Jan på
    // produktion.
    mockOneActiveUser();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "resetUserPassword").mockResolvedValue({
      username: "resetme",
      new_password: "Ab3dEfGh9Jkm",
    });
    const user = userEvent.setup();

    render(<UsersSection currentUserId="admin1" />);
    const resetButton = await screen.findByRole("button", { name: "Nulstil adgangskode" });
    await user.click(resetButton);

    await screen.findByText("Ny adgangskode til resetme:");
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ block: "start" })
    );
  });

  it("scroller også fejl-banneret i syne, ikke kun det vellykkede resultat", async () => {
    mockOneActiveUser();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "resetUserPassword").mockRejectedValue(new Error("Serverfejl"));
    const user = userEvent.setup();

    render(<UsersSection currentUserId="admin1" />);
    const resetButton = await screen.findByRole("button", { name: "Nulstil adgangskode" });
    await user.click(resetButton);

    await screen.findByText("Serverfejl");
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });
});

/**
 * Feature #174 — adgangskode-politik. Det testværdige (regel 19): den
 * indlæste politik skal faktisk afspejles korrekt i formularens felter
 * (ellers kan en admin tro politikken er én ting, mens den reelt er en
 * anden), og et gemt resultat/en fejl skal vises tydeligt, ikke sluges.
 */
describe("PasswordPolicySection (feature #174)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function mockPolicy(overrides = {}) {
    vi.spyOn(api, "getPasswordPolicy").mockResolvedValue({
      password_min_length: 8,
      password_require_uppercase: false,
      password_require_lowercase: false,
      password_require_digit: false,
      ...overrides,
    });
  }

  it("indlæser og viser den nuværende politik", async () => {
    mockPolicy({ password_min_length: 12, password_require_digit: true });
    render(<PasswordPolicySection />);

    expect(await screen.findByDisplayValue("12")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Kræv mindst ét tal (0-9)" })).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Kræv mindst ét stort bogstav (A-Z)" })
    ).not.toBeChecked();
  });

  it("gemmer ændringer og bekræfter det", async () => {
    mockPolicy();
    const updateSpy = vi.spyOn(api, "updatePasswordPolicy").mockResolvedValue({
      password_min_length: 10,
      password_require_uppercase: true,
      password_require_lowercase: false,
      password_require_digit: false,
    });
    const user = userEvent.setup();

    render(<PasswordPolicySection />);
    await screen.findByDisplayValue("8");

    const minLengthInput = screen.getByLabelText("Minimum-længde (tegn)");
    await user.clear(minLengthInput);
    await user.type(minLengthInput, "10");
    await user.click(screen.getByRole("checkbox", { name: "Kræv mindst ét stort bogstav (A-Z)" }));
    await user.click(screen.getByRole("button", { name: "Gem" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith({
        password_min_length: 10,
        password_require_uppercase: true,
        password_require_lowercase: false,
        password_require_digit: false,
      })
    );
    expect(await screen.findByText("Gemt!")).toBeInTheDocument();
  });

  it("viser backend-fejlbeskeden ved en mislykket gemning", async () => {
    mockPolicy();
    vi.spyOn(api, "updatePasswordPolicy").mockRejectedValue(
      new Error("Adgangskode skal være mindst 6 tegn")
    );
    const user = userEvent.setup();

    render(<PasswordPolicySection />);
    await screen.findByDisplayValue("8");
    await user.click(screen.getByRole("button", { name: "Gem" }));

    expect(await screen.findByText("Adgangskode skal være mindst 6 tegn")).toBeInTheDocument();
  });
});

/**
 * Feature #177 — admin-indstilling for gæsters dato/tidspunkt-krav ved
 * visningsønsker. Samme testværdige begrundelse som PasswordPolicySection
 * ovenfor: den indlæste værdi skal reelt afspejles, og gem/fejl skal vises.
 */
describe("ScreeningRequestPolicySection (feature #177)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("indlæser og viser den nuværende politik", async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at_for_guests: false,
    });
    render(<ScreeningRequestPolicySection />);

    expect(
      await screen.findByRole("checkbox", { name: "Kræv ønsket tidspunkt for gæster" })
    ).not.toBeChecked();
  });

  it("gemmer ændringer og bekræfter det", async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at_for_guests: true,
    });
    const updateSpy = vi
      .spyOn(api, "updateScreeningRequestPolicy")
      .mockResolvedValue({ require_preferred_at_for_guests: false });
    const user = userEvent.setup();

    render(<ScreeningRequestPolicySection />);
    const checkbox = await screen.findByRole("checkbox", {
      name: "Kræv ønsket tidspunkt for gæster",
    });
    expect(checkbox).toBeChecked();

    await user.click(checkbox);
    await user.click(screen.getByRole("button", { name: "Gem" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith({ require_preferred_at_for_guests: false })
    );
    expect(await screen.findByText("Gemt!")).toBeInTheDocument();
  });

  it("viser backend-fejlbeskeden ved en mislykket gemning", async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at_for_guests: true,
    });
    vi.spyOn(api, "updateScreeningRequestPolicy").mockRejectedValue(new Error("Serverfejl"));
    const user = userEvent.setup();

    render(<ScreeningRequestPolicySection />);
    await screen.findByRole("checkbox", { name: "Kræv ønsket tidspunkt for gæster" });
    await user.click(screen.getByRole("button", { name: "Gem" }));

    expect(await screen.findByText("Serverfejl")).toBeInTheDocument();
  });
});

/**
 * Feature #178 — admin-opsætningen der finder/gemmer Shield TV'ets Plex
 * client-id. Det testværdige (regel 19): "Hent klienter" skal rent faktisk
 * liste det backend svarer, et valg skal gemmes med det korrekte id, og en
 * fejl (både ved hentning og ved gemning) skal vises, ikke sluges.
 */
describe("PlexShieldSettingsRow (feature #178)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("henter og lister tilgængelige klienter", async () => {
    vi.spyOn(api, "getPlexClients").mockResolvedValue({
      ok: true,
      items: [{ name: "Shield", machine_identifier: "shield-id", product: "Plex for Android (TV)" }],
    });
    const user = userEvent.setup();

    render(<PlexShieldSettingsRow currentValue={null} onSaved={() => {}} />);
    await user.click(screen.getByRole("button", { name: "Hent tilgængelige klienter" }));

    expect(
      await screen.findByRole("button", { name: "Shield (Plex for Android (TV))" })
    ).toBeInTheDocument();
  });

  it("gemmer det valgte klient-id og kalder onSaved", async () => {
    vi.spyOn(api, "getPlexClients").mockResolvedValue({
      ok: true,
      items: [{ name: "Shield", machine_identifier: "shield-id", product: null }],
    });
    const updateSpy = vi.spyOn(api, "updateSystemSettings").mockResolvedValue({});
    const onSaved = vi.fn();
    const user = userEvent.setup();

    render(<PlexShieldSettingsRow currentValue={null} onSaved={onSaved} />);
    await user.click(screen.getByRole("button", { name: "Hent tilgængelige klienter" }));
    await user.click(await screen.findByRole("button", { name: "Shield" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith({ plex_shield_client_identifier: "shield-id" })
    );
    expect(onSaved).toHaveBeenCalled();
  });

  it("viser fejlbeskeden når klient-listen ikke kan hentes", async () => {
    vi.spyOn(api, "getPlexClients").mockResolvedValue({
      ok: false,
      error: "Plex er ikke konfigureret.",
      items: [],
    });
    const user = userEvent.setup();

    render(<PlexShieldSettingsRow currentValue={null} onSaved={() => {}} />);
    await user.click(screen.getByRole("button", { name: "Hent tilgængelige klienter" }));

    expect(await screen.findByText("Plex er ikke konfigureret.")).toBeInTheDocument();
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
