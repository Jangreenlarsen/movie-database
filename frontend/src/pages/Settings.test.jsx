/**
 * Feature #154 — oppetids-formateringen bag systemovervågnings-sektionen.
 * En forkert enheds-afrunding eller en glemt null-håndtering ville vise
 * brugeren en forkert eller crashende oppetid uden at nogen opdager det
 * (regel 19).
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import {
  AccountSection,
  AnthemDiagnosticsSection,
  DeploySection,
  MessagePreviewSection,
  PasswordPolicySection,
  PlexAutoImportSection,
  PlexImportSection,
  PlexShieldSettingsRow,
  ScreeningRequestPolicySection,
  SendTestEmailRow,
  SerialNumberSection,
  SystemSettingsSection,
  TestModeSection,
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
/**
 * Feature #194 — Jan: "vi skal have en mulighed for at opdater fra github på
 * Main eller Dev på portal". Det testværdige (regel 19): valget af branch
 * skal rent faktisk sendes med til `api.triggerDeploy`, og dev-branchen skal
 * kræve en bekræftelse (samme mønster som andre risikable handlinger) —
 * en fejl her ville enten stille opdatere til den forkerte branch, eller
 * lade en admin opdatere produktionen til dev uden nogen advarsel.
 */
describe("DeploySection — branch-valg (feature #194)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "health").mockResolvedValue({ version: "0.1.0", build: "0001" });
    vi.spyOn(api, "getDeployStatus").mockResolvedValue({ outcome: "unknown" });
  });

  it("opdaterer til main uden at bede om bekræftelse", async () => {
    const triggerSpy = vi.spyOn(api, "triggerDeploy").mockResolvedValue();
    const confirmSpy = vi.spyOn(window, "confirm");
    const user = userEvent.setup();

    render(<DeploySection />);
    await user.click(await screen.findByRole("button", { name: "Opdatér fra GitHub" }));

    expect(triggerSpy).toHaveBeenCalledWith("main");
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("viser en advarsel og beder om bekræftelse ved dev, og opdaterer når bekræftet", async () => {
    const triggerSpy = vi.spyOn(api, "triggerDeploy").mockResolvedValue();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();

    render(<DeploySection />);
    await user.click(screen.getByLabelText(/dev \(udvikling\)/));
    expect(screen.getByText(/ikke nødvendigvis stabil/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Opdatér fra GitHub" }));

    expect(confirmSpy).toHaveBeenCalled();
    expect(triggerSpy).toHaveBeenCalledWith("dev");
  });

  it("opdaterer ikke hvis bekræftelsen til dev afvises", async () => {
    const triggerSpy = vi.spyOn(api, "triggerDeploy").mockResolvedValue();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();

    render(<DeploySection />);
    await user.click(screen.getByLabelText(/dev \(udvikling\)/));
    await user.click(screen.getByRole("button", { name: "Opdatér fra GitHub" }));

    expect(triggerSpy).not.toHaveBeenCalled();
  });
});

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
 * Feature #206 (#197's afgrænsede "senere"-punkt: admin kan nu redigere en
 * ANDEN brugers e-mail, ikke kun sin egen). Det testværdige (regel 19): en
 * gemt ændring skal rent faktisk kalde det rigtige endpoint med den
 * indtastede værdi og genindlæse listen, og backendens specifikke fejl skal
 * vises.
 */
describe("UsersSection — admin redigerer en brugers e-mail (feature #206)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
  });

  function mockUserWithEmail(email) {
    vi.spyOn(api, "listUsers").mockResolvedValue([
      {
        id: "u1",
        username: "hasmail",
        full_name: null,
        email,
        role: "standard",
        status: "active",
        settings: {},
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
  }

  it("viser 'Ingen e-mail' når feltet er tomt", async () => {
    mockUserWithEmail(null);
    render(<UsersSection currentUserId="admin1" />);
    expect(await screen.findByText("Ingen e-mail")).toBeInTheDocument();
  });

  it("gemmer den nye adresse og genindlæser listen", async () => {
    mockUserWithEmail(null);
    const updateSpy = vi.spyOn(api, "updateMyEmail").mockResolvedValue({});
    const user = userEvent.setup();

    render(<UsersSection currentUserId="admin1" />);
    await user.click(await screen.findByRole("button", { name: "Redigér e-mail" }));
    await user.type(screen.getByPlaceholderText("din@e-mail.dk"), "hasmail@example.com");
    await user.click(screen.getByRole("button", { name: "Gem" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith("u1", "hasmail@example.com")
    );
  });

  it("annullér lukker redigeringen uden at kalde API'et", async () => {
    mockUserWithEmail("hasmail@example.com");
    const updateSpy = vi.spyOn(api, "updateMyEmail");
    const user = userEvent.setup();

    render(<UsersSection currentUserId="admin1" />);
    await user.click(await screen.findByRole("button", { name: "Redigér e-mail" }));
    await user.click(screen.getByRole("button", { name: "Annullér" }));

    expect(updateSpy).not.toHaveBeenCalled();
    expect(screen.getByText("hasmail@example.com")).toBeInTheDocument();
  });

  it("viser backendens specifikke fejlbesked ved en fejlet gemning", async () => {
    mockUserWithEmail(null);
    vi.spyOn(api, "updateMyEmail").mockRejectedValue(new Error("Ugyldig e-mailadresse"));
    const user = userEvent.setup();

    render(<UsersSection currentUserId="admin1" />);
    await user.click(await screen.findByRole("button", { name: "Redigér e-mail" }));
    await user.type(screen.getByPlaceholderText("din@e-mail.dk"), "not-an-email");
    await user.click(screen.getByRole("button", { name: "Gem" }));

    expect(await screen.findByText("Ugyldig e-mailadresse")).toBeInTheDocument();
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
 * Feature #177/#186 — admin-indstilling for dato/tidspunkt-krav ved
 * visningsønsker, gælder alle roller ens siden #186. Samme testværdige
 * begrundelse som PasswordPolicySection ovenfor: den indlæste værdi skal
 * reelt afspejles, og gem/fejl skal vises.
 */
describe("TestModeSection (feature #217)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("indlæser og viser den nuværende tilstand", async () => {
    vi.spyOn(api, "getTestModePolicy").mockResolvedValue({ test_mode: true });
    render(<TestModeSection />);

    expect(await screen.findByRole("checkbox", { name: "Test-tilstand aktiv" })).toBeChecked();
    expect(
      screen.getByText("Test-tilstand er aktiv — ingen e-mails eller beskeder bliver sendt lige nu.")
    ).toBeInTheDocument();
  });

  it("skjuler advarslen når tilstanden er slået fra", async () => {
    vi.spyOn(api, "getTestModePolicy").mockResolvedValue({ test_mode: false });
    render(<TestModeSection />);

    await screen.findByRole("checkbox", { name: "Test-tilstand aktiv" });
    expect(
      screen.queryByText("Test-tilstand er aktiv — ingen e-mails eller beskeder bliver sendt lige nu.")
    ).not.toBeInTheDocument();
  });

  it("gemmer ændringer og bekræfter det", async () => {
    vi.spyOn(api, "getTestModePolicy").mockResolvedValue({ test_mode: false });
    const updateSpy = vi.spyOn(api, "updateTestModePolicy").mockResolvedValue({ test_mode: true });
    const user = userEvent.setup();

    render(<TestModeSection />);
    const checkbox = await screen.findByRole("checkbox", { name: "Test-tilstand aktiv" });
    expect(checkbox).not.toBeChecked();

    await user.click(checkbox);
    await user.click(screen.getByRole("button", { name: "Gem" }));

    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith({ test_mode: true }));
    expect(await screen.findByText("Gemt!")).toBeInTheDocument();
  });

  it("viser backend-fejlbeskeden ved en mislykket gemning", async () => {
    vi.spyOn(api, "getTestModePolicy").mockResolvedValue({ test_mode: false });
    vi.spyOn(api, "updateTestModePolicy").mockRejectedValue(new Error("Serverfejl"));
    const user = userEvent.setup();

    render(<TestModeSection />);
    await screen.findByRole("checkbox", { name: "Test-tilstand aktiv" });
    await user.click(screen.getByRole("button", { name: "Gem" }));

    expect(await screen.findByText("Serverfejl")).toBeInTheDocument();
  });
});

/**
 * Feature #223 (Jan: "hvordan kan jeg se hvordan en besked se ud, kan vi
 * lave en besked design editor hvor alle de besked typer som er i spil
 * kan se og edit"). Det testværdige (regel 19, tilstands-skift i et
 * vindue): sektionen skal IKKE hente noget før den foldes ud (lazy), skal
 * vise den valgte type korrekt (emne/brødtekst/e-mail-html), skal kunne
 * skifte mellem typer, og skal håndtere de typer der IKKE har en
 * e-mail-udgave (ingen iframe for dem).
 */
function _previews() {
  return [
    {
      key: "wishlist_moved",
      name: "Ønske flyttet til biblioteket",
      description: "Til den der ønskede titlen, når den er købt.",
      subject: "Din ønskede film er nu i biblioteket",
      body: 'Den film du satte på indkøbslisten — "Dune: Part Two" — er nu købt og lagt i biblioteket. 🎬',
      html: "<html><body>Preview-html for wishlist_moved</body></html>",
    },
    {
      key: "admins_new_wishlist",
      name: "Admin: nyt ønske",
      description: "Til alle admins, når en bruger tilføjer en titel til ønskelisten.",
      subject: "Nyt ønske på indkøbslisten",
      body: 'anna har tilføjet "Dune: Part Two" (film) til ønskelisten.',
      html: null,
    },
  ];
}

describe("MessagePreviewSection (feature #223)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("henter ikke besked-eksempler før sektionen foldes ud", async () => {
    const spy = vi.spyOn(api, "listMessagePreviews").mockResolvedValue(_previews());
    render(<MessagePreviewSection />);

    await screen.findByText("Sådan ser beskederne ud");
    expect(spy).not.toHaveBeenCalled();
  });

  it("folder ud, henter og viser listen af besked-typer med den første valgt", async () => {
    vi.spyOn(api, "listMessagePreviews").mockResolvedValue(_previews());
    const user = userEvent.setup();
    render(<MessagePreviewSection />);

    await user.click(screen.getByRole("button", { name: /Sådan ser beskederne ud/ }));

    expect(await screen.findByRole("button", { name: "Ønske flyttet til biblioteket" })).toBeInTheDocument();
    expect(screen.getByText("Din ønskede film er nu i biblioteket")).toBeInTheDocument();
    expect(screen.getByText(/Den film du satte på indkøbslisten/)).toBeInTheDocument();
  });

  it("viser e-mail-udgaven som en iframe når typen har html", async () => {
    vi.spyOn(api, "listMessagePreviews").mockResolvedValue(_previews());
    const user = userEvent.setup();
    render(<MessagePreviewSection />);

    await user.click(screen.getByRole("button", { name: /Sådan ser beskederne ud/ }));
    await screen.findByText("Din ønskede film er nu i biblioteket");

    const frame = document.querySelector(".message-preview-frame");
    expect(frame).toBeInTheDocument();
    expect(frame.getAttribute("srcdoc")).toContain("Preview-html for wishlist_moved");
  });

  it("skifter til den valgte type ved klik i listen, uden iframe når typen ikke har html", async () => {
    vi.spyOn(api, "listMessagePreviews").mockResolvedValue(_previews());
    const user = userEvent.setup();
    render(<MessagePreviewSection />);

    await user.click(screen.getByRole("button", { name: /Sådan ser beskederne ud/ }));
    await screen.findByText("Din ønskede film er nu i biblioteket");

    await user.click(screen.getByRole("button", { name: "Admin: nyt ønske" }));

    expect(await screen.findByText("Nyt ønske på indkøbslisten")).toBeInTheDocument();
    expect(screen.queryByText("Din ønskede film er nu i biblioteket")).not.toBeInTheDocument();
    expect(document.querySelector(".message-preview-frame")).not.toBeInTheDocument();
  });

  it("viser backendens specifikke fejlbesked hvis hentningen fejler", async () => {
    vi.spyOn(api, "listMessagePreviews").mockRejectedValue(new Error("Kun admin kan se dette"));
    const user = userEvent.setup();
    render(<MessagePreviewSection />);

    await user.click(screen.getByRole("button", { name: /Sådan ser beskederne ud/ }));

    expect(await screen.findByText("Kun admin kan se dette")).toBeInTheDocument();
  });
});

