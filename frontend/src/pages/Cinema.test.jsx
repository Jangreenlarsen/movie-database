/**
 * Feature #185 (Jan: "i voldby bio kort vil det være fint hvis man kan
 * trykke på de film der er under Anmodninger så man kan se detajler såsom
 * hvor lang er film er m.m."). Det testværdige (regel 19): et klik på
 * poster/titel skal rent faktisk åbne detalje-visningen, den skal vise de
 * hentede felter (spilletid m.m.), en fejl skal vise backendens SPECIFIKKE
 * besked (regel 16), og Luk-knappen skal rent faktisk lukke den igen.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import Cinema, { PollCard, RequestDetailModal, RequestRow } from "./Cinema";

function _request(overrides = {}) {
  return {
    id: "req1",
    media_kind: "movie",
    movie_id: "m1",
    tv_show_id: null,
    poster_url: null,
    title: "The Matrix",
    year: 1999,
    requested_by: [{ username: "testuser", message: null, preferred_at: null }],
    ...overrides,
  };
}

describe("Cinema (feature #193 — rum/billede/lyd-sektion kun for gæster)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listScreenings").mockResolvedValue([]);
    vi.spyOn(api, "recordVisit").mockResolvedValue();
    // Feature #162 — PollsSection renders unconditionally inside Cinema now,
    // so every test in this file mounts it too.
    vi.spyOn(api, "listPolls").mockResolvedValue([]);
  });

  it("viser sektionen for en gæst", async () => {
    render(<Cinema user={{ role: "guest" }} />);
    expect(await screen.findByText("Rummet")).toBeInTheDocument();
  });

  it("skjuler sektionen for en admin", async () => {
    render(<Cinema user={{ role: "admin" }} />);
    await screen.findByText("Ingen kommende visninger er planlagt endnu.");
    expect(screen.queryByText("Rummet")).not.toBeInTheDocument();
  });

  it("skjuler sektionen for en standard-bruger", async () => {
    render(<Cinema user={{ role: "standard" }} />);
    await screen.findByText("Ingen kommende visninger er planlagt endnu.");
    expect(screen.queryByText("Rummet")).not.toBeInTheDocument();
  });
});

/**
 * Feature #195 — Jan: "guester som er login skal se samme public side for
 * voldby bio som guester som ikke er login på portal". Det testværdige
 * (regel 19): en logget-ind gæst skal reelt kunne åbne de samme Presse/
 * Forplejning/Galleri-modaler som en anonym besøgende på /bio — ikke kun
 * mangle knapperne stille uden at nogen opdager det.
 */
describe("Cinema — Presse/Forplejning/Galleri kun for gæster (feature #195)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listScreenings").mockResolvedValue([]);
    vi.spyOn(api, "recordVisit").mockResolvedValue();
    // Feature #162 — PollsSection renders unconditionally inside Cinema now,
    // so every test in this file mounts it too.
    vi.spyOn(api, "listPolls").mockResolvedValue([]);
  });

  it("en gæst kan åbne galleriet fra fanen", async () => {
    const user = userEvent.setup();
    render(<Cinema user={{ role: "guest" }} />);
    await screen.findByText("Rummet");

    await user.click(screen.getByRole("button", { name: /Galleri/ }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("admin ser ikke Presse/Forplejning/Galleri-knapperne (findes allerede på /bio)", async () => {
    render(<Cinema user={{ role: "admin" }} />);
    await screen.findByText("Ingen kommende visninger er planlagt endnu.");

    expect(screen.queryByRole("button", { name: /Presse Nyt/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Forplejning/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Galleri/ })).not.toBeInTheDocument();
  });
});

describe("Cinema — del-link (feature #193)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listScreenings").mockResolvedValue([]);
    vi.spyOn(api, "recordVisit").mockResolvedValue();
    // Feature #162 — PollsSection renders unconditionally inside Cinema now,
    // so every test in this file mounts it too.
    vi.spyOn(api, "listPolls").mockResolvedValue([]);
  });

  it("kopierer et link til /bio, ikke preview-siden /bio2", async () => {
    const user = userEvent.setup();
    render(<Cinema user={{ role: "admin" }} />);
    await screen.findByText("Ingen kommende visninger er planlagt endnu.");

    const writeTextSpy = vi.spyOn(navigator.clipboard, "writeText");
    await user.click(screen.getByRole("button", { name: /Del link til Voldby BIO/ }));

    expect(writeTextSpy).toHaveBeenCalledWith(`${window.location.origin}/bio`);
  });
});

