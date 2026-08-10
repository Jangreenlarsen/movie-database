/**
 * Besked-banneret (feature #100) — første komponent-test, og dermed også
 * beviset på at render-opsætningen virker.
 *
 * Det interessante er ikke at teksten vises, men hvad der sker når lukningen
 * fejler: banneret skal blive stående. Forsvandt det lokalt, ville brugeren
 * tro han havde kvitteret, mens afsenderen stadig så beskeden som ulæst.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import MessageBanner from "./MessageBanner";

const MESSAGE = {
  id: "abc123",
  subject: "Visning fredag",
  body: "Kom kl. 19.",
  sent_by: "jgl",
  created_at: "2026-08-09T10:00:00Z",
};

describe("MessageBanner", () => {
  beforeEach(() => {
    vi.spyOn(api, "getInbox").mockResolvedValue([]);
    vi.spyOn(api, "markMessageRead").mockResolvedValue(null);
  });

  it("viser intet når indbakken er tom", async () => {
    const { container } = render(<MessageBanner />);
    await waitFor(() => expect(api.getInbox).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("viser emne, tekst og afsender", async () => {
    api.getInbox.mockResolvedValue([MESSAGE]);
    render(<MessageBanner />);

    expect(await screen.findByText("Visning fredag")).toBeInTheDocument();
    expect(screen.getByText("Kom kl. 19.")).toBeInTheDocument();
    expect(screen.getByText(/jgl/)).toBeInTheDocument();
  });

  it("markerer beskeden læst og fjerner den når man lukker", async () => {
    api.getInbox.mockResolvedValue([MESSAGE]);
    render(<MessageBanner />);
    await screen.findByText("Visning fredag");

    await userEvent.click(screen.getByRole("button", { name: /luk besked/i }));

    await waitFor(() => expect(api.markMessageRead).toHaveBeenCalledWith("abc123"));
    await waitFor(() => expect(screen.queryByText("Visning fredag")).not.toBeInTheDocument());
  });

  it("lader banneret blive stående hvis markeringen fejler", async () => {
    // Kernen: forsvandt banneret alligevel, ville brugeren tro han havde
    // kvitteret, mens afsenderen stadig så beskeden som ulæst.
    api.getInbox.mockResolvedValue([MESSAGE]);
    api.markMessageRead.mockRejectedValue(new Error("Netværksfejl"));
    render(<MessageBanner />);
    await screen.findByText("Visning fredag");

    await userEvent.click(screen.getByRole("button", { name: /luk besked/i }));

    await waitFor(() => expect(screen.getByText(/Netværksfejl/)).toBeInTheDocument());
    expect(screen.getByText("Visning fredag")).toBeInTheDocument();
  });

  it("viser ikke en fejl når selve indbakken ikke kan hentes", async () => {
    // En utilgængelig indbakke må ikke lægge sig oven på hele appen —
    // beskeden kommer ved næste sideindlæsning.
    api.getInbox.mockRejectedValue(new Error("Backend nede"));
    const { container } = render(<MessageBanner />);

    await waitFor(() => expect(api.getInbox).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("viser flere beskeder på én gang", async () => {
    api.getInbox.mockResolvedValue([
      MESSAGE,
      { ...MESSAGE, id: "def456", subject: "Ny film på hylden" },
    ]);
    render(<MessageBanner />);

    expect(await screen.findByText("Visning fredag")).toBeInTheDocument();
    expect(screen.getByText("Ny film på hylden")).toBeInTheDocument();
  });
});
