/**
 * Feature #227 — admins "Tilmeldte pr. visning". Testet: tilføj sender
 * brugernavnet med (booking på vegne af), kun ledige sæder kan vælges, og
 * "Ryd alle" kræver bekræftelse.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { AttendeesAdmin } from "./Cinema";

const SCREENINGS = [
  { id: "later", title: "Alien: Romulus", scheduled_at: "2099-10-24T21:00:00" },
  { id: "next", title: "Dune: Part Two", scheduled_at: "2099-09-26T19:30:00" },
];

const RESERVATIONS = [
  {
    id: "r1",
    screening_id: "next",
    seat_id: "N1-1",
    seat_number: 1,
    scope: "screening",
    status: "approved",
    is_hold: false,
    reserved_by: "mette",
  },
  {
    id: "r7",
    screening_id: "next",
    seat_id: "N2-3",
    seat_number: 7,
    scope: "screening",
    status: "pending",
    is_hold: false,
    reserved_by: "jan",
  },
  {
    id: "hold",
    screening_id: null,
    seat_id: "N3-5",
    seat_number: 14,
    scope: "global",
    status: "approved",
    is_hold: true,
    reserved_by: "admin",
  },
];

function renderPanel(onChanged = vi.fn().mockResolvedValue(undefined)) {
  render(
    <AttendeesAdmin
      screenings={SCREENINGS}
      reservations={RESERVATIONS}
      status="ready"
      onChanged={onChanged}
    />
  );
  return onChanged;
}

function openBlock() {
  // Den næste visning (Dune) er foldet ud fra start — tidligst først.
  return screen.getByText("Dune: Part Two").closest(".cinema-attendees-block");
}

describe("AttendeesAdmin (feature #227)", () => {
  beforeEach(() => {
    vi.spyOn(api, "listUsers").mockResolvedValue([
      { id: "u1", username: "anna", status: "active" },
      { id: "u2", username: "peter", status: "active" },
      { id: "u3", username: "spaerret", status: "disabled" },
    ]);
  });

  it("folder den næste visning ud og viser dens tilmeldte", async () => {
    renderPanel();
    const block = openBlock();
    expect(within(block).getByText("mette")).toBeInTheDocument();
    expect(within(block).getByText("jan")).toBeInTheDocument();
    // 2 på visningen + det globale hold = 3 af 14.
    expect(within(block).getByText("3 af 14 sæder booket")).toBeInTheDocument();
    // Den senere visning er foldet sammen.
    expect(screen.getByRole("button", { name: "Vis og redigér" })).toBeInTheDocument();
  });

  it("tilbyder kun aktive brugere og ledige sæder", async () => {
    renderPanel();
    const block = openBlock();
    const [userSelect, seatSelect] = within(block).getAllByRole("combobox");

    await within(userSelect).findByRole("option", { name: "anna" });
    expect(within(userSelect).queryByRole("option", { name: "spaerret" })).toBeNull();

    const seatNames = within(seatSelect)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(seatNames).not.toContain("Sæde 1");
    expect(seatNames).not.toContain("Sæde 7");
    expect(seatNames).not.toContain("Sæde 14");
    expect(seatNames).toContain("Sæde 2");
  });

  it("tilføjer en bruger på vegne af dem", async () => {
    const reserve = vi.spyOn(api, "reserveSeats").mockResolvedValue([]);
    const onChanged = renderPanel();
    const user = userEvent.setup();
    const block = openBlock();
    const [userSelect, seatSelect] = within(block).getAllByRole("combobox");
    const addButton = within(block).getByRole("button", { name: "Tilføj tilmeldt" });
    expect(addButton).toBeDisabled();

    await within(userSelect).findByRole("option", { name: "anna" });
    await user.selectOptions(userSelect, "anna");
    await user.selectOptions(seatSelect, "N1-2");
    await user.click(addButton);

    expect(reserve).toHaveBeenCalledWith("next", ["N1-2"], "anna");
    expect(onChanged).toHaveBeenCalled();
  });

  it("viser backendens fejltekst når tilføjelse afvises", async () => {
    vi.spyOn(api, "reserveSeats").mockRejectedValue(
      new Error("Sæde 2 er allerede optaget — vælg et andet.")
    );
    renderPanel();
    const user = userEvent.setup();
    const block = openBlock();
    const [userSelect, seatSelect] = within(block).getAllByRole("combobox");
    await within(userSelect).findByRole("option", { name: "anna" });
    await user.selectOptions(userSelect, "anna");
    await user.selectOptions(seatSelect, "N1-2");
    await user.click(within(block).getByRole("button", { name: "Tilføj tilmeldt" }));

    expect(
      await within(block).findByText("Sæde 2 er allerede optaget — vælg et andet.")
    ).toBeInTheDocument();
  });

  it('"Ryd alle tilmeldte" kræver bekræftelse', async () => {
    const clear = vi.spyOn(api, "clearScreeningReservations").mockResolvedValue({ removed: 2 });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderPanel();
    const user = userEvent.setup();
    const block = openBlock();

    await user.click(within(block).getByRole("button", { name: "Ryd alle tilmeldte" }));
    expect(clear).not.toHaveBeenCalled();

    confirm.mockReturnValue(true);
    await user.click(within(block).getByRole("button", { name: "Ryd alle tilmeldte" }));
    expect(clear).toHaveBeenCalledWith("next");
  });

  it("godkender en afventende og fjerner en enkelt", async () => {
    const approve = vi.spyOn(api, "approveReservation").mockResolvedValue({});
    const cancel = vi.spyOn(api, "cancelReservation").mockResolvedValue(null);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPanel();
    const user = userEvent.setup();
    const block = openBlock();

    await user.click(within(block).getByRole("button", { name: "Godkend" }));
    expect(approve).toHaveBeenCalledWith("r7");

    await user.click(within(block).getAllByRole("button", { name: "Fjern" })[0]);
    expect(cancel).toHaveBeenCalledWith("r1");
  });
});