describe("ScreeningRequestPolicySection (feature #177/#186)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("indlæser og viser den nuværende politik", async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at: false,
    });
    render(<ScreeningRequestPolicySection />);

    expect(
      await screen.findByRole("checkbox", { name: "Kræv ønsket tidspunkt" })
    ).not.toBeChecked();
  });

  it("gemmer ændringer og bekræfter det", async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at: true,
    });
    const updateSpy = vi
      .spyOn(api, "updateScreeningRequestPolicy")
      .mockResolvedValue({ require_preferred_at: false });
    const user = userEvent.setup();

    render(<ScreeningRequestPolicySection />);
    const checkbox = await screen.findByRole("checkbox", {
      name: "Kræv ønsket tidspunkt",
    });
    expect(checkbox).toBeChecked();

    await user.click(checkbox);
    await user.click(screen.getByRole("button", { name: "Gem" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith({ require_preferred_at: false })
    );
    expect(await screen.findByText("Gemt!")).toBeInTheDocument();
  });

  it("viser backend-fejlbeskeden ved en mislykket gemning", async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at: true,
    });
    vi.spyOn(api, "updateScreeningRequestPolicy").mockRejectedValue(new Error("Serverfejl"));
    const user = userEvent.setup();

    render(<ScreeningRequestPolicySection />);
    await screen.findByRole("checkbox", { name: "Kræv ønsket tidspunkt" });
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

