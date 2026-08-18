/**
 * Feature #178 (Jan: "når man trykker på vis i plex så er option at starte
 * den i plex på shield der også"). Det testværdige (regel 19,
 * "tilstands-skift i et vindue"): knappen skal kun vises når titlen rent
 * faktisk er i Plex OG en Shield er konfigureret, og resultatet af et klik
 * (succes/fejl) skal faktisk vises, ikke sluges.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { PlexShieldPlayButton } from "./PlexAvailability";

const AVAILABLE = { available: true };

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
      />
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("sender kind/id og viser succes-beskeden fra backend", async () => {
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
      />
    );

    await user.click(screen.getByRole("button", { name: "📺 Afspil på Shield TV" }));

    expect(playSpy).toHaveBeenCalledWith("show", "s1");
    expect(await screen.findByText("Afspilning startet på Shield TV.")).toBeInTheDocument();
  });

  it("viser fejlbeskeden fra backend, når Shield ikke kan nås", async () => {
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
      />
    );

    await user.click(screen.getByRole("button", { name: "📺 Afspil på Shield TV" }));

    expect(
      await screen.findByText("Shield TV'et svarede ikke — er Plex-appen åben og tændt på den?")
    ).toBeInTheDocument();
  });

  it("deaktiverer knappen mens kommandoen sendes", async () => {
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
      />
    );

    const button = screen.getByRole("button", { name: "📺 Afspil på Shield TV" });
    await user.click(button);

    expect(await screen.findByRole("button", { name: "Starter..." })).toBeDisabled();

    resolvePlay({ ok: true, message: "Afspilning startet på Shield TV." });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "📺 Afspil på Shield TV" })).toBeEnabled()
    );
  });
});
