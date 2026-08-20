/**
 * Feature #176 (Jan: "når en guest eller standart user ønske en forvisning
 * i bio skal man afkraves at man også deffinere en dato og tidspunkt"). Det
 * testværdige (regel 19, "tilstands-skift i et vindue"): "Send ønske" skal
 * reelt forblive deaktiveret uden et valgt tidspunkt — ellers kunne et
 * ønske uden dato/tid stadig sendes fra UI'et, selvom backend nu afviser
 * det, og brugeren ville kun opdage det ved en fejlbesked i stedet for slet
 * ikke at kunne trykke "Send".
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import ScreeningRequestButton from "./ScreeningRequestButton";

function fillPreferredTime(container) {
  const dateInput = container.querySelector('input[type="date"]');
  fireEvent.change(dateInput, { target: { value: "2026-09-04" } });
  const [hourSelect, minuteSelect] = container.querySelectorAll("select");
  fireEvent.change(hourSelect, { target: { value: "20" } });
  fireEvent.change(minuteSelect, { target: { value: "00" } });
}

describe("ScreeningRequestButton (feature #176)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: true });
  });

  it('"Send ønske" er deaktiveret indtil et tidspunkt er valgt, aktiveres derefter', async () => {
    const user = userEvent.setup();
    const { container } = render(
      <ScreeningRequestButton mediaKind="movie" id="m1" username="testuser" />
    );

    await user.click(
      await screen.findByRole("button", { name: "🎬 Ønsk visning i Voldby BIO" })
    );
    const sendButton = screen.getByRole("button", { name: "Send ønske" });
    expect(sendButton).toBeDisabled();

    fillPreferredTime(container);
    expect(sendButton).toBeEnabled();
  });

  it("sender det valgte tidspunkt med, uden besked er stadig gyldigt", async () => {
    const requestSpy = vi.spyOn(api, "requestScreening").mockResolvedValue({
      requested_by: [{ username: "testuser", message: null, preferred_at: "2026-09-04T20:00:00" }],
    });
    const user = userEvent.setup();
    const { container } = render(
      <ScreeningRequestButton mediaKind="movie" id="m1" username="testuser" />
    );

    await user.click(
      await screen.findByRole("button", { name: "🎬 Ønsk visning i Voldby BIO" })
    );
    fillPreferredTime(container);
    await user.click(screen.getByRole("button", { name: "Send ønske" }));

    await waitFor(() =>
      expect(requestSpy).toHaveBeenCalledWith("movie", "m1", {
        message: "",
        preferredAt: "2026-09-04T20:00",
      })
    );
    expect(await screen.findByRole("button", { name: "✓ Ønsket til Voldby BIO" })).toBeInTheDocument();
  });
});

/**
 * Feature #177 gjorde kravet admin-styrbart, oprindeligt kun for gæster.
 * Feature #186 (Jan, 2026-08-20: "angivning af dato/tid for forvisning skal
 * gælde for alle roller og ikke kun guest") fjernede rolle-særbehandlingen
 * — politikken hentes og gælder nu ens uanset rolle, så disse tests kører
 * bevidst uden nogen `role`-prop overhovedet (komponenten tager ikke
 * længere imod én).
 */
describe("ScreeningRequestButton — politik gælder alle roller (feature #177/#186)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
  });

  it('politikken slået til: "Send ønske" er deaktiveret uden tidspunkt', async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at: true,
    });
    const user = userEvent.setup();
    render(<ScreeningRequestButton mediaKind="movie" id="m1" username="testuser" />);

    await user.click(
      await screen.findByRole("button", { name: "🎬 Ønsk visning i Voldby BIO" })
    );
    await waitFor(() => expect(api.getScreeningRequestPolicy).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: "Send ønske" })).toBeDisabled();
  });

  it('politikken slået fra: "Send ønske" er aktiveret uden tidspunkt', async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at: false,
    });
    const requestSpy = vi.spyOn(api, "requestScreening").mockResolvedValue({
      requested_by: [{ username: "testuser", message: null, preferred_at: null }],
    });
    const user = userEvent.setup();
    render(<ScreeningRequestButton mediaKind="movie" id="m1" username="testuser" />);

    await user.click(
      await screen.findByRole("button", { name: "🎬 Ønsk visning i Voldby BIO" })
    );
    const sendButton = await screen.findByRole("button", { name: "Send ønske" });
    await waitFor(() => expect(sendButton).toBeEnabled());

    await user.click(sendButton);
    await waitFor(() =>
      expect(requestSpy).toHaveBeenCalledWith("movie", "m1", { message: "", preferredAt: "" })
    );
  });

  it("politikken hentes og respekteres uanset hvilken rolle brugeren har (ingen guest-særbehandling længere)", async () => {
    // Feature #186's kerne-regressionstest: før fjernede komponenten
    // guest-særbehandlingen ved slet ikke at kalde politik-endpointet for
    // andre roller end guest, og standard/admin var altid ufravigeligt
    // krævet. Nu kaldes endpointet altid, og resultatet respekteres altid.
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at: false,
    });
    const user = userEvent.setup();
    render(<ScreeningRequestButton mediaKind="movie" id="m1" username="testuser" />);

    await user.click(
      await screen.findByRole("button", { name: "🎬 Ønsk visning i Voldby BIO" })
    );
    await waitFor(() => expect(api.getScreeningRequestPolicy).toHaveBeenCalled());
    expect(await screen.findByRole("button", { name: "Send ønske" })).toBeEnabled();
  });
});