/**
 * Feature #188 (retter BUGS.md #81) — engangs-omnummerering af D#-serien fra
 * 1. Det testværdige (regel 19, "tilstands-skift i et vindue"): knappen skal
 * reelt spørge om bekræftelse først, en annulleret bekræftelse må aldrig kalde
 * API'et, og både succes- og fejl-udfald skal vises korrekt — inklusive at
 * "Ledige numre"-oversigten genindlæses efter en vellykket omnummerering, så
 * Jan ser den nye, sammenhængende D#-serie med det samme.
 */
describe("SerialNumberSection — omnummerering af D#-serien (feature #188)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function mockConfig(overrides = {}) {
    return {
      start_number: 166,
      increment: 1,
      padding_width: 3,
      reuse_freed: false,
      free_numbers: { physical_movies: [], physical_tv: [], digital: [] },
      ...overrides,
    };
  }

  it("spørger om bekræftelse, og annulleret bekræftelse kalder aldrig API'et", async () => {
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue(mockConfig());
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    const renumberSpy = vi.spyOn(api, "renumberDigitalSerialNumbers");
    const user = userEvent.setup();

    render(<SerialNumberSection isAdmin={true} />);
    const button = await screen.findByRole("button", { name: "Omnummerér D#-serien fra 1" });
    await user.click(button);

    expect(confirmSpy).toHaveBeenCalled();
    expect(renumberSpy).not.toHaveBeenCalled();
  });

  it("viser antal omnummererede poster efter bekræftelse, og genindlæser ledige numre", async () => {
    vi.spyOn(api, "getSerialNumberConfig")
      .mockResolvedValueOnce(mockConfig({ start_number: 166, free_numbers: { physical_movies: [], physical_tv: [], digital: [] } }))
      .mockResolvedValueOnce(
        mockConfig({ start_number: 4, free_numbers: { physical_movies: [], physical_tv: [], digital: [1, 2, 3] } })
      );
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "renumberDigitalSerialNumbers").mockResolvedValue({ renumbered: 3 });
    const user = userEvent.setup();

    render(<SerialNumberSection isAdmin={true} />);
    const button = await screen.findByRole("button", { name: "Omnummerér D#-serien fra 1" });
    await user.click(button);

    expect(await screen.findByText("3 digitale poster omnummereret.")).toBeInTheDocument();
    // BUGS.md #86 — ledige numre vises nu som en dropdown (options) i
    // stedet for en kommasepareret tekststreng.
    expect(await screen.findByRole("option", { name: "D#1" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "D#2" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "D#3" })).toBeInTheDocument();
  });

  it("viser backendens specifikke fejlbesked hvis omnummerering fejler", async () => {
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue(mockConfig());
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "renumberDigitalSerialNumbers").mockRejectedValue(
      new Error("Der er allerede en omnummerering i gang.")
    );
    const user = userEvent.setup();

    render(<SerialNumberSection isAdmin={true} />);
    const button = await screen.findByRole("button", { name: "Omnummerér D#-serien fra 1" });
    await user.click(button);

    expect(await screen.findByText("Der er allerede en omnummerering i gang.")).toBeInTheDocument();
  });

  it("vises ikke for ikke-admin brugere", async () => {
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue(mockConfig());

    render(<SerialNumberSection isAdmin={false} />);
    await screen.findByText("Serienummer-opsætning");

    expect(screen.queryByRole("button", { name: "Omnummerér D#-serien fra 1" })).not.toBeInTheDocument();
  });
});

