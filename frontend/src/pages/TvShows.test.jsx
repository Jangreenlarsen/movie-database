/**
 * Feature #203 (Jan: "hvis en film/tv er bestilt så skal guest users se en
 * badge hvor der står 'bestilt'") — samme "Bestilt"-badge for gæster som
 * Library.test.jsx dækker for film, blot for TV-serier (identisk
 * kopieret mønster i TvShows.jsx, jf. CLAUDE.md regel 16's "tjek de øvrige
 * grene med det samme").
 */

import { render, screen, waitFor, within } from "@testing-library/react";
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
 * Feature #228 (erstatter #222's ene flueben) — ved en ny biblioteks-
 * tilføjelse eller "Flyt til bibliotek" vælger man mellem tre udfald for
 * beskeden til brugerne. Det testværdige (regel 19): valgene vises kun hvor
 * de er relevante, standarden er den samlede opdatering, og valget følger
 * rent faktisk med i payloadet som `announce`.
 */
describe("TvShowDetailModal — besked-valg ved biblioteks-tilføjelse (feature #228)", () => {
  beforeEach(() => {
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: false });
  });

  it("standard ved 'Flyt til bibliotek' er den samlede opdatering", async () => {
    vi.spyOn(api, "updateTvShow").mockResolvedValue({ ...baseShow, is_wishlist: false });
    renderAsAdmin({ ...baseShow, media_type: "Fysisk", format: "F-DVD" });

    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    const group = screen.getByRole("group", {
      name: "Besked til brugerne når den flyttes til biblioteket",
    });
    expect(within(group).getByRole("radio", { name: /Med i næste samlede opdatering/ })).toBeChecked();

    await userEvent.click(screen.getByRole("button", { name: "Flyt til bibliotek" }));
    await waitFor(() => expect(api.updateTvShow).toHaveBeenCalledTimes(1));
    const [, payload] = api.updateTvShow.mock.calls[0];
    expect(payload.announce).toBe("queue");
    expect(payload).not.toHaveProperty("notify_all");
  });

  it("'Send besked til alle med det samme' sendes som announce: now ved flyt", async () => {
    vi.spyOn(api, "updateTvShow").mockResolvedValue({ ...baseShow, is_wishlist: false });
    renderAsAdmin({ ...baseShow, media_type: "Fysisk", format: "F-DVD" });

    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    await userEvent.click(screen.getByRole("radio", { name: /Send besked til alle med det samme/ }));
    await userEvent.click(screen.getByRole("button", { name: "Flyt til bibliotek" }));

    await waitFor(() => expect(api.updateTvShow).toHaveBeenCalledTimes(1));
    const [, payload] = api.updateTvShow.mock.calls[0];
    expect(payload.announce).toBe("now");
  });

  it("vises ved oprettelse af en ny (ikke-ønske) serie, og 'Ingen besked' sendes med", async () => {
    vi.spyOn(api, "createTvShow").mockResolvedValue({ ...baseShow, id: "show-2" });
    renderAsAdmin({
      ...baseShow,
      id: undefined,
      is_wishlist: false,
      media_type: "Fysisk",
      format: "F-DVD",
    });

    await screen.findByRole("group", { name: "Besked til brugerne om den nye titel" });
    await userEvent.click(screen.getByRole("radio", { name: /Ingen besked/ }));
    await userEvent.click(screen.getByRole("button", { name: "Opret" }));

    await waitFor(() => expect(api.createTvShow).toHaveBeenCalledTimes(1));
    const [payload] = api.createTvShow.mock.calls[0];
    expect(payload.announce).toBe("none");
  });

  it("vises IKKE ved oprettelse af et nyt ønske", async () => {
    vi.spyOn(api, "createTvShow").mockResolvedValue({ ...baseShow, id: "show-2" });
    renderAsAdmin({ ...baseShow, id: undefined, is_wishlist: true });

    await screen.findByRole("button", { name: "Opret" });
    expect(
      screen.queryByRole("group", { name: "Besked til brugerne om den nye titel" })
    ).not.toBeInTheDocument();
  });

  it("vises IKKE ved en almindelig redigering af en allerede-ejet serie", async () => {
    renderAsAdmin({ ...baseShow, is_wishlist: false, media_type: "Fysisk", format: "F-DVD" });

    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    expect(screen.queryByRole("radio", { name: /Med i næste samlede opdatering/ })).not.toBeInTheDocument();
  });
});

describe("TvShowDetailModal — redigerbart serienummer (BUGS.md #109)", () => {
  const owned = {
    ...baseShow,
    is_wishlist: false,
    media_type: "Fysisk",
    format: "F-DVD",
    serial_number: 3,
    registered_by: "admin1",
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "recordVisit").mockResolvedValue({});
    vi.spyOn(api, "myScreeningRequests").mockResolvedValue([]);
    vi.spyOn(api, "getScreeningRequestPolicy").mockResolvedValue({ require_preferred_at: false });
  });

  async function editSerial(value) {
    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    const input = screen.getByDisplayValue("3");
    await userEvent.clear(input);
    await userEvent.type(input, value);
    await userEvent.click(screen.getByRole("button", { name: "Gem ændringer" }));
  }

  it("bekræfter byt-plads med titlen og sender det nye nummer", async () => {
    vi.spyOn(api, "getTvSerialSwapTarget").mockResolvedValue({ title: "Anden Serie" });
    const update = vi.spyOn(api, "updateTvShow").mockResolvedValue({});
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderAsAdmin(owned);

    await editSerial("7");

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
    expect(api.getTvSerialSwapTarget).toHaveBeenCalledWith("show-1", 7);
    expect(confirm.mock.calls[0][0]).toContain("Anden Serie");
    expect(update.mock.calls[0][1].serial_number).toBe(7);
  });

  it("gemmer intet når byttet fortrydes", async () => {
    vi.spyOn(api, "getTvSerialSwapTarget").mockResolvedValue({ title: "Anden Serie" });
    const update = vi.spyOn(api, "updateTvShow").mockResolvedValue({});
    vi.spyOn(window, "confirm").mockReturnValue(false);
    renderAsAdmin(owned);

    await editSerial("7");
    await waitFor(() => expect(api.getTvSerialSwapTarget).toHaveBeenCalled());
    expect(update).not.toHaveBeenCalled();
  });

  it("et frit nummer gemmes uden bekræftelse", async () => {
    vi.spyOn(api, "getTvSerialSwapTarget").mockResolvedValue({ title: null });
    const update = vi.spyOn(api, "updateTvShow").mockResolvedValue({});
    const confirm = vi.spyOn(window, "confirm");
    renderAsAdmin(owned);

    await editSerial("12");
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
    expect(confirm).not.toHaveBeenCalled();
    expect(update.mock.calls[0][1].serial_number).toBe(12);
  });

  it("feltet er låst for en bruger der hverken er admin eller har registreret serien", async () => {
    render(
      <TvShowDetailModal
        show={owned}
        user={{ username: "andenbruger", role: "standard" }}
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
    await userEvent.click(await screen.findByRole("button", { name: "Redigér" }));
    expect(screen.getByDisplayValue("3")).toBeDisabled();
  });
});
