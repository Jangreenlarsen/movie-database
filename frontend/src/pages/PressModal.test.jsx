/**
 * Feature #210 (Jan, efter portal-opdateringen om afstemning/e-mail: "sæt
 * den ind på presse nyt siden i portal og giv den en dato") — "Presse Nyt"
 * gik fra ét fast nummer til to. Feature #211 udvidede videre: en dropdown
 * erstattede det oprindelige frem/tilbage-link ("dropdown list hvor man
 * vælger de forskelige presse opslag fra"), og det nye nummer fik billeder
 * ("der skal billeder med i den ny presse nyhed"). Det testværdige (regel
 * 19, "tilstands-skift i et vindue"): det nyeste nummer skal vises som
 * standard, dropdownen skal rent faktisk skifte visningen begge veje,
 * "Vis som PDF" må kun vises for det oprindelige nummer (kun det har en
 * ægte PDF bag sig), og billederne må kun vises for det nye nummer.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PressModal } from "./CinemaPublic";

describe("PressModal (feature #210/#211)", () => {
  it("viser det nyeste nummer som standard, med billeder og uden PDF-link", async () => {
    render(<PressModal onClose={() => {}} />);
    expect(await screen.findByText("Nu bestemmer biografgæsterne selv")).toBeInTheDocument();
    expect(screen.queryByText("Vis som PDF ↗")).not.toBeInTheDocument();
    expect(screen.getAllByRole("img")).toHaveLength(2);
  });

  it("skifter til det oprindelige nummer og tilbage igen via dropdownen", async () => {
    const user = userEvent.setup();
    render(<PressModal onClose={() => {}} />);
    await screen.findByText("Nu bestemmer biografgæsterne selv");

    const select = screen.getByRole("combobox", { name: "Vælg nummer" });
    await user.selectOptions(select, "Ny biograf åbner i Voldby (12. marts 2026)");

    expect(await screen.findByText("Ny biograf åbner i Voldby")).toBeInTheDocument();
    // Det oprindelige nummer har en ægte PDF bag sig, men ingen billeder.
    expect(screen.getByText("Vis som PDF ↗")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();

    await user.selectOptions(select, "Nu bestemmer biografgæsterne selv (29. august 2026)");
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
