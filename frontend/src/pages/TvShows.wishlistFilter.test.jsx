/**
 * Feature #214 — samme rettelse som Library.wishlistFilter.test.jsx, blot
 * for TV-siden (identisk kopieret mønster i TvShows.jsx, jf. CLAUDE.md regel
 * 16's "tjek de øvrige grene med det samme").
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import TvShows from "./TvShows";

const user = {
  username: "guest1",
  role: "guest",
  settings: {},
};

describe("TvShows — 'Filtrér dine ønsker' skjules under 'Tilføre film på title' (feature #214)", () => {
  beforeEach(() => {
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    vi.spyOn(api, "listOwners").mockResolvedValue([]);
    vi.spyOn(api, "listLocations").mockResolvedValue([]);
    vi.spyOn(api, "tvAttributeOptions").mockResolvedValue({
      formats: [],
      audio_types: [],
      media_types: [],
      order_statuses: [],
      subtitles: [],
    });
    vi.spyOn(api, "listTvGenres").mockResolvedValue([]);
    vi.spyOn(api, "getSerialNumberConfig").mockResolvedValue({ padding_width: 0 });
    vi.spyOn(api, "getPlexAvailability").mockResolvedValue({
      status: "unconfigured",
      items: {},
      shieldConfigured: false,
      playAllowed: true,
    });
    vi.spyOn(api, "listTvShows").mockResolvedValue({ items: [], total: 0 });
  });

  it("skjuler filter-rækken mens tilføjelsesformularen er åben og viser den igen når den lukkes", async () => {
    render(
      <TvShows
        user={user}
        wishlist={true}
        onSettingsChanged={() => {}}
        onGoToMovies={() => {}}
        onLibraryChanged={() => {}}
      />
    );

    await waitFor(() => expect(api.listTvShows).toHaveBeenCalled());
    expect(screen.getByPlaceholderText("Filtrér dine ønsker...")).toBeInTheDocument();

    const uEvent = userEvent.setup();
    await uEvent.click(screen.getByRole("button", { name: /Tilføre film på title/i }));

    expect(screen.queryByPlaceholderText("Filtrér dine ønsker...")).not.toBeInTheDocument();

    await uEvent.click(screen.getByRole("button", { name: /Tilføre film på title/i }));

    expect(screen.getByPlaceholderText("Filtrér dine ønsker...")).toBeInTheDocument();
  });
});
