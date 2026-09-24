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

import { render, screen, waitFor, within } from "@testing-library/react";
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

/**
 * Feature #228 (erstatter #222's ene flueben) — ved en ny biblioteks-
 * tilføjelse eller "Flyt til bibliotek" vælger man mellem tre udfald for
 * beskeden til brugerne. Det testværdige (regel 19): valgene vises kun hvor
 * de er relevante, standarden er den samlede opdatering, og valget følger
 * rent faktisk med i payloadet som `announce`.
 */
describe("MovieDetailModal — besked-valg ved biblioteks-tilføjelse (feature #228)", () => {
  beforeEach(() => {
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: false });
  });

  it("standard ved 'Flyt til bibliotek' er den samlede opdatering", async () => {
    vi.spyOn(api, "updateMovie").mockResolvedValue({ ...baseMovie, is_wishlist: false });
    renderModal({ ...baseMovie, media_type: "Fysisk", format: "F-DVD" });

    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    const group = screen.getByRole("group", {
      name: "Besked til brugerne når den flyttes til biblioteket",
    });
    expect(within(group).getByRole("radio", { name: /Med i næste samlede opdatering/ })).toBeChecked();

    await userEvent.click(screen.getByRole("button", { name: "Flyt til bibliotek" }));
    await waitFor(() => expect(api.updateMovie).toHaveBeenCalledTimes(1));
    const [, payload] = api.updateMovie.mock.calls[0];
    expect(payload.announce).toBe("queue");
    expect(payload).not.toHaveProperty("notify_all");
  });

  it("'Send besked til alle med det samme' sendes som announce: now ved flyt", async () => {
    vi.spyOn(api, "updateMovie").mockResolvedValue({ ...baseMovie, is_wishlist: false });
    renderModal({ ...baseMovie, media_type: "Fysisk", format: "F-DVD" });

    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    await userEvent.click(screen.getByRole("radio", { name: /Send besked til alle med det samme/ }));
    await userEvent.click(screen.getByRole("button", { name: "Flyt til bibliotek" }));

    await waitFor(() => expect(api.updateMovie).toHaveBeenCalledTimes(1));
    const [, payload] = api.updateMovie.mock.calls[0];
    expect(payload.announce).toBe("now");
  });

  it("vises ved oprettelse af en ny (ikke-ønske) film, og 'Ingen besked' sendes med", async () => {
    vi.spyOn(api, "createMovie").mockResolvedValue({ ...baseMovie, id: "movie-2" });
    renderModal({
      ...baseMovie,
      id: undefined,
      is_wishlist: false,
      media_type: "Fysisk",
      format: "F-DVD",
    });

    await screen.findByRole("group", { name: "Besked til brugerne om den nye titel" });
    await userEvent.click(screen.getByRole("radio", { name: /Ingen besked/ }));
    await userEvent.click(screen.getByRole("button", { name: "Opret" }));

    await waitFor(() => expect(api.createMovie).toHaveBeenCalledTimes(1));
    const [payload] = api.createMovie.mock.calls[0];
    expect(payload.announce).toBe("none");
  });

  it("vises IKKE ved oprettelse af et nyt ønske", async () => {
    vi.spyOn(api, "createMovie").mockResolvedValue({ ...baseMovie, id: "movie-2" });
    renderModal({ ...baseMovie, id: undefined, is_wishlist: true });

    await screen.findByRole("button", { name: "Opret" });
    expect(
      screen.queryByRole("group", { name: "Besked til brugerne om den nye titel" })
    ).not.toBeInTheDocument();
  });

  it("vises IKKE ved en almindelig redigering af en allerede-ejet film", async () => {
    renderModal({ ...baseMovie, is_wishlist: false, media_type: "Fysisk", format: "F-DVD" });

    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    expect(screen.queryByRole("radio", { name: /Med i næste samlede opdatering/ })).not.toBeInTheDocument();
  });
});

