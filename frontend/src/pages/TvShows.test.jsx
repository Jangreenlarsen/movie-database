/**
 * Feature #203 (Jan: "hvis en film/tv er bestilt så skal guest users se en
 * badge hvor der står 'bestilt'") — samme "Bestilt"-badge for gæster som
 * Library.test.jsx dækker for film, blot for TV-serier (identisk
 * kopieret mønster i TvShows.jsx, jf. CLAUDE.md regel 16's "tjek de øvrige
 * grene med det samme").
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { TvShowDetailModal } from "./TvShows";

const attributeOptions = {
  formats: ["F-DVD", "F-BluRay"],
  audio_types: ["5.1"],
  media_types: ["Fysisk", "Digital"],
  order_statuses: ["Bestilt"],
  subtitles: ["Dansk", "English"],
};

const basePlex = { status: "unconfigured", items: {}, shieldConfigured: false, playAllowed: true };

const baseShow = {
  id: "show-1",
  name: "Wishlist Serie",
  year: 2020,
  end_year: null,
  status: null,
  poster_url: null,
  tmdb_id: 42,
  overview: null,
  creators: [],
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
  is_wishlist: true,
  wishlist_status: null,
  imdb_url: null,
  rating: null,
  seasons: [],
};

function renderAsGuest(show) {
  return render(
    <TvShowDetailModal
      show={show}
      user={{ username: "guest1", role: "guest" }}
      allTags={[]}
      allOwners={[]}
      allLocations={[]}
      attributeOptions={attributeOptions}
      serialPaddingWidth={0}
      plex={basePlex}
      onClose={() => {}}
      onChanged={() => {}}
    />
  );
}

function renderAsAdmin(show) {
  return render(
    <TvShowDetailModal
      show={show}
      user={{ username: "admin1", role: "admin" }}
      allTags={[]}
      allOwners={[]}
      allLocations={[]}
      attributeOptions={attributeOptions}
      serialPaddingWidth={0}
      plex={basePlex}
      onClose={() => {}}
      onChanged={() => {}}
    />
  );
}

describe("TvShowDetailModal — 'Bestilt'-badge for gæster (feature #203)", () => {
  beforeEach(() => {
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
  });

  it("viser en forenklet 'Bestilt'-badge for en gæst, uden bestillingskilden", async () => {
    const show = { ...baseShow, order_status: "Bestilt ved iMusic" };
    renderAsGuest(show);

    expect(await screen.findByText("Bestilt")).toBeInTheDocument();
    expect(screen.queryByText("Bestilt ved iMusic")).not.toBeInTheDocument();
  });

  it("viser fortsat intet bestillings-felt for en gæst når ønsket ikke er bestilt", async () => {
    const show = { ...baseShow, order_status: null };
    renderAsGuest(show);

    await screen.findByText(show.name);
    expect(screen.queryByText("Bestilt")).not.toBeInTheDocument();
    expect(screen.queryByText("Ikke bestilt")).not.toBeInTheDocument();
  });

  it("viser fortsat den fulde bestillingsstatus (med kilde) for en admin", async () => {
    const show = { ...baseShow, order_status: "Bestilt ved iMusic" };
    renderAsAdmin(show);

    expect(await screen.findByText("Bestilt ved iMusic")).toBeInTheDocument();
  });
});

/**
 * Feature #222 — se den identiske note i Library.test.jsx. TvShowDetailModal
 * er en struktureret tro kopi af MovieDetailModal (regel 16), så samme fire
 * tilstande dækkes her.
 */
describe("TvShowDetailModal — broadcast-flueben ved biblioteks-tilføjelse (feature #222)", () => {
  beforeEach(() => {
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: false });
  });

  it("vises ved 'Flyt til bibliotek' for et ønske, default fra, og sendes med i payload når afkrydset", async () => {
    vi.spyOn(api, "updateTvShow").mockResolvedValue({ ...baseShow, is_wishlist: false });
    const show = { ...baseShow, media_type: "Fysisk", format: "F-DVD" };
    renderAsAdmin(show);

    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    const checkbox = screen.getByRole("checkbox", {
      name: "Send besked til alle når den flyttes til biblioteket",
    });
    expect(checkbox).not.toBeChecked();

    await userEvent.click(checkbox);
    await userEvent.click(screen.getByRole("button", { name: "Flyt til bibliotek" }));

    await waitFor(() => expect(api.updateTvShow).toHaveBeenCalledTimes(1));
    const [, payload] = api.updateTvShow.mock.calls[0];
    expect(payload.notify_all).toBe(true);
  });

  it("vises ved oprettelse af en ny (ikke-ønske) serie, og sendes med til createTvShow", async () => {
    vi.spyOn(api, "createTvShow").mockResolvedValue({ ...baseShow, id: "show-2" });
    const draft = {
      ...baseShow,
      id: undefined,
      is_wishlist: false,
      media_type: "Fysisk",
      format: "F-DVD",
    };
    renderAsAdmin(draft);

    const checkbox = await screen.findByRole("checkbox", {
      name: "Send besked til alle om denne nye tilføjelse",
    });
    await userEvent.click(checkbox);
    await userEvent.click(screen.getByRole("button", { name: "Opret" }));

    await waitFor(() => expect(api.createTvShow).toHaveBeenCalledTimes(1));
    const [payload] = api.createTvShow.mock.calls[0];
    expect(payload.notify_all).toBe(true);
  });

  it("vises IKKE ved en almindelig redigering af en allerede-ejet serie (ikke en flyt-handling)", async () => {
    const show = { ...baseShow, is_wishlist: false, media_type: "Fysisk", format: "F-DVD" };
    renderAsAdmin(show);

    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    expect(
      screen.queryByRole("checkbox", { name: "Send besked til alle når den flyttes til biblioteket" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: "Send besked til alle om denne nye tilføjelse" })
    ).not.toBeInTheDocument();
  });
});