/**
 * BUGS.md #86 (Jan, 2026-08-22: "under settings/bibliotek/Serienummer-
 * opsætning skal vi have serie nr. i en dropdown liste fordi hvis der er
 * mange nr. ikke i brug bliver den liste meget stor"). Det testværdige: den
 * kommaseparerede tekst er erstattet af en `<select>`, og et loft ramt
 * (backend'ens MAX_FREE_NUMBERS, 100) skal vise en tydelig "kun de laveste"-
 * besked i stedet for stiltiende at se ud som en komplet liste.
 */
describe("SerialFreeList — ledige numre som dropdown (BUGS.md #86)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function mockConfig(overrides = {}) {
    return {
      start_number: 166,
      increment: 1,
      padding_width: 3,
      reuse_freed: false,
      free_numbers: { physical_movies: [], physical_tv: [], digital: [] },
      ...overrides,
    };
  }

  it("viser ledige numre som en dropdown med hvert nummer som en option", async () => {
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue(
      mockConfig({ free_numbers: { physical_movies: [2, 5, 7], physical_tv: [], digital: [] } })
    );

    render(<SerialNumberSection isAdmin={true} />);

    expect(await screen.findByRole("option", { name: "M#2" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "M#5" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "M#7" })).toBeInTheDocument();
  });

  it("viser 'ingen' i stedet for en tom dropdown når der ikke er ledige numre", async () => {
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue(
      mockConfig({ free_numbers: { physical_movies: [], physical_tv: [], digital: [] } })
    );

    render(<SerialNumberSection isAdmin={true} />);

    expect(await screen.findAllByText("ingen")).toHaveLength(3);
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("viser en 'kun de laveste' -besked når loftet på 100 er ramt", async () => {
    const hundredNumbers = Array.from({ length: 100 }, (_, i) => i + 1);
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue(
      mockConfig({ free_numbers: { physical_movies: hundredNumbers, physical_tv: [], digital: [] } })
    );

    render(<SerialNumberSection isAdmin={true} />);

    expect(await screen.findByText("viser kun de 100 laveste")).toBeInTheDocument();
  });

  it("viser IKKE en 'kun de laveste'-besked når antallet er under loftet", async () => {
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue(
      mockConfig({ free_numbers: { physical_movies: [1, 2, 3], physical_tv: [], digital: [] } })
    );

    render(<SerialNumberSection isAdmin={true} />);

    await screen.findByRole("option", { name: "M#1" });
    expect(screen.queryByText(/viser kun de/)).not.toBeInTheDocument();
  });
});

