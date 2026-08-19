/**
 * Feature #178 (Jan: "når man trykker på vis i plex så er option at starte
 * den i plex på shield der også"), opfølgning (Jan: "lave dem toggle bar
 * sådan at når man trykker på dem så ændre knap sig fra 'play start' til
 * 'play stop'"). Det testværdige (regel 19, "tilstands-skift i et vindue"):
 * knappen skal kun vises når titlen rent faktisk er i Plex OG en Shield er
 * konfigureret, resultatet af et klik (succes/fejl) skal faktisk vises, og
 * selve toggle-overgangen (start → stop → start) skal reelt fungere, ikke
 * kun se rigtig ud efter det første klik.
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
    expect(screen.getByRole("link", { name: "▶ Afspil i Plex" })).toBeInTheDocument();
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

  it("sender kind/id, viser succes-beskeden og skifter knappen til 'Stop'", async () => {
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
    expect(screen.getByRole("button", { name: "⏹ Stop Shield TV" })).toBeInTheDocument();
  });

  it("viser fejlbeskeden fra backend og forbliver på 'Afspil', når Shield ikke kan nås", async () => {
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
    // Startede aldrig reelt — knappen skal ikke lade som om den nu kan stoppes.
    expect(screen.getByRole("button", { name: "📺 Afspil på Shield TV" })).toBeInTheDocument();
  });

  it("deaktiverer knappen mens 'afspil'-kommandoen sendes", async () => {
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

    const button = screen.getByRole("button", { name: "📺 Afspil på Shield TV" });
    await user.click(button);

    expect(await screen.findByRole("button", { name: "Starter..." })).toBeDisabled();

    resolvePlay({ ok: true, message: "Afspilning startet på Shield TV." });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "⏹ Stop Shield TV" })).toBeEnabled()
    );
  });

  it("kan stoppe igen efter start, og vender tilbage til 'Afspil'", async () => {
    vi.spyOn(api, "playOnShield").mockResolvedValue({
      ok: true,
      message: "Afspilning startet på Shield TV.",
    });
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

    await user.click(screen.getByRole("button", { name: "📺 Afspil på Shield TV" }));
    const stopButton = await screen.findByRole("button", { name: "⏹ Stop Shield TV" });

    await user.click(stopButton);

    expect(stopSpy).toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "📺 Afspil på Shield TV" })).toBeInTheDocument()
    );
    // Vellykket stop rydder beskeden — ingen gammel "startet"-tekst skal blive hængende.
    expect(screen.queryByText("Afspilning startet på Shield TV.")).not.toBeInTheDocument();
  });

  it("forbliver på 'Stop' og viser fejlbeskeden, hvis selve stop-kommandoen fejler", async () => {
    vi.spyOn(api, "playOnShield").mockResolvedValue({
      ok: true,
      message: "Afspilning startet på Shield TV.",
    });
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

    await user.click(screen.getByRole("button", { name: "📺 Afspil på Shield TV" }));
    await user.click(await screen.findByRole("button", { name: "⏹ Stop Shield TV" }));

    expect(await screen.findByText("Plex afviste stop-kommandoen (HTTP 500).")).toBeInTheDocument();
    // Stoppet fejlede — knappen skal stadig tilbyde at prøve stop igen, ikke
    // falde tilbage til "Afspil" og risikere at sende endnu en playMedia.
    expect(screen.getByRole("button", { name: "⏹ Stop Shield TV" })).toBeInTheDocument();
  });
});
