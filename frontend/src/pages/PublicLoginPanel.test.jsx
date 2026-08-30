/**
 * Feature #205 — samme "glemt adgangskode"-flow som Login.jsx (se
 * Login.test.jsx for den fulde dækning af selve logikken), duplikeret ind i
 * den offentlige /bio-sides login-panel for parity (samme mønster som
 * e-mail-feltet, feature #200). Testet separat fordi duplikeret JSX er
 * netop den slags der nemt kan få en kopiér-fejl (forkert onClick, forkert
 * prop) uden at nogen opdager det med det samme (regel 19).
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { PublicLoginPanel } from "./CinemaPublic";

describe("PublicLoginPanel — glemt adgangskode (feature #205)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("skifter til 'glemt adgangskode' og sender e-mailen til backend", async () => {
    vi.spyOn(api, "forgotPassword").mockResolvedValue({
      message: "Hvis denne e-mail er registreret, har vi sendt et link til at nulstille adgangskoden.",
    });
    const user = userEvent.setup();
    render(<PublicLoginPanel language="da" onClose={() => {}} />);

    await user.click(screen.getByRole("button", { name: "Glemt din adgangskode?" }));
    await user.type(screen.getByLabelText("E-mail"), "mig@example.com");
    await user.click(screen.getByRole("button", { name: "Send nulstillingslink" }));

    expect(await screen.findByText(/Hvis denne e-mail er registreret/)).toBeInTheDocument();
    expect(api.forgotPassword).toHaveBeenCalledWith("mig@example.com");
  });

  it("kan gå tilbage til login-formularen igen", async () => {
    const user = userEvent.setup();
    render(<PublicLoginPanel language="da" onClose={() => {}} />);

    await user.click(screen.getByRole("button", { name: "Glemt din adgangskode?" }));
    await user.click(screen.getByRole("button", { name: "Tilbage til login" }));

    expect(screen.getByLabelText("Brugernavn")).toBeInTheDocument();
  });
});
