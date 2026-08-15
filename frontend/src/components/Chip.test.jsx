/**
 * Feature #156 — Chip fik en tredje visuel tilstand (`negated`, rød med
 * diagonal streg). Testen dækker den regression der allerede opstod én gang
 * under udviklingen: `aria-pressed={active || negated}` blev `undefined` (i
 * stedet for `false`) når `negated` slet ikke sendes med af ældre kaldere
 * som SubtitlesPicker, hvilket fjernede attributten helt frem for at sætte
 * den til "false" (regel 19 — silent-failure-prone logik).
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Chip from "./Chip";

describe("Chip", () => {
  it("er hverken aktiv eller negeret som udgangspunkt, uden negated-prop", () => {
    render(<Chip label="4K" onClick={() => {}} />);
    const chip = screen.getByRole("button", { name: "4K" });
    expect(chip).toHaveAttribute("aria-pressed", "false");
    expect(chip.className).not.toContain("chip-active");
    expect(chip.className).not.toContain("chip-negated");
  });

  it("viser inkluderet tilstand", () => {
    render(<Chip label="4K" active onClick={() => {}} />);
    const chip = screen.getByRole("button", { name: "4K" });
    expect(chip).toHaveAttribute("aria-pressed", "true");
    expect(chip.className).toContain("chip-active");
  });

  it("viser ekskluderet tilstand, og lader den vinde over active", () => {
    // active+negated samtidig bør ikke kunne ske i praksis (cycleFilterValue
    // sætter aldrig begge), men negated skal vinde defensivt hvis det gør.
    render(<Chip label="4K" active negated onClick={() => {}} />);
    const chip = screen.getByRole("button", { name: "4K" });
    expect(chip).toHaveAttribute("aria-pressed", "true");
    expect(chip.className).toContain("chip-negated");
    expect(chip.className).not.toContain("chip-active");
  });

  it("kalder onClick ved klik", async () => {
    const onClick = vi.fn();
    render(<Chip label="4K" onClick={onClick} />);
    screen.getByRole("button", { name: "4K" }).click();
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
