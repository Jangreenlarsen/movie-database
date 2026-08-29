/**
 * Feature #210 (Jan, efter portal-opdateringen om afstemning/e-mail: "sæt
 * den ind på presse nyt siden i portal og giv den en dato") — "Presse Nyt"
 * gik fra ét fast nummer til to. Det testværdige (regel 19, "tilstands-
 * skift i et vindue"): det nyeste nummer skal vises som standard, linket
 * til det andet nummer skal rent faktisk skifte visningen begge veje, og
 * "Vis som PDF" må kun vises for det oprindelige nummer (kun det har en
 * ægte PDF bag sig) — ikke for det nye.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PressModal } from "./CinemaPublic";

describe("PressModal (feature #210)", () => {
  it("viser det nyeste nummer som standard", async () => {
    render(<PressModal onClose={() => {}} />);
    expect(await screen.findByText("Nu bestemmer biografgæsterne selv")).toBeInTheDocument();
  });

  it("viser ikke 'Vis som PDF' for det nyeste nummer", async () => {
    render(<PressModal onClose={() => {}} />);
    await screen.findByText("Nu bestemmer biografgæsterne selv");
    expect(screen.queryByText("Vis som PDF ↗")).not.toBeInTheDocument();
  });

  it("skifter til det oprindelige nummer og tilbage igen", async () => {
    const user = userEvent.setup();
    render(<PressModal onClose={() => {}} />);

    await user.click(await screen.findByText(/Tidligere: Ny biograf åbner i Voldby/));
    expect(await screen.findByText("Ny biograf åbner i Voldby")).toBeInTheDocument();
    // Det oprindelige nummer har en ægte PDF bag sig.
    expect(screen.getByText("Vis som PDF ↗")).toBeInTheDocument();

    await user.click(screen.getByText("← Tilbage til seneste nummer"));
    expect(await screen.findByText("Nu bestemmer biografgæsterne selv")).toBeInTheDocument();
  });

  it("lukker modalen ved klik på Tilbage", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<PressModal onClose={onClose} />);

    await user.click(await screen.findByRole("button", { name: "← Tilbage" }));
    expect(onClose).toHaveBeenCalled();
  });
});