describe("RequestRow (feature #185)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("åbner detalje-visningen ved klik på titlen", async () => {
    vi.spyOn(api, "getMovie").mockResolvedValue({
      id: "m1",
      title: "The Matrix",
      year: 1999,
      runtime: 136,
      genres: ["Action", "Sci-Fi"],
      rating: 8.7,
      overview: "En hacker opdager sandheden om virkeligheden.",
    });
    const user = userEvent.setup();

    render(<RequestRow request={_request()} onChanged={() => {}} />);
    await user.click(screen.getByText(/The Matrix/));

    expect(await screen.findByText("136 min")).toBeInTheDocument();
    expect(screen.getByText("Action, Sci-Fi")).toBeInTheDocument();
    expect(screen.getByText("8.7")).toBeInTheDocument();
  });

  it("åbner detalje-visningen ved klik på posteren", async () => {
    vi.spyOn(api, "getMovie").mockResolvedValue({
      id: "m1",
      title: "The Matrix",
      year: 1999,
      runtime: 136,
      genres: [],
      overview: null,
    });
    const user = userEvent.setup();

    render(<RequestRow request={_request()} onChanged={() => {}} />);
    await user.click(screen.getByText("🎬"));

    expect(await screen.findByText("136 min")).toBeInTheDocument();
  });
});

describe("RequestDetailModal (feature #185)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("henter og viser film-detaljer, inkl. spilletid", async () => {
    vi.spyOn(api, "getMovie").mockResolvedValue({
      id: "m1",
      title: "Amadeus",
      year: 1984,
      runtime: 160,
      genres: ["Drama"],
      rating: 8.4,
      overview: "Mozarts liv set gennem Salieris øjne.",
    });

    render(<RequestDetailModal mediaKind="movie" id="m1" onClose={() => {}} />);

    expect(await screen.findByText("Amadeus (1984)")).toBeInTheDocument();
    expect(screen.getByText("160 min")).toBeInTheDocument();
    expect(screen.getByText("Drama")).toBeInTheDocument();
    expect(screen.getByText("8.4")).toBeInTheDocument();
    expect(screen.getByText("Mozarts liv set gennem Salieris øjne.")).toBeInTheDocument();
  });

  it("henter TV-serie-detaljer via getTvShow, inkl. antal sæsoner i stedet for spilletid", async () => {
    vi.spyOn(api, "getTvShow").mockResolvedValue({
      id: "s1",
      name: "The Wire",
      year: 2002,
      number_of_seasons: 5,
      genres: ["Crime"],
      overview: null,
    });

    render(<RequestDetailModal mediaKind="tv" id="s1" onClose={() => {}} />);

    expect(await screen.findByText("The Wire (2002)")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.queryByText(/min$/)).not.toBeInTheDocument();
  });

  it("viser backendens specifikke fejlbesked hvis hentningen fejler", async () => {
    vi.spyOn(api, "getMovie").mockRejectedValue(new Error("Filmen findes ikke længere"));

    render(<RequestDetailModal mediaKind="movie" id="m1" onClose={() => {}} />);

    expect(await screen.findByText("Filmen findes ikke længere")).toBeInTheDocument();
  });

  it("lukker ved klik på Luk", async () => {
    vi.spyOn(api, "getMovie").mockResolvedValue({
      id: "m1",
      title: "Amadeus",
      year: 1984,
      runtime: 160,
      genres: [],
      overview: null,
    });
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(<RequestDetailModal mediaKind="movie" id="m1" onClose={onClose} />);
    await user.click(await screen.findByRole("button", { name: "Luk" }));

    expect(onClose).toHaveBeenCalled();
  });
});

/**
 * Feature #162 (Jan: "Kunne man lave en afstemning side hvor man kunne
 * stemme på nogen udvalgte film"). Det testværdige (regel 19): et klik på
 * "Stem" skal rent faktisk kalde api.votePoll med det rigtige kandidat-
 * index, sejrs-badgen skal kun vises på topscoreren efter lukning, og
 * "Planlæg"-knappen skal kun tilbydes admin på en vindende kandidat i en
 * LUKKET (ikke længere åben) afstemning.
 */
