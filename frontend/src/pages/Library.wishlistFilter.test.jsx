/**
 * Feature #214 (Jan: "vi skal have en funktion på portal der fjener 'filter
 * dine ønske' funktion når man trykker på tilføre film på title") — på
 * Ønskelisten sad "Filtrér dine ønsker..."-rækken lige over MovieLookupForms
 * eget søgefelt, når "Tilføre film på title" var åben, og de to blev nemt
 * forvekslet. Rækken skjules nu mens tilføjelsesformularen er åben.
 *
 * Opfølgning (Jan: "skal også gælde for film og tv serie sektioner også")
 * — samme forvekslings-problem gælder biblioteket generelle søgning, ikke
 * kun ønskelistens filter, så rækken skjules nu uanset wishlist eller ej.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import Library from "./Library";

const user = {
  username: "guest1",
  role: "guest",
  settings: {},
};

describe("Library — 'Filtrér dine ønsker' skjules under 'Tilføre film på title' (feature #214)", () => {
  beforeEach(() => {
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    vi.spyOn(api, "listOwners").mockResolvedValue([]);
    vi.spyOn(api, "listLocations").mockResolvedValue([]);
    vi.spyOn(api, "attributeOptions").mockResolvedValue({
      formats: [],
      audio_types: [],
      media_types: [],
      order_statuses: [],
      subtitles: [],
    });
    vi.spyOn(api, "listMovieGenres").mockResolvedValue([]);
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue({ padding_width: 0 });
    vi.spyOn(api, "getPlexAvailability").mockResolvedValue({
      status: "unconfigured",
      items: {},
      shieldConfigured: false,
      playAllowed: true,
    });
    vi.spyOn(api, "listMovies").mockResolvedValue({ items: [], total: 0 });
  });

  it("skjuler filter-rækken mens tilføjelsesformularen er åben og viser den igen når den lukkes", async () => {
    render(
      <Library
        user={user}
        wishlist={true}
        onSettingsChanged={() => {}}
        onGoToTvShows={() => {}}
        onLibraryChanged={() => {}}
      />
    );

    await waitFor(() => expect(api.listMovies).toHaveBeenCalled());
    expect(screen.getByPlaceholderText("Filtrér dine ønsker...")).toBeInTheDocument();

    const uEvent = userEvent.setup();
    await uEvent.click(screen.getByRole("button", { name: /Tilføre film på title/i }));

    expect(screen.queryByPlaceholderText("Filtrér dine ønsker...")).not.toBeInTheDocument();

    await uEvent.click(screen.getByRole("button", { name: /Tilføre film på title/i }));

    expect(screen.getByPlaceholderText("Filtrér dine ønsker...")).toBeInTheDocument();
  });

  it("skjuler den almindelige biblioteks-søgning (ikke kun ønskelistens) mens tilføjelsesformularen er åben", async () => {
    render(
      <Library
        user={{ username: "standard1", role: "standard", settings: {} }}
        onSettingsChanged={() => {}}
        onGoToTvShows={() => {}}
        onLibraryChanged={() => {}}
      />
    );

    await waitFor(() => expect(api.listMovies).toHaveBeenCalled());
    expect(screen.getByPlaceholderText("Søg på titel, skuespiller, genre, serienr...")).toBeInTheDocument();

    const uEvent = userEvent.setup();
    await uEvent.click(screen.getByRole("button", { name: /Tilføre film på title/i }));

    expect(
      screen.queryByPlaceholderText("Søg på titel, skuespiller, genre, serienr...")
    ).not.toBeInTheDocument();

    await uEvent.click(screen.getByRole("button", { name: /Tilføre film på title/i }));

    expect(screen.getByPlaceholderText("Søg på titel, skuespiller, genre, serienr...")).toBeInTheDocument();
  });
});
