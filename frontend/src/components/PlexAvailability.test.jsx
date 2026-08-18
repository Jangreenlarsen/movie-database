/**
 * Feature #178 (Jan: "når man trykker på vis i plex så er option at starte
 * den i plex på shield der også"), opfølgning-kæde (Jan: "afspil på shield
 * skal være en funktion som kun er på admin users", derefter — efter at en
 * direkte playMedia-kommando transcodede video/lyd — "er det muligt så at
 * hoppe ind i plex klienten der hvor man skal til at trykke på play ... og
 * af den vej få spillet film med de local settings for klient der måtte
 * være"). Det testværdige (regel 19, "tilstands-skift i et vindue"):
 * knapperne skal kun vises for admin når titlen rent faktisk er i Plex OG en
 * Shield er konfigureret, resultatet af hvert klik (succes/fejl) skal
 * faktisk vises, og "Vis"/"Stop" er nu to uafhængige handlinger — ikke
 * længere én toggle der antager en kendt "afspiller nu"-tilstand.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { PlexShieldControls } from "./PlexAvailability";

const AVAILABLE = { available: true };

describe("PlexShieldControls (feature #178)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("vises ikke når titlen ikke er i Plex", () => {
    render(
      <PlexShieldControls
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
      <PlexShieldControls
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
   * Jan: "afspil på shield skal være en funktion som kun er på admin
   * users". Selvom alt andet er opfyldt, skal en ikke-admin slet ikke se
   * knapperne.
   */
  it("vises ikke for en ikke-admin, selvom titlen er i Plex og Shield er konfigureret", () => {
    render(
      <PlexShieldControls
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={false}
      />
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it('viser begge knapper: "Vis på Shield TV" og "Stop Shield TV"', () => {
    render(
      <PlexShieldControls
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={true}
      />
    );
    expect(screen.getByRole("button", { name: "📺 Vis på Shield TV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "⏹ Stop Shield TV" })).toBeInTheDocument();
  });

  it("'Vis på Shield TV' sender kind/id og viser succes-beskeden fra backend", async () => {
    const showSpy = vi.spyOn(api, "playOnShield").mockResolvedValue({
      ok: true,
      message: "Åbnet på Shield TV — tryk Afspil på fjernbetjeningen.",
    });
    const user = userEvent.setup();

    render(
      <PlexShieldControls
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="show"
        itemId="s1"
        isAdmin={true}
      />
    );

    await user.click(screen.getByRole("button", { name: "📺 Vis på Shield TV" }));

    expect(showSpy).toHaveBeenCalledWith("show", "s1");
    expect(
      await screen.findByText("Åbnet på Shield TV — tryk Afspil på fjernbetjeningen.")
    ).toBeInTheDocument();
    // Begge knapper står stadig — det er ikke en toggle, "Vis" kan bruges igen.
    expect(screen.getByRole("button", { name: "📺 Vis på Shield TV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "⏹ Stop Shield TV" })).toBeInTheDocument();
  });

  it("'Vis på Shield TV' viser fejlbeskeden fra backend, når Shield ikke kan nås", async () => {
    vi.spyOn(api, "playOnShield").mockResolvedValue({
      ok: false,
      message: "Shield TV'et svarede ikke — er Plex-appen åben og tændt på den?",
    });
    const user = userEvent.setup();

    render(
      <PlexShieldControls
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={true}
      />
    );

    await user.click(screen.getByRole("button", { name: "📺 Vis på Shield TV" }));

    expect(
      await screen.findByText("Shield TV'et svarede ikke — er Plex-appen åben og tændt på den?")
    ).toBeInTheDocument();
  });

  it("deaktiverer begge knapper mens 'Vis'-kommandoen sendes", async () => {
    let resolveShow;
    vi.spyOn(api, "playOnShield").mockReturnValue(
      new Promise((resolve) => {
        resolveShow = resolve;
      })
    );
    const user = userEvent.setup();

    render(
      <PlexShieldControls
        availability={AVAILABLE}
        shieldConfigured={true}
        kind="movie"
        itemId="m1"
        isAdmin={true}
      />
    );

    await user.click(screen.getByRole("button", { name: "📺 Vis på Shield TV" }));

    expect(await screen.findByRole("button", { name: "Åbner..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "⏹ Stop Shield TV" })).toBeDisabled();

    resolveShow({ ok: true, message: "Åbnet på Shield TV — tryk Afspil på fjernbetjeningen." });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "📺 Vis på Shield TV" })).toBeEnabled()
    );
  });

  it("'Stop Shield TV' virker uafhængigt af 'Vis' og viser succes-beskeden", async () => {
    const stopSpy = vi
      .spyOn(api, "stopShield")
      .mockResolvedValue({ ok: true, message: "Afspilning stoppet på Shield TV." });
    const user = userEvent.setup();

    render(
      <PlexShieldControls
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

  it("'Stop Shield TV' viser fejlbeskeden, hvis stop-kommandoen fejler", async () => {
    vi.spyOn(api, "stopShield").mockResolvedValue({
      ok: false,
      message: "Plex afviste stop-kommandoen (HTTP 500).",
    });
    const user = userEvent.setup();

    render(
      <PlexShieldControls
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
