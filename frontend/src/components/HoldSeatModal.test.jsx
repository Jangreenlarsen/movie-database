/**
 * Feature #231 — admins for-reservér-vindue med den grafiske sal. Det
 * testværdige (regel 19): hvilke sæder der er optaget afhænger af det valgte
 * omfang, flere sæder sendes som hver sit hold med det rigtige omfang, og en
 * afvisning fra backend vises med backendens egen tekst.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import HoldSeatModal from "./HoldSeatModal";

const SEATS = [
  { id: "N1-1", number: 1 }, { id: "N1-2", number: 2 }, { id: "N1-3", number: 3 },
  { id: "N1-4", number: 4 }, { id: "N2-1", number: 5 }, { id: "N2-2", number: 6 },
  { id: "N2-3", number: 7 }, { id: "N2-4", number: 8 }, { id: "N2-5", number: 9 },
  { id: "N3-1", number: 10 }, { id: "N3-2", number: 11 }, { id: "N3-3", number: 12 },
  { id: "N3-4", number: 13 }, { id: "N3-5", number: 14 },
];

const SCREENINGS = [
  { id: "s1", title: "Project Hail Mary", scheduled_at: "2099-09-26T19:00:00" },
  { id: "s2", title: "Dune", scheduled_at: "2099-10-03T19:00:00" },
];

const RESERVATIONS = [
  // Jgl på sæde 7 til s1 — optaget for s1 og for et globalt hold, ikke for s2.
  { seat_id: "N2-3", scope: "screening", screening_id: "s1", status: "approved" },
  // Lis' faste sæde 4 — optaget overalt.
  { seat_id: "N1-4", scope: "global", screening_id: null, status: "approved", is_hold: true },
];

const seatButton = (n) => screen.getByRole("button", { name: new RegExp(`^Sæde ${n} –`) });

function renderModal(onChanged = vi.fn().mockResolvedValue(undefined)) {
  render(
    <HoldSeatModal
      seats={SEATS}
      screenings={SCREENINGS}
      reservations={RESERVATIONS}
      onClose={() => {}}
      onChanged={onChanged}
    />
  );
  return onChanged;
}

describe("HoldSeatModal (feature #231)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("alle visninger: ethvert sæde med en reservation er optaget", () => {
    renderModal();
    expect(seatButton(4)).toBeDisabled();
    expect(seatButton(7)).toBeDisabled();
    expect(seatButton(1)).toBeEnabled();
  });

  it("én visning: kun visningens egne og faste sæder er optaget", async () => {
    renderModal();
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Gælder"), "screening");

    // Ingen visning valgt endnu → intet kan vælges.
    expect(seatButton(1)).toBeDisabled();
    expect(screen.getByText("Vælg først en visning.")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Visning"), "s2");
    expect(seatButton(7)).toBeEnabled();
    expect(seatButton(4)).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Visning"), "s1");
    expect(seatButton(7)).toBeDisabled();
  });

  it("for-reserverer flere valgte sæder med det valgte omfang", async () => {
    const hold = vi.spyOn(api, "holdSeat").mockResolvedValue({});
    const onChanged = renderModal();
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Gælder"), "screening");
    await user.selectOptions(screen.getByLabelText("Visning"), "s2");

    await user.click(seatButton(2));
    await user.click(seatButton(1));
    await user.click(screen.getByRole("button", { name: "For-reservér 2 sæder" }));

    await waitFor(() => expect(hold).toHaveBeenCalledTimes(2));
    expect(hold).toHaveBeenNthCalledWith(1, { seat_id: "N1-1", scope: "screening", screening_id: "s2" });
    expect(hold).toHaveBeenNthCalledWith(2, { seat_id: "N1-2", scope: "screening", screening_id: "s2" });
    expect(await screen.findByText("2 sæder er for-reserveret.")).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalled();
  });

  it("et globalt hold sendes uden screening_id", async () => {
    const hold = vi.spyOn(api, "holdSeat").mockResolvedValue({});
    renderModal();
    const user = userEvent.setup();
    await user.click(seatButton(14));
    await user.click(screen.getByRole("button", { name: "For-reservér 1 sæde" }));
    await waitFor(() => expect(hold).toHaveBeenCalledWith({ seat_id: "N3-5", scope: "global" }));
  });

  it("viser backendens fejltekst og stopper ved første afvisning", async () => {
    const hold = vi
      .spyOn(api, "holdSeat")
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new Error("Sæde 3 er allerede optaget — vælg et andet."));
    const onChanged = renderModal();
    const user = userEvent.setup();
    await user.click(seatButton(1));
    await user.click(seatButton(3));
    await user.click(seatButton(5));
    await user.click(screen.getByRole("button", { name: "For-reservér 3 sæder" }));

    expect(await screen.findByText("Sæde 3 er allerede optaget — vælg et andet.")).toBeInTheDocument();
    expect(hold).toHaveBeenCalledTimes(2);
    // Det ene der gik igennem, udløser stadig en genindlæsning.
    expect(onChanged).toHaveBeenCalled();
    // Sæde 3 og 5 står stadig valgt, så admin kan prøve igen.
    expect(screen.getByRole("button", { name: "For-reservér 2 sæder" })).toBeInTheDocument();
  });
});
