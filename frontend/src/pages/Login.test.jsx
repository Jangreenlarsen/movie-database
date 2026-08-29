/**
 * Feature #205 — selvbetjent "glemt adgangskode" erstatter #171's statiske
 * "kontakt Jan/Lis"-tekst med et rigtigt link + formular. Det testværdige
 * (regel 19, "tilstands-skift i et vindue"): linket skifter rent faktisk
 * til forgot-tilstanden, submit kalder det nye API-kald med den indtastede
 * adresse, og backendens specifikke fejlbesked vises (ikke en generisk).
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import Login from "./Login";

describe("Login — glemt adgangskode (feature #205)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function renderLogin() {
    return render(<Login onAuthenticated={() => {}} language="da" onLanguageChange={() => {}} />);
  }

  it("skifter til 'glemt adgangskode'-formularen og skjuler login-felterne", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("button", { name: "Glemt din adgangskode?" }));

    expect(screen.queryByLabelText("Brugernavn")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Adgangskode")).not.toBeInTheDocument();
    expect(screen.getByLabelText("E-mail")).toBeInTheDocument();
  });

  it("sender e-mailen til backend og viser bekræftelsesbeskeden", async () => {
    vi.spyOn(api, "forgotPassword").mockResolvedValue({
      message: "Hvis denne e-mail er registreret, har vi sendt et link til at nulstille adgangskoden.",
    });
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("button", { name: "Glemt din adgangskode?" }));
    await user.type(screen.getByLabelText("E-mail"), "mig@example.com");
    await user.click(screen.getByRole("button", { name: "Send nulstillingslink" }));

    expect(await screen.findByText(/Hvis denne e-mail er registreret/)).toBeInTheDocument();
    expect(api.forgotPassword).toHaveBeenCalledWith("mig@example.com");
  });

  it("viser backendens specifikke fejlbesked, ikke en generisk", async () => {
    vi.spyOn(api, "forgotPassword").mockRejectedValue(
      new Error("E-mail-udsendelse er ikke konfigureret på serveren endnu — kontakt en administrator.")
    );
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("button", { name: "Glemt din adgangskode?" }));
    await user.type(screen.getByLabelText("E-mail"), "mig@example.com");
    await user.click(screen.getByRole("button", { name: "Send nulstillingslink" }));

    expect(
      await screen.findByText("E-mail-udsendelse er ikke konfigureret på serveren endnu — kontakt en administrator.")
    ).toBeInTheDocument();
  });

  it("kan gå tilbage til login-formularen igen", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("button", { name: "Glemt din adgangskode?" }));
    await user.click(screen.getByRole("button", { name: "Tilbage til login" }));

    expect(screen.getByLabelText("Brugernavn")).toBeInTheDocument();
  });
});