/**
 * Feature #197 — udgående e-mail via Resend. Det testværdige (regel 19):
 * de to nye Indstillinger-rækker skal rent faktisk sende det rigtige felt-
 * navn med til `updateSystemSettings`, samme som enhver anden
 * nøgle/plain-række på denne side — en kopiér-fejl her ville stille sætte
 * en helt anden nøgle end den admin troede de rettede.
 */
describe("SystemSettingsSection — Resend/e-mail (feature #197)", () => {
  const fullStatus = {
    tmdb_api_token: { configured: false, source: "unset" },
    discogs_token: { configured: false, source: "unset" },
    upcdatabase_token: { configured: false, source: "unset" },
    ean_search_api_key: { configured: false, source: "unset" },
    omdb_api_key: { configured: false, source: "unset" },
    plex_token: { configured: false, source: "unset" },
    plex_server_url: "",
    primary_barcode_source: "upcitemdb",
    plex_shield_client_identifier: "",
    anthem_host: "",
    anthem_port: 14999,
    resend_api_key: { configured: false, source: "unset" },
    email_from_address: "",
  };

  beforeEach(() => {
    vi.spyOn(api, "getSystemSettings").mockResolvedValue(fullStatus);
  });

  it("gemmer resend_api_key under det rigtige feltnavn", async () => {
    const updateSpy = vi.spyOn(api, "updateSystemSettings").mockResolvedValue({});
    render(<SystemSettingsSection />);

    // Flere rækker deler samme "Ikke sat"-pladsholder — find NETOP Resend-
    // rækkens felt via dens label, og hold sig til dens egen form/knap
    // resten af vejen, så testen ikke ved et tilfælde rammer en anden nøgle.
    const input = await screen.findByLabelText(/Resend API-nøgle/);
    await userEvent.type(input, "re_test_key");
    const form = input.closest("form");
    await userEvent.click(within(form).getByRole("button", { name: "Gem" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith(expect.objectContaining({ resend_api_key: "re_test_key" }))
    );
  });

  it("gemmer email_from_address som almindelig tekst, ikke maskeret", async () => {
    const updateSpy = vi.spyOn(api, "updateSystemSettings").mockResolvedValue({});
    render(<SystemSettingsSection />);

    const input = await screen.findByLabelText(/E-mail-afsenderadresse/);
    await userEvent.type(input, "Voldby BIO <noreply@laces.dk>");
    const form = input.closest("form");
    await userEvent.click(within(form).getByRole("button", { name: "Gem" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ email_from_address: "Voldby BIO <noreply@laces.dk>" })
      )
    );
  });
});

/**
 * Feature #212 (Jan: "kan vi ikke lige få en test funktion ind i api config
 * for AVM70 også sådan at vi kan testet den på samme hvilkor som api
 * keys"). Det testværdige (regel 19): knappen skal rent faktisk kalde
 * `testSystemSetting("anthem_host")` (ikke en anden nøgle ved en
 * kopiér-fejl) og vise backendens resultat-besked, både ved succes og fejl.
 */
describe("AnthemTestConnectionRow (feature #212)", () => {
  const fullStatus = {
    tmdb_api_token: { configured: false, source: "unset" },
    discogs_token: { configured: false, source: "unset" },
    upcdatabase_token: { configured: false, source: "unset" },
    ean_search_api_key: { configured: false, source: "unset" },
    omdb_api_key: { configured: false, source: "unset" },
    plex_token: { configured: false, source: "unset" },
    plex_server_url: "",
    primary_barcode_source: "upcitemdb",
    plex_shield_client_identifier: "",
    anthem_host: "192.168.1.60",
    anthem_port: 14999,
    resend_api_key: { configured: false, source: "unset" },
    email_from_address: "",
  };

  beforeEach(() => {
    vi.spyOn(api, "getSystemSettings").mockResolvedValue(fullStatus);
  });

  // Flere rækker på siden deler samme "Test forbindelse"-knaptekst (TMDb,
  // Discogs, Resend, ...) — skop til netop Anthem-kortet via dets egen
  // overskrift, så testen ikke ved et tilfælde rammer en anden nøgles knap.
  async function anthemSection() {
    const heading = await screen.findByRole("heading", { name: "Anthem AVM 70" });
    return within(heading.closest(".settings-section"));
  }

  it("kalder testSystemSetting med anthem_host og viser succes-beskeden", async () => {
    const testSpy = vi
      .spyOn(api, "testSystemSetting")
      .mockResolvedValue({ ok: true, message: "Forbundet til Anthem-enheden på 192.168.1.60:14999" });
    render(<SystemSettingsSection />);

    const section = await anthemSection();
    await userEvent.click(section.getByRole("button", { name: "Test forbindelse" }));

    expect(testSpy).toHaveBeenCalledWith("anthem_host");
    expect(
      await section.findByText(/Forbundet til Anthem-enheden på 192\.168\.1\.60:14999/)
    ).toBeInTheDocument();
  });

  it("viser den specifikke fejlbesked ved en mislykket test", async () => {
    vi.spyOn(api, "testSystemSetting").mockResolvedValue({
      ok: false,
      message: "Kunne ikke forbinde til 192.168.1.60:14999 (Connection refused)",
    });
    render(<SystemSettingsSection />);

    const section = await anthemSection();
    await userEvent.click(section.getByRole("button", { name: "Test forbindelse" }));

    expect(
      await section.findByText(/Kunne ikke forbinde til 192\.168\.1\.60:14999 \(Connection refused\)/)
    ).toBeInTheDocument();
  });
});

/**
 * Feature #197 — brugerens egen e-mail (Indstillinger → Konto), kun brugt
 * til udgående notifikationer. Det testværdige (regel 19): en vellykket
 * gemning skal give den opdaterede bruger videre til `onSettingsChanged`
 * (ellers ville resten af appen blive ved med at vise den GAMLE e-mail
 * indtil næste fulde sideindlæsning), og en backend-fejl skal vises som
 * den specifikke besked (regel 16), ikke bare forsvinde.
 */
describe("AccountSection — e-mail (feature #197)", () => {
  const baseUser = { id: "u1", username: "jan", role: "standard", email: null };

  it("gemmer e-mailen og giver den opdaterede bruger videre til onSettingsChanged", async () => {
    const updated = { ...baseUser, email: "jan@example.com" };
    vi.spyOn(api, "updateMyEmail").mockResolvedValue(updated);
    const onSettingsChanged = vi.fn();

    render(<AccountSection user={baseUser} onSettingsChanged={onSettingsChanged} />);

    await userEvent.type(screen.getByLabelText("E-mail"), "jan@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Gem e-mail" }));

    await waitFor(() => expect(api.updateMyEmail).toHaveBeenCalledWith("u1", "jan@example.com"));
    expect(onSettingsChanged).toHaveBeenCalledWith(updated);
    expect(await screen.findByText("E-mail gemt!")).toBeInTheDocument();
  });

  it("viser backendens specifikke fejlbesked i stedet for at sluge den", async () => {
    // Syntaktisk gyldig nok til at bestå <input type="email">s egen native
    // browser-validering (ellers når submit-handleren aldrig at køre i
    // jsdom) — selve pointen er at bekræfte at EN fejl fra backend vises
    // med sin specifikke besked (regel 16), ikke frontendens eget formatkrav.
    vi.spyOn(api, "updateMyEmail").mockRejectedValue(new Error("value is not a valid email address"));
    render(<AccountSection user={baseUser} onSettingsChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("E-mail"), "en.email@eksempel.dk");
    await userEvent.click(screen.getByRole("button", { name: "Gem e-mail" }));

    expect(await screen.findByText("value is not a valid email address")).toBeInTheDocument();
  });

  it("sender null (ikke tom streng) når feltet ryddes, så backend rydder e-mailen i stedet for at afvise den", async () => {
    const updateSpy = vi
      .spyOn(api, "updateMyEmail")
      .mockResolvedValue({ ...baseUser, email: null });
    render(<AccountSection user={{ ...baseUser, email: "old@example.com" }} onSettingsChanged={vi.fn()} />);

    const input = screen.getByLabelText("E-mail");
    await userEvent.clear(input);
    await userEvent.click(screen.getByRole("button", { name: "Gem e-mail" }));

    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith("u1", null));
  });
});

