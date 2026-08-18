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

describe("ScreeningRequestButton — gæste-specifik politik (feature #177)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
  });

  it('gæst med politikken slået til: "Send ønske" er stadig deaktiveret uden tidspunkt', async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at_for_guests: true,
    });
    const user = userEvent.setup();
    render(<ScreeningRequestButton mediaKind="movie" id="m1" username="testuser" role="guest" />);

    await user.click(
      await screen.findByRole("button", { name: "🎬 Ønsk visning i Voldby BIO" })
    );
    await waitFor(() => expect(api.getScreeningRequestPolicy).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: "Send ønske" })).toBeDisabled();
  });

  it('gæst med politikken slået fra: "Send ønske" er aktiveret uden tidspunkt', async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at_for_guests: false,
    });
    const requestSpy = vi.spyOn(api, "requestScreening").mockResolvedValue({
      requested_by: [{ username: "testuser", message: null, preferred_at: null }],
    });
    const user = userEvent.setup();
    render(<ScreeningRequestButton mediaKind="movie" id="m1" username="testuser" role="guest" />);

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

  it("standard-bruger er upåvirket af gæste-politikken, selv når den er slået fra", async () => {
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({
      require_preferred_at_for_guests: false,
    });
    const user = userEvent.setup();
    render(<ScreeningRequestButton mediaKind="movie" id="m1" username="testuser" role="standard" />);

    await user.click(
      await screen.findByRole("button", { name: "🎬 Ønsk visning i Voldby BIO" })
    );
    expect(api.getScreeningRequestPolicy).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Send ønske" })).toBeDisabled();
  });
});
