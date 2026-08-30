/**
 * Feature #203 (Jan: "hvis en film/tv er bestilt så skal guest users se en
 * badge hvor der står 'bestilt'") — samme "Bestilt"-badge for gæster som
 * Library.test.jsx dækker for film, blot for TV-serier (identisk
 * kopieret mønster i TvShows.jsx, jf. CLAUDE.md regel 16's "tjek de øvrige
 * grene med det samme").
 */

import { render, screen } from "@testing-library/react";
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