function _poll(overrides = {}) {
  return {
    id: "poll1",
    title: null,
    status: "open",
    total_votes: 3,
    my_vote: null,
    winner_indices: [],
    created_by: "creator",
    candidates: [
      { media_kind: "movie", movie_id: "m1", tv_show_id: null, title: "Dune", year: 2021, poster_url: null, vote_count: 2 },
      { media_kind: "movie", movie_id: "m2", tv_show_id: null, title: "Arrival", year: 2016, poster_url: null, vote_count: 1 },
    ],
    ...overrides,
  };
}

describe("PollCard (feature #162)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("stemmer på en kandidat og genindlæser bagefter", async () => {
    const voteSpy = vi.spyOn(api, "votePoll").mockResolvedValue(_poll());
    const onChanged = vi.fn();
    const user = userEvent.setup();

    render(<PollCard poll={_poll()} isAdmin={false} onChanged={onChanged} />);
    const voteButtons = screen.getAllByRole("button", { name: "Stem" });
    await user.click(voteButtons[1]);

    expect(voteSpy).toHaveBeenCalledWith("poll1", 1);
    expect(onChanged).toHaveBeenCalled();
  });

  it("markerer egen stemme, ikke en generisk 'Stem'-knap", async () => {
    render(<PollCard poll={_poll({ my_vote: 0 })} isAdmin={false} onChanged={() => {}} />);
    expect(await screen.findByRole("button", { name: "✓ Din stemme" })).toBeInTheDocument();
  });

  it("viser sejrs-badge kun på topscoreren efter lukning", async () => {
    render(
      <PollCard
        poll={_poll({ status: "closed", winner_indices: [0] })}
        isAdmin={false}
        onChanged={() => {}}
      />
    );
    const dune = await screen.findByText(/Dune/);
    expect(dune.textContent).toContain("🏆");
    const arrival = screen.getByText(/Arrival/);
    expect(arrival.textContent).not.toContain("🏆");
  });

  it("skjuler 'Stem'-knappen når afstemningen ikke længere er åben", async () => {
    render(
      <PollCard poll={_poll({ status: "closed", winner_indices: [0] })} isAdmin={false} onChanged={() => {}} />
    );
    await screen.findByText(/Dune/);
    expect(screen.queryByRole("button", { name: "Stem" })).not.toBeInTheDocument();
  });

  it("tilbyder kun 'Planlæg' til admin på den vindende kandidat i en lukket afstemning", async () => {
    render(
      <PollCard
        poll={_poll({ status: "closed", winner_indices: [0] })}
        isAdmin={true}
        onChanged={() => {}}
      />
    );
    const scheduleButtons = await screen.findAllByRole("button", { name: "Planlæg" });
    expect(scheduleButtons).toHaveLength(1);
  });

  it("skjuler 'Planlæg' for en ikke-admin", async () => {
    render(
      <PollCard poll={_poll({ status: "closed", winner_indices: [0] })} isAdmin={false} onChanged={() => {}} />
    );
    await screen.findByText(/Dune/);
    expect(screen.queryByRole("button", { name: "Planlæg" })).not.toBeInTheDocument();
  });

  it("viser afstemningens dato på kortet (feature #208)", async () => {
    render(<PollCard poll={_poll({ target_date: "2099-09-05T00:00:00Z" })} isAdmin={false} onChanged={() => {}} />);
    expect(await screen.findByText(/5\. sep/i)).toBeInTheDocument();
  });

  it("viser afstemningens stemme-frist på kortet, uafhængigt af dato (feature #215)", async () => {
    render(
      <PollCard
        poll={_poll({ target_date: "2099-09-05T00:00:00Z", voting_deadline: "2099-09-01T20:00:00Z" })}
        isAdmin={false}
        onChanged={() => {}}
      />
    );
    expect(await screen.findByText(/Stem senest.*1\. sep/i)).toBeInTheDocument();
  });

  it("skjuler stemme-frist-linjen når ingen frist er sat", async () => {
    render(<PollCard poll={_poll()} isAdmin={false} onChanged={() => {}} />);
    await screen.findByText(/Dune/);
    expect(screen.queryByText(/Stem senest/)).not.toBeInTheDocument();
  });

  it("foreslår afstemningens dato i planlægnings-formularen (feature #208)", async () => {
    const user = userEvent.setup();
    render(
      <PollCard
        poll={_poll({ status: "closed", winner_indices: [0], target_date: "2099-09-05T00:00:00Z" })}
        isAdmin={true}
        onChanged={() => {}}
      />
    );
    await user.click(await screen.findByRole("button", { name: "Planlæg" }));
    const dateInput = document.querySelector('input[type="date"]');
    expect(dateInput.value).toBe("2099-09-05");
  });

  it("admin kan fjerne en afstemning efter bekræftelse (feature #208-opfølgning)", async () => {
    const deleteSpy = vi.spyOn(api, "deletePoll").mockResolvedValue();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onChanged = vi.fn();
    const user = userEvent.setup();

    render(<PollCard poll={_poll()} isAdmin={true} onChanged={onChanged} />);
    await user.click(await screen.findByRole("button", { name: "Fjern" }));

    expect(deleteSpy).toHaveBeenCalledWith("poll1");
    expect(onChanged).toHaveBeenCalled();
  });

  it("annulleret bekræftelse fjerner ikke afstemningen", async () => {
    const deleteSpy = vi.spyOn(api, "deletePoll");
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();

    render(<PollCard poll={_poll()} isAdmin={true} onChanged={() => {}} />);
    await user.click(await screen.findByRole("button", { name: "Fjern" }));

    expect(deleteSpy).not.toHaveBeenCalled();
  });

  it("skjuler 'Fjern' for en ikke-admin", async () => {
    render(<PollCard poll={_poll()} isAdmin={false} onChanged={() => {}} />);
    await screen.findByText(/Dune/);
    expect(screen.queryByRole("button", { name: "Fjern" })).not.toBeInTheDocument();
  });
});

