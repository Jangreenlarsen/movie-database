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
import Cinema, { RequestDetailModal, RequestRow } from "./Cinema";

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

describe("Cinema — del-link (feature #193)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listScreenings").mockResolvedValue([]);
    vi.spyOn(api, "recordVisit").mockResolvedValue();
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
