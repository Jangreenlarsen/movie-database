/**
 * Feature #172 — tvunget adgangskodeskift efter en admin-nulstilling. Det
 * testværdige (regel 19, "tilstands-skift i et vindue"): et vellykket skift
 * skal rent faktisk hente den friske bruger og give den videre (ellers
 * forbliver appen i den blokerede tilstand på trods af at skiftet lykkedes),
 * og en fejl fra backend skal vises — ikke sluge sig selv og lade brugeren
 * stå uden forklaring, låst ude af hele appen.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import ForcePasswordChange from "./ForcePasswordChange";

const user172 = { id: "u1", username: "mustchange", must_change_password: true };

describe("ForcePasswordChange (feature #172)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("skifter adgangskoden og giver den friske bruger videre", async () => {
    vi.spyOn(api, "changeMyPassword").mockResolvedValue(null);
    const refreshedUser = { ...user172, must_change_password: false };
    vi.spyOn(api, "me").mockResolvedValue(refreshedUser);
    const onPasswordChanged = vi.fn();
    const user = userEvent.setup();

    render(
      <ForcePasswordChange user={user172} onPasswordChanged={onPasswordChanged} onLogout={() => {}} />
    );

    await user.type(screen.getByLabelText("Nuværende adgangskode"), "temp-code-123");
    await user.type(screen.getByLabelText("Ny adgangskode"), "myOwnNewPassword1");
    await user.click(screen.getByRole("button", { name: "Skift adgangskode" }));

    await waitFor(() => expect(onPasswordChanged).toHaveBeenCalledWith(refreshedUser));
    expect(api.changeMyPassword).toHaveBeenCalledWith("temp-code-123", "myOwnNewPassword1");
  });

  it("viser backend-fejlbeskeden og giver ikke brugeren videre", async () => {
    vi.spyOn(api, "changeMyPassword").mockRejectedValue(new Error("Forkert nuværende adgangskode"));
    const onPasswordChanged = vi.fn();
    const user = userEvent.setup();

    render(
      <ForcePasswordChange user={user172} onPasswordChanged={onPasswordChanged} onLogout={() => {}} />
    );

    await user.type(screen.getByLabelText("Nuværende adgangskode"), "wrong-code");
    await user.type(screen.getByLabelText("Ny adgangskode"), "myOwnNewPassword1");
    await user.click(screen.getByRole("button", { name: "Skift adgangskode" }));

    expect(await screen.findByText("Forkert nuværende adgangskode")).toBeInTheDocument();
    expect(onPasswordChanged).not.toHaveBeenCalled();
  });

  it("logout-knappen kalder onLogout uden at kræve et skift først", async () => {
    const onLogout = vi.fn();
    const user = userEvent.setup();
    render(<ForcePasswordChange user={user172} onPasswordChanged={() => {}} onLogout={onLogout} />);

    await user.click(screen.getByRole("button", { name: "Log ud" }));
    expect(onLogout).toHaveBeenCalled();
  });
});
