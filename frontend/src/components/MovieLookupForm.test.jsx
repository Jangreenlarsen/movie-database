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

describe("MovieLookupForm valgmuligheder (BUGS.md #111)", () => {
  it("viser en fejl når format-/medietype-listerne ikke kan hentes", async () => {
    vi.spyOn(api, "attributeOptions").mockRejectedValue(new Error("Timeout"));
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    vi.spyOn(api, "listOwners").mockResolvedValue([]);
    vi.spyOn(api, "listLocations").mockResolvedValue([]);
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue({ padding_width: 0 });
    render(<MovieLookupForm user={{ username: "x" }} mode="both" />);
    expect(await screen.findByText(/Kunne ikke hente valgmulighederne.*Timeout/)).toBeInTheDocument();
  });
});

describe("MovieLookupForm fejlbeskeder (BUGS.md #107)", () => {
  beforeEach(() => {
    vi.spyOn(api, "attributeOptions").mockResolvedValue({
      formats: [], audio_types: [], media_types: [], order_statuses: [], subtitles: [],
    });
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    vi.spyOn(api, "listOwners").mockResolvedValue([]);
    vi.spyOn(api, "listLocations").mockResolvedValue([]);
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue({ padding_width: 0 });
  });

  it("stregkode-opslaget viser backendens egen fejltekst", async () => {
    vi.spyOn(api, "scanLookup").mockRejectedValue(new Error("TMDb-nøgle er ikke sat"));
    render(<MovieLookupForm user={{ username: "x" }} mode="scan" />);
    await userEvent.click(screen.getByTestId("fake-scan"));
    expect(await screen.findByText("TMDb-nøgle er ikke sat")).toBeInTheDocument();
  });

  it("titel-søgningen viser backendens egen fejltekst", async () => {
    vi.spyOn(api, "tmdbSearch").mockRejectedValue(new Error("TMDb rate-limit ramt (429), prøv igen om lidt"));
    vi.spyOn(api, "tvTmdbSearch").mockResolvedValue([]);
    render(<MovieLookupForm user={{ username: "x" }} mode="manual" />);
    await userEvent.type(screen.getByPlaceholderText("Film- eller serietitel..."), "Alien");
    await userEvent.click(screen.getByRole("button", { name: "Søg" }));
    expect(
      await screen.findByText("TMDb rate-limit ramt (429), prøv igen om lidt")
    ).toBeInTheDocument();
  });

  it("falder tilbage til den generiske tekst uden en besked", async () => {
    vi.spyOn(api, "scanLookup").mockRejectedValue(new Error(""));
    render(<MovieLookupForm user={{ username: "x" }} mode="scan" />);
    await userEvent.click(screen.getByTestId("fake-scan"));
    expect(
      await screen.findByText("Opslag fejlede. Prøv igen, eller søg manuelt på titel nedenfor.")
    ).toBeInTheDocument();
  });
});
