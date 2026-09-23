/**
 * Feature #227 — "Mine pladser". Det testværdige (regel 19): at afmelding
 * faktisk rammer de rigtige reservationer, at et fortrudt "Meld fra" ikke
 * gør noget, og at backendens egen fejltekst vises (regel 16).
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import MyReservationsButton, { MyReservationsModal } from "./MyReservations";

const ROWS = [
  {
    id: "r6",
    screening_id: "s1",
    seat_number: 6,
    status: "approved",
    screening_title: "Dune: Part Two",
    screening_at: "2099-09-26T19:30:00",
  },
  {
    id: "r7",
    screening_id: "s1",
    seat_number: 7,
    status: "pending",
    screening_title: "Dune: Part Two",
    screening_at: "2099-09-26T19:30:00",
  },
  {
    id: "r12",
    screening_id: "s2",
    seat_number: 12,
    status: "approved",
    screening_title: "Paddington i Peru",
    screening_at: "2099-10-11T16:00:00",
  },
];

describe("MyReservationsModal (feature #227)", () => {
  beforeEach(() => {
    vi.spyOn(api, "myReservations").mockResolvedValue(ROWS);
  });

  it("grupperer pladserne pr. visning med status", async () => {
    render(<MyReservationsModal onClose={() => {}} />);

    const dune = (await screen.findByText("Dune: Part Two")).closest("section");
    expect(within(dune).getByText("Sæde 6")).toBeInTheDocument();
    expect(within(dune).getByText("Sæde 7")).toBeInTheDocument();
    expect(within(dune).getByText("Godkendt")).toBeInTheDocument();
    expect(within(dune).getByText("Afventer konduktør")).toBeInTheDocument();
    expect(within(dune).getByText("2 pladser")).toBeInTheDocument();

    const paddington = screen.getByText("Paddington i Peru").closest("section");
    expect(within(paddington).getByText("1 plads")).toBeInTheDocument();
    // Én plads = ingen "meld fra alle"-knap.
    expect(within(paddington).queryByRole("button", { name: /alle/ })).toBeNull();
  });

  it("melder én plads fra efter bekræftelse", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const cancel = vi.spyOn(api, "cancelReservation").mockResolvedValue(null);
    const user = userEvent.setup();
    render(<MyReservationsModal onClose={() => {}} />);

    const paddington = (await screen.findByText("Paddington i Peru")).closest("section");
    await user.click(within(paddington).getByRole("button", { name: "Meld fra" }));

    expect(cancel).toHaveBeenCalledTimes(1);
    expect(cancel).toHaveBeenCalledWith("r12");
  });

  it("gør intet når bekræftelsen fortrydes", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const cancel = vi.spyOn(api, "cancelReservation").mockResolvedValue(null);
    const user = userEvent.setup();
    render(<MyReservationsModal onClose={() => {}} />);

    const paddington = (await screen.findByText("Paddington i Peru")).closest("section");
    await user.click(within(paddington).getByRole("button", { name: "Meld fra" }));

    expect(cancel).not.toHaveBeenCalled();
  });

  it('"Meld fra alle" rammer hver plads på visningen — og kun den visning', async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const cancel = vi.spyOn(api, "cancelReservation").mockResolvedValue(null);
    const user = userEvent.setup();
    render(<MyReservationsModal onClose={() => {}} />);

    await user.click(await screen.findByRole("button", { name: "Meld fra alle 2 pladser" }));

    expect(cancel.mock.calls.map(([id]) => id)).toEqual(["r6", "r7"]);
  });

  it("viser backendens egen fejltekst når afmelding fejler", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "cancelReservation").mockRejectedValue(
      new Error("Du kan kun annullere dine egne reservationer")
    );
    const user = userEvent.setup();
    render(<MyReservationsModal onClose={() => {}} />);

    const paddington = (await screen.findByText("Paddington i Peru")).closest("section");
    await user.click(within(paddington).getByRole("button", { name: "Meld fra" }));

    expect(
      await screen.findByText("Du kan kun annullere dine egne reservationer")
    ).toBeInTheDocument();
  });

  it("viser en tom-tilstand uden pladser", async () => {
    api.myReservations.mockResolvedValue([]);
    render(<MyReservationsModal onClose={() => {}} />);
    expect(await screen.findByText(/Du har ingen kommende pladser/)).toBeInTheDocument();
  });

  it("lukker på Escape", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<MyReservationsModal onClose={onClose} />);
    await screen.findByText("Dune: Part Two");
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});

describe("MyReservationsButton (feature #227)", () => {
  it("viser antal pladser som tal i hovedet", async () => {
    vi.spyOn(api, "myReservations").mockResolvedValue(ROWS);
    render(<MyReservationsButton />);
    expect(
      await screen.findByRole("button", { name: "Mine pladser — 3 pladser" })
    ).toBeInTheDocument();
  });

  it("viser intet tal uden pladser, og henter igen når en plads ændres et andet sted", async () => {
    const mine = vi.spyOn(api, "myReservations").mockResolvedValue([]);
    render(<MyReservationsButton />);
    expect(await screen.findByRole("button", { name: "Mine pladser" })).toBeInTheDocument();

    mine.mockResolvedValue([ROWS[0]]);
    window.dispatchEvent(new Event("reservations:changed"));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Mine pladser — 1 plads" })).toBeInTheDocument()
    );
  });
});
