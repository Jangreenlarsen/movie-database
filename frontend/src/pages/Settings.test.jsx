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
  AnthemDiagnosticsSection,
  PasswordPolicySection,
  PlexAutoImportSection,
  PlexImportSection,
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
 * Feature #178-opfølgning (Jan: "sæt op i users styring hvem kan se og
 * bruge vis iplex/spil i plex i detajle for film/tv"). Det testværdige
 * (regel 19): knappen skal reelt afspejle og skifte den enkelte brugers
 * tilstand, ikke bare vise et statisk label.
 */
describe("UsersSection — Plex-link pr. bruger (feature #178-opfølgning)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
  });

  function mockOneUser(plexPlayEnabled) {
    vi.spyOn(api, "listUsers").mockResolvedValue([
      {
        id: "u1",
        username: "plexuser",
        full_name: null,
        role: "standard",
        status: "active",
        plex_play_enabled: plexPlayEnabled,
        settings: {},
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
  }

  it("viser 'Til' for en bruger med adgang, og slår den fra ved klik", async () => {
    mockOneUser(true);
    const toggleSpy = vi.spyOn(api, "updateUserPlexPlay").mockResolvedValue({});
    const user = userEvent.setup();

    render(<UsersSection currentUserId="admin1" />);
    const button = await screen.findByRole("button", { name: "Plex-link: Til" });
    await user.click(button);

    expect(toggleSpy).toHaveBeenCalledWith("u1", false);
  });

  it("viser 'Fra' for en bruger uden adgang, og slår den til ved klik", async () => {
    mockOneUser(false);
    const toggleSpy = vi.spyOn(api, "updateUserPlexPlay").mockResolvedValue({});
    const user = userEvent.setup();

    render(<UsersSection currentUserId="admin1" />);
    const button = await screen.findByRole("button", { name: "Plex-link: Fra" });
    await user.click(button);

    expect(toggleSpy).toHaveBeenCalledWith("u1", true);
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
 * Feature #182 — "Importér fra Plex"s tag-felt er den delte definition som
 * den automatiske scan (feature #181) også bruger (Jan: "søger for at tag
 * på importerede i auto-scan plex er det tag som er difineret under
 * 'importer fra plex'"). Det testværdige (regel 19): feltet skal indlæse
 * den faktisk gemte værdi ved åbning, ikke altid nulstille til den
 * hårdkodede "Plex-import"-default, og skal falde tilbage til defaulten
 * hvis indlæsningen fejler i stedet for at crashe eller vise tomt.
 */
describe("PlexImportSection tag-indlæsning (feature #182)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("indlæser det faktisk gemte tag i stedet for hardkodet default", async () => {
    vi.spyOn(api, "getPlexAutoImportPolicy").mockResolvedValue({
      plex_auto_import_enabled: false,
      plex_auto_import_interval_minutes: 360,
      plex_import_tag: "Fra-Plex-server",
    });

    render(<PlexImportSection />);

    await waitFor(() =>
      expect(screen.getByLabelText(/Tag på importerede/)).toHaveValue("Fra-Plex-server")
    );
  });

  it("falder tilbage til standard-tagget hvis indlæsningen fejler", async () => {
    vi.spyOn(api, "getPlexAutoImportPolicy").mockRejectedValue(new Error("net error"));

    render(<PlexImportSection />);

    expect(await screen.findByLabelText(/Tag på importerede/)).toHaveValue("Plex-import");
  });
});

/**
 * Feature #181 — automatisk periodisk scan af Plex for nye film/serier.
 * Samme testværdige begrundelse som ScreeningRequestPolicySection ovenfor:
 * den indlæste politik (til/fra + interval) skal reelt afspejles, en
 * gemning skal sende de rigtige felter, og en fejl skal vises — ikke
 * sluges.
 */
describe("PlexAutoImportSection (feature #181)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("indlæser og viser den nuværende politik", async () => {
    vi.spyOn(api, "getPlexAutoImportPolicy").mockResolvedValue({
      plex_auto_import_enabled: true,
      plex_auto_import_interval_minutes: 360,
    });
    render(<PlexAutoImportSection />);

    expect(
      await screen.findByRole("checkbox", { name: "Kør automatisk scan" })
    ).toBeChecked();
    expect(screen.getByLabelText(/Interval \(minutter\)/)).toHaveValue(360);
    expect(screen.getByText("≈ hver 6. time")).toBeInTheDocument();
  });

  it("gemmer ændringer og bekræfter det", async () => {
    vi.spyOn(api, "getPlexAutoImportPolicy").mockResolvedValue({
      plex_auto_import_enabled: false,
      plex_auto_import_interval_minutes: 360,
    });
    const updateSpy = vi.spyOn(api, "updatePlexAutoImportPolicy").mockResolvedValue({
      plex_auto_import_enabled: true,
      plex_auto_import_interval_minutes: 120,
    });
    const user = userEvent.setup();

    render(<PlexAutoImportSection />);
    const checkbox = await screen.findByRole("checkbox", { name: "Kør automatisk scan" });
    expect(checkbox).not.toBeChecked();

    await user.click(checkbox);
    const intervalInput = screen.getByLabelText(/Interval \(minutter\)/);
    await user.clear(intervalInput);
    await user.type(intervalInput, "120");
    await user.click(screen.getByRole("button", { name: "Gem" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith({
        plex_auto_import_enabled: true,
        plex_auto_import_interval_minutes: 120,
      })
    );
    expect(await screen.findByText("Gemt!")).toBeInTheDocument();
    expect(screen.getByText("≈ hver 2. time")).toBeInTheDocument();
  });

  it("viser backend-fejlbeskeden ved en mislykket gemning", async () => {
    vi.spyOn(api, "getPlexAutoImportPolicy").mockResolvedValue({
      plex_auto_import_enabled: false,
      plex_auto_import_interval_minutes: 360,
    });
    vi.spyOn(api, "updatePlexAutoImportPolicy").mockRejectedValue(new Error("Serverfejl"));
    const user = userEvent.setup();

    render(<PlexAutoImportSection />);
    await screen.findByRole("checkbox", { name: "Kør automatisk scan" });
    await user.click(screen.getByRole("button", { name: "Gem" }));

    expect(await screen.findByText("Serverfejl")).toBeInTheDocument();
  });

  it("viser en fejl hvis politikken ikke kan hentes", async () => {
    vi.spyOn(api, "getPlexAutoImportPolicy").mockRejectedValue(new Error("net error"));
    render(<PlexAutoImportSection />);

    expect(await screen.findByText("Kunne ikke hente indstillingen.")).toBeInTheDocument();
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

  /**
   * BUGS.md #76 (Jan: "der skal nok noget feedback til så man kan se at din
   * code gør det korekte") — et tomt resultat skal vise HVILKET af de to
   * meget forskellige scenarier det er, ikke bare "intet fundet" begge gange.
   */
  it("skelner mellem 'PMS rapporterer reelt 0' og 'PMS rapporterede noget, men det blev filtreret fra'", async () => {
    vi.spyOn(api, "getPlexClients").mockResolvedValueOnce({
      ok: true,
      items: [],
      raw_entry_count: 0,
    });
    const user = userEvent.setup();
    const { rerender } = render(<PlexShieldSettingsRow currentValue={null} onSaved={() => {}} />);
    await user.click(screen.getByRole("button", { name: "Hent tilgængelige klienter" }));

    expect(
      await screen.findByText(/rapporterede 0 registrerede klienter i alt/)
    ).toBeInTheDocument();

    vi.spyOn(api, "getPlexClients").mockResolvedValueOnce({
      ok: true,
      items: [],
      raw_entry_count: 2,
    });
    rerender(<PlexShieldSettingsRow currentValue={null} onSaved={() => {}} />);
    await user.click(screen.getByRole("button", { name: "Hent tilgængelige klienter" }));

    expect(
      await screen.findByText("Plex-serveren rapporterede 2 klient(er), men ingen af dem havde et brugbart client-id.")
    ).toBeInTheDocument();
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

/**
 * Feature #183 — AVM 70-diagnostik. Det testværdige (regel 19, "tilstands-
 * skift i et vindue"): en modtaget snapshot skal rent faktisk opdatere det
 * viste panel, en fejlet forbindelse skal vise backendens SPECIFIKKE
 * fejlbesked (ikke en generisk — regel 16), og optag/download-knappen skal
 * rent faktisk udløse en fil-download med de akkumulerede hændelser.
 *
 * `api.openAnthemDiagnosticsStream` mockes til at returnere et
 * Response-lignende objekt hvis `.body.getReader()` giver de rå SSE-bytes
 * tilbage chunk for chunk — samme kontrakt komponenten selv læser mod.
 */
describe("AnthemDiagnosticsSection (feature #183)", () => {
  // `hangAfter: true` lader forbindelsen "forblive åben" efter de angivne
  // chunks — samme virkelighed som den rigtige strøm (holdt i live af
  // heartbeats), i modsætning til `done: true` som ville simulere at
  // serveren lukker forbindelsen (og komponenten derfor forlader "live").
  function fakeStreamResponse(chunks, { ok = true, detail, hangAfter = false } = {}) {
    let i = 0;
    const encoder = new TextEncoder();
    return {
      ok,
      json: async () => ({ detail }),
      body: {
        getReader: () => ({
          read: async () => {
            if (i >= chunks.length) {
              if (hangAfter) return new Promise(() => {});
              return { done: true, value: undefined };
            }
            const value = encoder.encode(chunks[i]);
            i += 1;
            return { done: false, value };
          },
        }),
      },
    };
  }

  const snapshotEvent = {
    type: "snapshot",
    timestamp: "2026-08-19T20:00:00+00:00",
    raw: null,
    power: true,
    input_name: "Plex",
    input_number: 3,
    volume: 42,
    mute: false,
    audio_listening_mode_text: "Dolby Atmos",
    audio_input_format_text: "Dolby TrueHD",
    audio_input_channels_text: "7.1-channel",
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("viser det modtagne snapshot i live-panelet", async () => {
    vi.spyOn(api, "openAnthemDiagnosticsStream").mockResolvedValue(
      fakeStreamResponse([`data: ${JSON.stringify(snapshotEvent)}\n\n`])
    );
    const user = userEvent.setup();

    render(<AnthemDiagnosticsSection />);
    await user.click(screen.getByRole("button", { name: "▶ Start overvågning" }));

    expect(await screen.findByText("Plex (3)")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Dolby Atmos")).toBeInTheDocument();
    expect(screen.getByText("Dolby TrueHD")).toBeInTheDocument();
  });

  it("viser backendens specifikke fejlbesked ved en mislykket forbindelse", async () => {
    vi.spyOn(api, "openAnthemDiagnosticsStream").mockResolvedValue(
      fakeStreamResponse([], {
        ok: false,
        detail: "Anthem er ikke konfigureret — sæt IP/port under Indstillinger → Eksterne API-nøgler.",
      })
    );
    const user = userEvent.setup();

    render(<AnthemDiagnosticsSection />);
    await user.click(screen.getByRole("button", { name: "▶ Start overvågning" }));

    expect(
      await screen.findByText(
        "Anthem er ikke konfigureret — sæt IP/port under Indstillinger → Eksterne API-nøgler."
      )
    ).toBeInTheDocument();
  });

  // En manuelt styret strøm — testen skal kunne skubbe events ind ÉT AD
  // GANGEN, med kontrol over hvornår, for pålideligt at kunne teste "kun
  // events der ankommer EFTER optagelse er startet, tælles med" uden at
  // gætte på timing mellem `start()`s læse-loop og et knap-klik.
  function makeControllableStream() {
    const encoder = new TextEncoder();
    const queue = [];
    const waiters = [];

    function push(event) {
      const chunk = { done: false, value: encoder.encode(`data: ${JSON.stringify(event)}\n\n`) };
      if (waiters.length > 0) waiters.shift()(chunk);
      else queue.push(chunk);
    }

    function read() {
      return new Promise((resolve) => {
        if (queue.length > 0) resolve(queue.shift());
        else waiters.push(resolve);
      });
    }

    return {
      response: { ok: true, json: async () => ({}), body: { getReader: () => ({ read }) } },
      push,
    };
  }

  it("optager kun hændelser der ankommer EFTER optagelse er startet, og udløser en download", async () => {
    const { response, push } = makeControllableStream();
    vi.spyOn(api, "openAnthemDiagnosticsStream").mockResolvedValue(response);
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const createUrlSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:fake");
    const revokeUrlSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const user = userEvent.setup();

    render(<AnthemDiagnosticsSection />);
    await user.click(screen.getByRole("button", { name: "▶ Start overvågning" }));

    const recordButton = await screen.findByRole("button", { name: "● Start log-optagelse" });
    await waitFor(() => expect(recordButton).toBeEnabled());

    // Sendt FØR optagelse starter — skal IKKE tælles med i optagelsen.
    push(snapshotEvent);
    await screen.findByText("42");

    await user.click(recordButton);

    // Sendt EFTER optagelse er startet — skal tælles med.
    const secondEvent = { ...snapshotEvent, type: "update", raw: "Z1VOL55", volume: 55 };
    push(secondEvent);
    await screen.findByText("55");

    expect(
      await screen.findByRole("button", { name: "⬇ Download log (1 hændelser)" })
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "⬇ Download log (1 hændelser)" }));

    expect(createUrlSpy).toHaveBeenCalled();
    const [blobArg] = createUrlSpy.mock.calls[0];
    const downloaded = JSON.parse(await blobArg.text());
    expect(downloaded).toHaveLength(1);
    expect(downloaded[0].raw).toBe("Z1VOL55");
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeUrlSpy).toHaveBeenCalledWith("blob:fake");
  });
});
