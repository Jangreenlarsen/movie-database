/**
 * Feature #205 — siden et token-link fra forgot-password-mailen peger på.
 * Testværdigt (regel 19): manglende token vises som en klar fejl i stedet
 * for en tavs/knækket formular, en client-side password-mismatch fanges
 * FØR et unødvendigt API-kald, og backendens specifikke fejl (udløbet/brugt
 * token) vises frem for en generisk besked.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import ResetPassword from "./ResetPassword";

function withQuery(search) {
  const url = new URL(window.location.href);
  url.search = search;
  window.history.replaceState({}, "", url);
}

describe("ResetPassword (feature #205)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    withQuery("");
  });

  it("viser en fejl med det samme hvis linket mangler et token", () => {
    withQuery("");
    render(<ResetPassword />);
    expect(screen.getByText(/Linket mangler et gyldigt token/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Ny adgangskode")).not.toBeInTheDocument();
  });

  it("fanger et mismatch mellem de to felter uden at kalde backend", async () => {
    withQuery("?token=abc123");
    const user = userEvent.setup();
    vi.spyOn(api, "resetPassword");
    render(<ResetPassword />);

    await user.type(screen.getByLabelText("Ny adgangskode"), "mynewpassword1");
    await user.type(screen.getByLabelText("Gentag ny adgangskode"), "somethingelse2");
    await user.click(screen.getByRole("button", { name: "Skift adgangskode" }));

    expect(await screen.findByText("De to adgangskoder er ikke ens")).toBeInTheDocument();
    expect(api.resetPassword).not.toHaveBeenCalled();
  });

  it("sender token + ny adgangskode til backend og viser succesbeskeden", async () => {
    withQuery("?token=abc123");
    vi.spyOn(api, "resetPassword").mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ResetPassword />);

    await user.type(screen.getByLabelText("Ny adgangskode"), "mynewpassword1");
    await user.type(screen.getByLabelText("Gentag ny adgangskode"), "mynewpassword1");
    await user.click(screen.getByRole("button", { name: "Skift adgangskode" }));

    expect(await screen.findByText(/Din adgangskode er ændret/)).toBeInTheDocument();
    expect(api.resetPassword).toHaveBeenCalledWith("abc123", "mynewpassword1");
  });

  it("viser backendens specifikke fejl ved et udløbet/ugyldigt token", async () => {
    withQuery("?token=expired");
    vi.spyOn(api, "resetPassword").mockRejectedValue(
      new Error("Nulstillings-linket er ugyldigt eller udløbet. Anmod om et nyt.")
    );
    const user = userEvent.setup();
    render(<ResetPassword />);

    await user.type(screen.getByLabelText("Ny adgangskode"), "mynewpassword1");
    await user.type(screen.getByLabelText("Gentag ny adgangskode"), "mynewpassword1");
    await user.click(screen.getByRole("button", { name: "Skift adgangskode" }));

    expect(
      await screen.findByText("Nulstillings-linket er ugyldigt eller udløbet. Anmod om et nyt.")
    ).toBeInTheDocument();
  });
});
