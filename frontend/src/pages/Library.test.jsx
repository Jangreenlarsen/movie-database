/**
 * Feature #196 (Jan: "flyt til bibliotek fra ønskeliste til at man skal
 * sætte alle parameter som i edit med en save") — to testværdige adfærds-
 * ændringer, ingen af dem visuelle (regel 19):
 *
 * 1. moveToLibrary() sendte tidligere kun { is_wishlist: false } og smed
 *    stiltiende alle felter man havde redigeret i formularen væk (BUGS.md-
 *    klasse fejl: en handling der ser ud til at gemme, men ikke gør det).
 *    Nu genbruger den samme payload-opbygning som "Gem ændringer".
 * 2. "Flyt til bibliotek" kan nu blive uden format/medietype sat, hvilket
 *    backend afviser (ClassificationRequiredError) — knappen skal derfor
 *    være deaktiveret i det tilfælde, ikke først fejle efter klik.
 *
 * Desuden: CollectionSection.addPart() tillod tidligere kun tilføjelse til
 * ønskelisten når den film man SÅ PÅ selv var et ønske ("følg forælderen",
 * BUGS.md #58) — en ejet films collection-sektion blokerede med en
 * henvisning til det fulde tilføj-flow. Ønskelisten har aldrig krævet
 * format/medietype, så blokeringen gav ingen mening for netop den handling.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { MovieDetailModal } from "./Library";

const attributeOptions = {
  formats: ["F-DVD", "F-BluRay"],
  audio_types: ["5.1"],
  media_types: ["Fysisk", "Digital"],
  order_statuses: ["Bestilt"],
  subtitles: ["Dansk", "English"],
};

const basePlex = { status: "unconfigured", items: {}, shieldConfigured: false, playAllowed: true };

const baseMovie = {
  id: "movie-1",
  title: "Wishlist Film",
  year: 2020,
  poster_url: null,
  tmdb_id: 42,
  overview: null,
  director: null,
  cast: [],
  genres: [],
  tags: [],
  audio_types: [],
  subtitles: [],
  format: null,
  media_type: null,
  location: null,
  owner: null,
  order_status: null,
  personal_rating: null,
  personal_note: null,
  watched: false,
  watched_at: null,
  serial_number: null,
  registered_by: null,
  collection_id: null,
  collection_name: null,
  is_wishlist: true,
  wishlist_status: null,
  imdb_url: null,
  trailer_url: null,
  runtime: null,
  rating: null,
};

function renderModal(movie) {
  return render(
    <MovieDetailModal
      movie={movie}
      user={{ username: "admin1", role: "admin" }}
      allTags={[]}
      allOwners={[]}
      allLocations={[]}
      attributeOptions={attributeOptions}
      serialPaddingWidth={0}
      plex={basePlex}
      onClose={() => {}}
      onChanged={() => {}}
      onFilterByPerson={() => {}}
    />
  );
}

describe("MovieDetailModal — flyt til bibliotek (feature #196)", () => {
  beforeEach(() => {
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: false });
  });

  it("sender de redigerede felter sammen med is_wishlist:false, ikke kun et isoleret flag", async () => {
    vi.spyOn(api, "updateMovie").mockResolvedValue({ ...baseMovie, is_wishlist: false });
    const movie = { ...baseMovie, media_type: "Fysisk", format: "F-DVD" };
    renderModal(movie);

    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    const noteField = screen.getByPlaceholderText("Egne tanker om filmen...");
    await userEvent.type(noteField, "Fundet i kælderen");

    await userEvent.click(screen.getByRole("button", { name: "Flyt til bibliotek" }));

    await waitFor(() => expect(api.updateMovie).toHaveBeenCalledTimes(1));
    const [movieId, payload] = api.updateMovie.mock.calls[0];
    expect(movieId).toBe("movie-1");
    expect(payload.is_wishlist).toBe(false);
    expect(payload.personal_note).toBe("Fundet i kælderen");
    expect(payload.media_type).toBe("Fysisk");
    expect(payload.format).toBe("F-DVD");
  });

  it("deaktiverer 'Flyt til bibliotek' når medietype/format mangler", async () => {
    vi.spyOn(api, "updateMovie").mockResolvedValue({});
    const movie = { ...baseMovie }; // hverken media_type eller format sat
    renderModal(movie);

    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    expect(screen.getByRole("button", { name: "Flyt til bibliotek" })).toBeDisabled();
    expect(api.updateMovie).not.toHaveBeenCalled();
  });
});

describe("CollectionSection — tilføj serie-del til ønskelisten (feature #196)", () => {
  beforeEach(() => {
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: false });
  });

  it("tillader tilføjelse til ønskelisten fra en EJET films collection-sektion (tidligere blokeret, BUGS.md #58)", async () => {
    vi.spyOn(api, "getCollection").mockResolvedValue({
      id: 99,
      name: "Test-trilogien",
      poster_url: null,
      parts: [
        {
          tmdb_id: 501,
          title: "Del To",
          year: 2021,
          poster_url: null,
          owned: false,
          owned_movie_id: null,
          owned_is_wishlist: false,
        },
      ],
    });
    vi.spyOn(api, "createMovie").mockResolvedValue({});

    const ownedMovie = {
      ...baseMovie,
      is_wishlist: false, // ejet, ikke ønske — den tidligere "følg forælderen"-blokering ramte netop dette
      media_type: "Fysisk",
      format: "F-DVD",
      collection_id: 99,
      collection_name: "Test-trilogien",
    };
    renderModal(ownedMovie);

    await userEvent.click(screen.getByText(/Del af samlingen: Test-trilogien/));
    const addButton = await screen.findByRole("button", { name: "+ Ønskeliste" });
    await userEvent.click(addButton);

    await waitFor(() => expect(api.createMovie).toHaveBeenCalledTimes(1));
    expect(api.createMovie).toHaveBeenCalledWith({ tmdb_id: 501, is_wishlist: true });
    // Ingen fejlbesked om "det fulde tilføj-flow" — handlingen lykkedes.
    expect(screen.queryByText(/fulde tilføj-flow/)).not.toBeInTheDocument();
  });
});
