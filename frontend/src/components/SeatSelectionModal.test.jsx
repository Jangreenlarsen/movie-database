/**
 * Feature #133 — sæde-vælgerens tilstands-logik. Det testværdige (regel 19):
 * hvert sædes backend-tilstand skal mappe til den rigtige klikbarhed (ledig =
 * klikbar, optaget/afventer = deaktiveret, din plads = klikbar for at
 * annullere), og et valgt sæde skal aktivere "Reservér" og sende de rigtige
 * sæde-id'er. Går mappingen galt, kan en gæst reservere et optaget sæde eller
 * slet ikke kunne vælge et ledigt — uden at build/lint fanger det.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import SeatSelectionModal from "./SeatSelectionModal";

function seatMapWith(overrides = {}) {
  const numbers = {
    "N1-1": 1, "N1-2": 2, "N1-3": 3, "N1-4": 4,
    "N2-1": 5, "N2-2": 6, "N2-3": 7, "N2-4": 8, "N2-5": 9,
    "N3-1": 10, "N3-2": 11, "N3-3": 12, "N3-4": 13, "N3-5": 14,
  };
  return {
    screening_id: "s1",
    seats: Object.entries(numbers).map(([seat_id, number]) => ({
      seat_id,
      number,
      status: "free",
      reservation_id: null,
      approved: null,
      ...(overrides[seat_id] ?? {}),
    })),
  };
}

const seatButton = (n) => screen.getByRole("button", { name: new RegExp(`^Sæde ${n} –`) });

describe("SeatSelectionModal (feature #133)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("mapper backend-tilstande til klikbarhed", async () => {
    vi.spyOn(api, "getSeatMap").mockResolvedValue(
      seatMapWith({
        "N1-2": { status: "mine", reservation_id: "r2", approved: false },
        "N1-3": { status: "taken" },
        "N1-4": { status: "pending" },
      })
    );
    render(<SeatSelectionModal screeningId="s1" screeningTitle="Testfilm" onClose={() => {}} />);

    await waitFor(() => expect(seatButton(1)).toBeInTheDocument());
    expect(seatButton(1)).toBeEnabled(); // ledig
    expect(seatButton(2)).toBeEnabled(); // din plads — klikbar (annullér)
    expect(seatButton(3)).toBeDisabled(); // optaget
    expect(seatButton(4)).toBeDisabled(); // afventer (andens)
  });

  it("valg af et ledigt sæde aktiverer Reservér og sender sæde-id'et", async () => {
    vi.spyOn(api, "getSeatMap").mockResolvedValue(seatMapWith());
    const reserve = vi
      .spyOn(api, "reserveSeats")
      .mockResolvedValue([{ seat_id: "N1-1", status: "pending" }]);
    const user = userEvent.setup();
    render(<SeatSelectionModal screeningId="s1" screeningTitle="Testfilm" onClose={() => {}} />);

    await waitFor(() => expect(seatButton(1)).toBeInTheDocument());

    // Før valg er Reservér deaktiveret.
    const reserveBtn = screen.getByRole("button", { name: /Reservér valgte/ });
    expect(reserveBtn).toBeDisabled();

    await user.click(seatButton(1));
    expect(seatButton(1)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Reservér valgte \(1\)/ })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: /Reservér valgte/ }));
    expect(reserve).toHaveBeenCalledWith("s1", ["N1-1"]);
  });

  it("fravalg fjerner sædet igen fra valget", async () => {
    vi.spyOn(api, "getSeatMap").mockResolvedValue(seatMapWith());
    const user = userEvent.setup();
    render(<SeatSelectionModal screeningId="s1" screeningTitle="Testfilm" onClose={() => {}} />);

    await waitFor(() => expect(seatButton(5)).toBeInTheDocument());
    await user.click(seatButton(5));
    expect(seatButton(5)).toHaveAttribute("aria-pressed", "true");
    await user.click(seatButton(5));
    expect(seatButton(5)).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: /Reservér valgte/ })).toBeDisabled();
  });
});