describe("CollectionSection — tilføj serie-del til ønskelisten (feature #196)", () => {
  beforeEach(() => {
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: false });
  });

  it("tillader tilføjelse til ønskelisten fra en EJET films collection-sektion (tidligere blokeret, BUGS.md #58), og '+ Ønskeliste'-knappen erstattes af 'På indkøbslisten' bagefter, så samme del ikke kan tilføjes igen ved et nyt klik", async () => {
    const unowned = {
      tmdb_id: 501,
      title: "Del To",
      year: 2021,
      poster_url: null,
      owned: false,
      owned_movie_id: null,
      owned_is_wishlist: false,
    };
    vi.spyOn(api, "getCollection")
      .mockResolvedValueOnce({ id: 99, name: "Test-trilogien", poster_url: null, parts: [unowned] })
      .mockResolvedValueOnce({
        id: 99,
        name: "Test-trilogien",
        poster_url: null,
        parts: [{ ...unowned, owned: true, owned_movie_id: "new-wish-id", owned_is_wishlist: true }],
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

    // Efter reload (anden getCollection-respons) bør knappen være væk, erstattet
    // af "På indkøbslisten" — ellers kunne et nyt klik tilføje samme del igen.
    await waitFor(() => expect(api.getCollection).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "+ Ønskeliste" })).not.toBeInTheDocument()
    );
    expect(screen.getByText("På indkøbslisten")).toBeInTheDocument();
  });
});

describe("CollectionSection — viser medietype for ejede dele (feature #201)", () => {
  beforeEach(() => {
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: false });
  });

  it("viser '✓ Ejer (Fysisk)'/'✓ Ejer (Digital)' i stedet for bare '✓ Ejer' når backend oplyser medietypen", async () => {
    vi.spyOn(api, "getCollection").mockResolvedValue({
      id: 99,
      name: "Test-trilogien",
      poster_url: null,
      parts: [
        {
          tmdb_id: 1,
          title: "Del Én",
          year: 2019,
          poster_url: null,
          owned: true,
          owned_movie_id: "m1",
          owned_is_wishlist: false,
          owned_media_type: "Fysisk",
        },
        {
          tmdb_id: 2,
          title: "Del To",
          year: 2020,
          poster_url: null,
          owned: true,
          owned_movie_id: "m2",
          owned_is_wishlist: false,
          owned_media_type: "Digital",
        },
      ],
    });

    const movie = {
      ...baseMovie,
      is_wishlist: false,
      media_type: "Fysisk",
      format: "F-DVD",
      collection_id: 99,
      collection_name: "Test-trilogien",
    };
    renderModal(movie);

    await userEvent.click(screen.getByText(/Del af samlingen: Test-trilogien/));

    expect(await screen.findByText("✓ Ejer (Fysisk)")).toBeInTheDocument();
    expect(screen.getByText("✓ Ejer (Digital)")).toBeInTheDocument();
    // Aldrig den generiske "✓ Ejer" uden medietype, når backend rent
    // faktisk oplyste den.
    expect(screen.queryByText("✓ Ejer")).not.toBeInTheDocument();
  });
});