/**
 * Feature #199 (Jan: "lave også en email test funktion") — knappen der
 * sender en ægte testmail, adskilt fra "Test forbindelse" (som kun
 * bekræfter nøglens gyldighed). Det testværdige (regel 19): den indtastede
 * adresse skal rent faktisk sendes med, og et succes-/fejlsvar skal vises
 * korrekt — ellers ved en admin ikke om Resend-opsætningen reelt virker.
 */
describe("SendTestEmailRow (feature #199)", () => {
  it("sender testmailen til den indtastede adresse og viser succes-beskeden", async () => {
    const sendSpy = vi
      .spyOn(api, "sendTestEmail")
      .mockResolvedValue({ ok: true, message: "Testmail sendt — tjek indbakken (og evt. spam-mappen)" });
    render(<SendTestEmailRow />);

    await userEvent.type(screen.getByLabelText(/Send en testmail til/), "jan@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send testmail" }));

    await waitFor(() => expect(sendSpy).toHaveBeenCalledWith("jan@example.com"));
    expect(await screen.findByText(/Testmail sendt/)).toBeInTheDocument();
  });

  it("viser den specifikke fejlbesked når Resend afviser afsendelsen", async () => {
    vi.spyOn(api, "sendTestEmail").mockResolvedValue({
      ok: false,
      message: "Resend-nøgle og/eller e-mail-afsenderadresse mangler",
    });
    render(<SendTestEmailRow />);

    await userEvent.type(screen.getByLabelText(/Send en testmail til/), "jan@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send testmail" }));

    expect(await screen.findByText(/nøgle og\/eller e-mail-afsenderadresse mangler/)).toBeInTheDocument();
  });

  it("knappen er deaktiveret uden en indtastet adresse", () => {
    render(<SendTestEmailRow />);
    expect(screen.getByRole("button", { name: "Send testmail" })).toBeDisabled();
  });
});
