/**
 * Feature #178 (Jan: "når man trykker på vis i plex så er option at starte
 * den i plex på shield der også"). BUGS.md #79 (Jan, 2026-08-20: "det se ud
 * for mig at det rent faktisk er to spederate komandoer som bliver sendt,
 * hvis det er tilfældet så skal vi have to knapper i steddet for en til
 * start og en til stop") erstattede den tidligere toggle-knap (der GÆTTEDE
 * enhedens tilstand) med to altid-synlige, uafhængige knapper. Det
 * testværdige (regel 19): begge knapper skal kunne bruges direkte, i
 * vilkårlig rækkefølge, uden at den ene kræver at den anden er trykket
 * først — det er netop pointen, at der ikke er nogen gættet tilstand at
 * være "ude af trit" med.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { PlexPlayLink, PlexShieldPlayButton } from "./PlexAvailability";

const AVAILABLE = { available: true };

/**
 * Feature #178-opfølgning (Jan: "sæt op i users styring hvem kan se og
 * bruge vis iplex/spil i plex i detajle for film/tv"). Det testværdige
 * (regel 19): en bruger uden tilladelse skal se ABSOLUT intet — ikke en
 * deaktiveret knap, ikke en forklarende besked — adskilt fra det tekniske
 * "intet link kunne bygges"-tilfælde, som stadig skal vise sin besked når
 * brugeren rent faktisk har adgang.
 */
describe("PlexPlayLink — pr.-bruger adgang (feature #178-opfølgning)", () => {
  it("vises ikke overhovedet når playAllowed er false, selvom titlen er i Plex", () => {
    render(
      <PlexPlayLink
        availability={{ available: true, play_url: "https://plex.example/details" }}
        plex={{ status: "ready", playAllowed: false }}
      />
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByText(/Plex/)).not.toBeInTheDocument();
  });

  it("viser det normale afspil-link når playAllowed er true", () => {
    render(
      <PlexPlayLink
        availability={{ available: true, play_url: "https://plex.example/details" }}
        plex={{ status: "ready", playAllowed: true }}
      />
    );
    expect(screen.getByRole("link", { name: "▶ Afspil i Plex lokalt" })).toBeInTheDocument();
  });

  it("skelner stadig det tekniske 'intet link'-tilfælde fra manglende tilladelse", () => {
    render(
      <PlexPlayLink
        availability={{ available: true, play_url: null }}
        plex={{ status: "ready", playAllowed: true }}
      />
    );
    expect(
      screen.getByText("▶ Ligger i Plex (kunne ikke bygge afspilnings-link).")
    ).toBeInTheDocument();
  });
});