/**
 * Feature #213 (Jan: "guest kan opret en afsteming med x antal film til
 * afsteming men det er en adm som skal godkende at afsteming skal gøre
 * global for alle efter følgende og det er også adm som kan tilret listen
 * som en guest vil laveafsteming på"). Det testværdige (regel 19): en
 * 'pending' afstemning skal ikke vise stemme-furniture (der er ingen
 * stemmer endnu), kun admin skal se godkend-/redigér-knapperne, og
 * "Fjern"-knappen skal kaldes "Afvis" for netop denne status.
 */
describe("PollCard — 'pending' afstemning (feature #213)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function _pendingPoll(overrides = {}) {
    return _poll({ status: "pending", total_votes: 0, created_by: "voldbygæst", ...overrides });
  }

  it("viser 'Afventer godkendelse'-badge og skjuler stemmetal/knap", async () => {
    render(<PollCard poll={_pendingPoll()} isAdmin={false} onChanged={() => {}} />);
    expect(await screen.findByText("Afventer godkendelse")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stem" })).not.toBeInTheDocument();
    expect(screen.queryByText(/stemme/)).not.toBeInTheDocument();
  });

  it("viser hverken Godkend-, Redigér- eller Fjern/Afvis-knap for en ikke-admin", async () => {
    render(<PollCard poll={_pendingPoll()} isAdmin={false} onChanged={() => {}} />);
    await screen.findByText("Afventer godkendelse");
    expect(screen.queryByRole("button", { name: "Godkend" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Redigér kandidater" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Afvis" })).not.toBeInTheDocument();
  });

  it("admin ser hvem der foreslog den, og kan godkende", async () => {
    const approveSpy = vi.spyOn(api, "approvePoll").mockResolvedValue(_poll());
    const onChanged = vi.fn();
    const user = userEvent.setup();

    render(<PollCard poll={_pendingPoll()} isAdmin={true} onChanged={onChanged} />);
    expect(await screen.findByText("Foreslået af voldbygæst")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Godkend" }));
    expect(approveSpy).toHaveBeenCalledWith("poll1");
    expect(onChanged).toHaveBeenCalled();
  });

  it("admin ser 'Afvis' i stedet for 'Fjern', og den kalder stadig deletePoll", async () => {
    const deleteSpy = vi.spyOn(api, "deletePoll").mockResolvedValue();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();

    render(<PollCard poll={_pendingPoll()} isAdmin={true} onChanged={() => {}} />);
    expect(screen.queryByRole("button", { name: "Fjern" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Afvis" }));

    expect(window.confirm).toHaveBeenCalledWith(
      "Afvis dette afstemnings-forslag? Forslagsstilleren får besked."
    );
    expect(deleteSpy).toHaveBeenCalledWith("poll1");
  });

  it("admin kan redigere kandidatlisten og gemme den", async () => {
    vi.spyOn(api, "listMovies").mockResolvedValue({
      items: [{ id: "m3", title: "Ny Kandidat", year: 2020, poster_url: null }],
    });
    vi.spyOn(api, "listTvShows").mockResolvedValue({ items: [] });
    const updateSpy = vi.spyOn(api, "updatePollCandidates").mockResolvedValue(_poll());
    const onChanged = vi.fn();
    const user = userEvent.setup();

    render(<PollCard poll={_pendingPoll()} isAdmin={true} onChanged={onChanged} />);
    await user.click(await screen.findByRole("button", { name: "Redigér kandidater" }));

    // Fjern den ene oprindelige kandidat (Arrival), tilføj en ny.
    const removeButtons = await screen.findAllByRole("button", { name: "Fjern" });
    await user.click(removeButtons[removeButtons.length - 1]);
    await user.type(screen.getByPlaceholderText("Søg i biblioteket..."), "Ny Kandidat");
    await user.click(screen.getByRole("button", { name: "Søg" }));
    await user.click(await screen.findByText(/Ny Kandidat/));
    await user.click(screen.getByRole("button", { name: "Gem kandidater" }));

    expect(updateSpy).toHaveBeenCalledWith("poll1", [
      { media_kind: "movie", movie_id: "m1", tv_show_id: null },
      { media_kind: "movie", movie_id: "m3", tv_show_id: null },
    ]);
    expect(onChanged).toHaveBeenCalled();
  });
});

describe("Cinema — afstemninger vises for alle roller (feature #162)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listScreenings").mockResolvedValue([]);
    vi.spyOn(api, "recordVisit").mockResolvedValue();
  });

  it("viser afstemnings-sektionen for en gæst", async () => {
    vi.spyOn(api, "listPolls").mockResolvedValue([_poll()]);
    render(<Cinema user={{ role: "guest" }} />);
    expect(await screen.findByText("🗳️ Afstemninger")).toBeInTheDocument();
    expect(screen.getByText(/Dune/)).toBeInTheDocument();
  });

  it("viser 'Foreslå en afstemning' i stedet for 'Ny afstemning' for en gæst (feature #213)", async () => {
    vi.spyOn(api, "listPolls").mockResolvedValue([]);
    render(<Cinema user={{ role: "guest" }} />);
    await screen.findByText("🗳️ Afstemninger");
    expect(screen.queryByRole("button", { name: "+ Ny afstemning" })).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "+ Foreslå en afstemning" })).toBeInTheDocument();
  });

  it("viser 'Ny afstemning'-knappen for admin", async () => {
    vi.spyOn(api, "listPolls").mockResolvedValue([]);
    render(<Cinema user={{ role: "admin" }} />);
    expect(await screen.findByRole("button", { name: "+ Ny afstemning" })).toBeInTheDocument();
  });

  it("gæst ser 'Dine forslag' som overskrift over sin egen pending afstemning (feature #213)", async () => {
    vi.spyOn(api, "listPolls").mockResolvedValue([_poll({ status: "pending", created_by: "testuser" })]);
    render(<Cinema user={{ role: "guest", username: "testuser" }} />);
    expect(await screen.findByText("Dine forslag")).toBeInTheDocument();
    expect(screen.queryByText("Afventer din godkendelse")).not.toBeInTheDocument();
  });

  it("admin ser 'Afventer din godkendelse' som overskrift over andres pending afstemninger (feature #213)", async () => {
    vi.spyOn(api, "listPolls").mockResolvedValue([_poll({ status: "pending", created_by: "voldbygæst" })]);
    render(<Cinema user={{ role: "admin", username: "admin1" }} />);
    expect(await screen.findByText("Afventer din godkendelse")).toBeInTheDocument();
    expect(screen.queryByText("Dine forslag")).not.toBeInTheDocument();
  });
});