describe("CollectionSection — klikbare dele (feature #230)", () => {
  const parts = [
    { tmdb_id: 1, title: "Del Én", year: 2019, poster_url: null, owned: true, owned_movie_id: "movie-1", owned_is_wishlist: false, owned_media_type: "Fysisk" },
    { tmdb_id: 2, title: "Del To", year: 2020, poster_url: null, owned: true, owned_movie_id: "m2", owned_is_wishlist: false, owned_media_type: "Digital" },
    { tmdb_id: 3, title: "Del Tre", year: 2021, poster_url: null, owned: false, owned_movie_id: null, owned_is_wishlist: false },
  ];
  const ownedMovie = {
    ...baseMovie,
    is_wishlist: false,
    media_type: "Fysisk",
    format: "F-DVD",
    collection_id: 99,
    collection_name: "Test-trilogien",
  };

  function renderWithOpen(onOpenMovie, extra = {}) {
    return render(
      <MovieDetailModal
        movie={ownedMovie}
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
        onOpenMovie={onOpenMovie}
        {...extra}
      />
    );
  }

  beforeEach(() => {
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: false });
    vi.spyOn(api, "getCollection").mockResolvedValue({ id: 99, name: "Test-trilogien", poster_url: null, parts });
  });

  it("åbner en ejet søster-film med dens fulde data, men ikke den man står på eller en man ikke ejer", async () => {
    const full = { ...ownedMovie, id: "m2", title: "Del To" };
    vi.spyOn(api, "getMovie").mockResolvedValue(full);
    const onOpenMovie = vi.fn();
    renderWithOpen(onOpenMovie);

    await userEvent.click(screen.getByText(/Del af samlingen: Test-trilogien/));
    await userEvent.click(await screen.findByRole("button", { name: "Del To (2020)" }));

    expect(api.getMovie).toHaveBeenCalledWith("m2");
    await waitFor(() => expect(onOpenMovie).toHaveBeenCalledWith(full));
    expect(screen.queryByRole("button", { name: "Del Én (2019)" })).toBeNull();
    expect(screen.getByText("Del Én (2019)")).toHaveAttribute("aria-current", "true");
    expect(screen.queryByRole("button", { name: "Del Tre (2021)" })).toBeNull();
  });

  it("viser backendens fejltekst når filmen ikke kan hentes", async () => {
    vi.spyOn(api, "getMovie").mockRejectedValue(new Error("Filmen blev ikke fundet"));
    renderWithOpen(vi.fn());
    await userEvent.click(screen.getByText(/Del af samlingen: Test-trilogien/));
    await userEvent.click(await screen.findByRole("button", { name: "Del To (2020)" }));
    expect(await screen.findByText("Filmen blev ikke fundet")).toBeInTheDocument();
  });

  it("er foldet ud fra start når filmen blev åbnet fra en anden films samling", async () => {
    renderWithOpen(vi.fn(), { collectionInitiallyExpanded: true });
    expect(await screen.findByRole("button", { name: "Del To (2020)" })).toBeInTheDocument();
  });

  it("uden onOpenMovie (fx scan-flowet) er delene bare tekst", async () => {
    renderWithOpen(undefined);
    await userEvent.click(screen.getByText(/Del af samlingen: Test-trilogien/));
    await screen.findByText("Del To (2020)");
    expect(screen.queryByRole("button", { name: "Del To (2020)" })).toBeNull();
  });
});

describe("MovieDetailModal — 'Bestilt'-badge for gæster (feature #203)", () => {
  function renderAsGuest(movie) {
    return render(
      <MovieDetailModal
        movie={movie}
        user={{ username: "guest1", role: "guest" }}
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

  beforeEach(() => {
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: false });
  });

  it("viser en forenklet 'Bestilt'-badge for en gæst, uden bestillingskilden", async () => {
    const movie = { ...baseMovie, order_status: "Bestilt ved iMusic" };
    renderAsGuest(movie);

    expect(await screen.findByText("Bestilt")).toBeInTheDocument();
    expect(screen.queryByText("Bestilt ved iMusic")).not.toBeInTheDocument();
  });

  it("viser fortsat intet bestillings-felt for en gæst når ønsket ikke er bestilt", async () => {
    const movie = { ...baseMovie, order_status: null };
    renderAsGuest(movie);

    await screen.findByText(movie.title);
    expect(screen.queryByText("Bestilt")).not.toBeInTheDocument();
    expect(screen.queryByText("Ikke bestilt")).not.toBeInTheDocument();
  });

  it("viser fortsat den fulde bestillingsstatus (med kilde) for en admin", async () => {
    const movie = { ...baseMovie, order_status: "Bestilt ved iMusic" };
    renderModal(movie);

    expect(await screen.findByText("Bestilt ved iMusic")).toBeInTheDocument();
  });
});
