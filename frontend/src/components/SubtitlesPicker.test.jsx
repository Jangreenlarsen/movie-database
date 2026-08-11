/**
 * Feature #123 — undertekst-vælgeren. Det interessante er ikke at chips'ene
 * vises, men tilstands-logikken: den frie "Andet"-tekst og de faste valg skal
 * ende i én liste i rigtig rækkefølge, og en post der åbnes med eksisterende
 * fritekst skal genskabe "Andet"-feltet. Går det galt, gemmer man tavst en
 * forkert undertekst-liste (regel 19).
 */

import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import SubtitlesPicker from "./SubtitlesPicker";

/** Kontrolleret wrapper — komponenten ejer ikke selv sin værdi. */
function Harness({ initial = [], options = ["Eng", "DK"] }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <SubtitlesPicker value={value} onChange={setValue} options={options} />
      <output data-testid="value">{JSON.stringify(value)}</output>
    </>
  );
}

const current = () => JSON.parse(screen.getByTestId("value").textContent);

describe("SubtitlesPicker", () => {
  it("markerer de faste valg der allerede er i værdien", () => {
    render(<Harness initial={["DK"]} />);
    expect(screen.getByRole("button", { name: "DK" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Eng" })).toHaveAttribute("aria-pressed", "false");
  });

  it("tilføjer og fjerner et fast valg", async () => {
    render(<Harness initial={[]} />);
    await userEvent.click(screen.getByRole("button", { name: "Eng" }));
    expect(current()).toEqual(["Eng"]);
    await userEvent.click(screen.getByRole("button", { name: "DK" }));
    expect(current()).toEqual(["Eng", "DK"]);
    await userEvent.click(screen.getByRole("button", { name: "Eng" }));
    expect(current()).toEqual(["DK"]);
  });

  it("bevarer options-rækkefølgen uanset klik-rækkefølge", async () => {
    render(<Harness initial={[]} />);
    await userEvent.click(screen.getByRole("button", { name: "DK" }));
    await userEvent.click(screen.getByRole("button", { name: "Eng" }));
    // Klikket DK først, men options er ["Eng","DK"] → Eng skal stå først.
    expect(current()).toEqual(["Eng", "DK"]);
  });

  it("åbner et fritekst-felt når Andet vælges, og tilføjer det efter de faste", async () => {
    render(<Harness initial={["DK"]} />);
    expect(screen.queryByPlaceholderText(/Norsk/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Andet" }));
    const input = screen.getByPlaceholderText(/Norsk/);
    await userEvent.type(input, "Norsk, Fransk");
    expect(current()).toEqual(["DK", "Norsk", "Fransk"]);
  });

  it("genskaber Andet-feltet fra eksisterende fritekst i værdien", () => {
    render(<Harness initial={["Eng", "Fastbrændt DA"]} />);
    expect(screen.getByRole("button", { name: "Andet" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByPlaceholderText(/Norsk/)).toHaveValue("Fastbrændt DA");
  });

  it("fjerner fritekst-posterne igen når Andet slås fra", async () => {
    render(<Harness initial={["DK", "Norsk"]} />);
    await userEvent.click(screen.getByRole("button", { name: "Andet" }));
    expect(current()).toEqual(["DK"]);
    expect(screen.queryByPlaceholderText(/Norsk/)).not.toBeInTheDocument();
  });
});
