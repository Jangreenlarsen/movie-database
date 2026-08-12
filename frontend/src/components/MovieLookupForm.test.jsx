/**
 * Feature #124 — ønskelistens to store knapper åbner scan og titel-søgning
 * hver for sig, så den manuelle titel-søgning ikke forveksles med bibliotekets
 * generelle søgning. Det testværdige er `mode`-styringen: kun det rette kort
 * må vises, og scan→titel-fallbacken skal kunne skifte kort. Går det galt,
 * ser man to søgefelter igen — præcis det denne feature fjernede (regel 19).
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import MovieLookupForm from "./MovieLookupForm";

// Kameraet kan ikke køre i jsdom; erstat scanneren med en knap der udløser
// det samme onDetected-kald, så scan→fallback-stien kan drives fra en test.
vi.mock("../scanner/BarcodeScanner", () => ({
  default: ({ onDetected }) => (
    <button type="button" data-testid="fake-scan" onClick={() => onDetected("5711111111111")}>
      scan
    </button>
  ),
}));

const scanHeading = () => screen.queryByRole("heading", { name: "Scan" });
const manualHeading = () => screen.queryByRole("heading", { name: "Søg manuelt (TMDb)" });

describe("MovieLookupForm mode (feature #124)", () => {
  beforeEach(() => {
    vi.spyOn(api, "attributeOptions").mockResolvedValue({
      formats: [], audio_types: [], media_types: [], order_statuses: [], subtitles: [],
    });
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    vi.spyOn(api, "listOwners").mockResolvedValue([]);
    vi.spyOn(api, "listLocations").mockResolvedValue([]);
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue({ padding_width: 0 });
  });

  it("mode=both viser begge kort (bibliotekets uændrede opførsel)", () => {
    render(<MovieLookupForm user={{ username: "x" }} mode="both" />);
    expect(scanHeading()).toBeInTheDocument();
    expect(manualHeading()).toBeInTheDocument();
  });

  it("mode=scan viser kun scan-kortet", () => {
    render(<MovieLookupForm user={{ username: "x" }} mode="scan" />);
    expect(scanHeading()).toBeInTheDocument();
    expect(manualHeading()).not.toBeInTheDocument();
  });

  it("mode=manual viser kun titel-søgningen", () => {
    render(<MovieLookupForm user={{ username: "x" }} mode="manual" />);
    expect(manualHeading()).toBeInTheDocument();
    expect(scanHeading()).not.toBeInTheDocument();
  });

  it("scan uden match tilbyder at skifte til titel-søgning", async () => {
    vi.spyOn(api, "scanLookup").mockResolvedValue({ candidates: [], guessed_title: "Foo", barcode_source: null });
    render(<MovieLookupForm user={{ username: "x" }} mode="scan" />);

    await userEvent.click(screen.getByTestId("fake-scan"));
    const fallback = await screen.findByRole("button", { name: "Søg på titel i stedet" });
    await userEvent.click(fallback);

    // Skiftet skjuler scan-kortet og viser titel-søgningen i stedet.
    expect(manualHeading()).toBeInTheDocument();
    expect(scanHeading()).not.toBeInTheDocument();
  });
});