describe("PlexShieldPlayButton (feature #178)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("vises ikke når titlen ikke er i Plex", () => {
    render(
      <PlexShieldPlayButton
        availability={{ available: false }}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={true}
      />
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("vises ikke når Shield ikke er konfigureret, selvom titlen er i Plex", () => {
    render(
      <PlexShieldPlayButton
        availability={AVAILABLE}
        shieldConfigured={false}
        kind="movie"
        itemId="m1"
        isAdmin={true}
      />
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  /**
   * Jan, opfølgning 2026-08-18: "afspil på shield skal være en funktion som
   * kun er på admin users". Selvom alt andet er opfyldt (titlen er i Plex,
   * Shield er konfigureret), skal en ikke-admin slet ikke se knappen.
   */
  it("vises ikke for en ikke-admin, selvom titlen er i Plex og Shield er konfigureret", () => {
    render(
      <PlexShieldPlayButton
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={false}
      />
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  /**
   * Jan, opfølgning 2026-08-19: "hvis jeg disabler 'vis i plex' skal
   * 'afspil i plex også disablet, alt plex under detajle kort på film/tv
   * skal ikke være syndeligt hvis plex er disablet på user". En admin hvis
   * EGEN plex_play_enabled er slået fra skal heller ikke se Shield-knappen,
   * selvom de er admin og alt andet er opfyldt.
   */
  it("vises ikke når playAllowed er false, selvom brugeren er admin og alt andet er opfyldt", () => {
    render(
      <PlexShieldPlayButton
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={true}
        playAllowed={false}
      />
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("begge knapper er synlige med det samme, uden at kræve hinanden først", () => {
    render(
      <PlexShieldPlayButton
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={true}
      />
    );
    expect(screen.getByRole("button", { name: "📺 Afspil på Shield TV" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "⏹ Stop Shield TV" })).toBeEnabled();
  });

  it("'Afspil' sender kind/id og viser succes-beskeden, uden at ændre nogen af knapperne", async () => {
    const playSpy = vi
      .spyOn(api, "playOnShield")
      .mockResolvedValue({ ok: true, message: "Afspilning startet på Shield TV." });
    const user = userEvent.setup();

    render(
      <PlexShieldPlayButton
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="show"
        itemId="s1"
        isAdmin={true}
      />
    );

    await user.click(screen.getByRole("button", { name: "📺 Afspil på Shield TV" }));

    expect(playSpy).toHaveBeenCalledWith("show", "s1");
    expect(await screen.findByText("Afspilning startet på Shield TV.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "📺 Afspil på Shield TV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "⏹ Stop Shield TV" })).toBeInTheDocument();
  });

  it("'Stop' virker direkte, uden at 'Afspil' nogensinde er trykket først", async () => {
    const stopSpy = vi
      .spyOn(api, "stopShield")
      .mockResolvedValue({ ok: true, message: "Afspilning stoppet på Shield TV." });
    const user = userEvent.setup();

    render(
      <PlexShieldPlayButton
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={true}
      />
    );

    await user.click(screen.getByRole("button", { name: "⏹ Stop Shield TV" }));

    expect(stopSpy).toHaveBeenCalled();
    expect(await screen.findByText("Afspilning stoppet på Shield TV.")).toBeInTheDocument();
  });

  it("viser fejlbeskeden fra backend, hvis Shield ikke kan nås", async () => {
    vi.spyOn(api, "playOnShield").mockResolvedValue({
      ok: false,
      message: "Shield TV'et svarede ikke — er Plex-appen åben og tændt på den?",
    });
    const user = userEvent.setup();

    render(
      <PlexShieldPlayButton
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={true}
      />
    );

    await user.click(screen.getByRole("button", { name: "📺 Afspil på Shield TV" }));

    expect(
      await screen.findByText("Shield TV'et svarede ikke — er Plex-appen åben og tændt på den?")
    ).toBeInTheDocument();
  });

  it("deaktiverer BEGGE knapper mens én kommando er undervejs, for at undgå overlappende kald", async () => {
    let resolvePlay;
    vi.spyOn(api, "playOnShield").mockReturnValue(
      new Promise((resolve) => {
        resolvePlay = resolve;
      })
    );
    const user = userEvent.setup();

    render(
      <PlexShieldPlayButton
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={true}
      />
    );

    await user.click(screen.getByRole("button", { name: "📺 Afspil på Shield TV" }));

    expect(await screen.findByRole("button", { name: "Starter..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "⏹ Stop Shield TV" })).toBeDisabled();

    resolvePlay({ ok: true, message: "Afspilning startet på Shield TV." });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "📺 Afspil på Shield TV" })).toBeEnabled()
    );
    expect(screen.getByRole("button", { name: "⏹ Stop Shield TV" })).toBeEnabled();
  });

  it("viser fejlbeskeden hvis selve stop-kommandoen fejler", async () => {
    vi.spyOn(api, "stopShield").mockResolvedValue({
      ok: false,
      message: "Plex afviste stop-kommandoen (HTTP 500).",
    });
    const user = userEvent.setup();

    render(
      <PlexShieldPlayButton
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={true}
      />
    );

    await user.click(screen.getByRole("button", { name: "⏹ Stop Shield TV" }));

    expect(await screen.findByText("Plex afviste stop-kommandoen (HTTP 500).")).toBeInTheDocument();
  });
});
