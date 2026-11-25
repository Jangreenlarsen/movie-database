/**
 * Feature #232 — forhåndsvisning af den samlede opdatering og plakatstriben
 * på beskeder. Det testværdige (regel 19): at previewet viser backendens
 * mail og emne, lukkes når køen ændres, at backendens fejltekst vises
 * (regel 16), og at striben begrænser sig og falder tilbage til titlen.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import AnnouncementQueueSection from "./AnnouncementQueue";
import MessageMediaStrip from "./MessageMediaStrip";

const QUEUE = [
  {
    id: "a1",
    media_kind: "movie",
    item_id: "m1",
    title: "Dune: Part Two",
    year: 2024,
    poster_url: null,
    added_by: "jan",
    created_at: "2026-09-23T10:00:00Z",
  },
];

const PREVIEW = {
  subject: "Nyt i Voldby BIO-samlingen",
  body: "• Dune: Part Two (2024, film)",
  html: "<p>MAIL</p>",
  count: 1,
};

describe("Forhåndsvisning af den samlede opdatering (feature #232)", () => {
  beforeEach(() => {
    vi.spyOn(api, "listAnnouncements").mockResolvedValue(QUEUE);
  });

  it("viser året ved titlen i køen", async () => {
    render(<AnnouncementQueueSection />);
    expect(await screen.findByText("(2024)", { exact: false })).toBeInTheDocument();
  });

  it("henter og viser mailen og emnet, og kan skjules igen", async () => {
    const preview = vi.spyOn(api, "previewAnnouncements").mockResolvedValue(PREVIEW);
    const user = userEvent.setup();
    render(<AnnouncementQueueSection />);

    await user.click(await screen.findByRole("button", { name: "Forhåndsvis mail" }));
    expect(preview).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Nyt i Voldby BIO-samlingen")).toBeInTheDocument();
    const frame = screen.getByTitle("Forhåndsvisning af den samlede opdatering");
    expect(frame).toHaveAttribute("srcdoc", "<p>MAIL</p>");

    await user.click(screen.getByRole("button", { name: "Skjul forhåndsvisning" }));
    expect(screen.queryByTitle("Forhåndsvisning af den samlede opdatering")).not.toBeInTheDocument();
  });

  it("lukker previewet når en titel fjernes, så det aldrig viser en gammel kø", async () => {
    vi.spyOn(api, "previewAnnouncements").mockResolvedValue(PREVIEW);
    vi.spyOn(api, "removeAnnouncement").mockResolvedValue(null);
    const user = userEvent.setup();
    render(<AnnouncementQueueSection />);

    await user.click(await screen.findByRole("button", { name: "Forhåndsvis mail" }));
    expect(screen.getByTitle("Forhåndsvisning af den samlede opdatering")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Fjern Dune: Part Two fra den samlede opdatering" }));
    expect(screen.queryByTitle("Forhåndsvisning af den samlede opdatering")).not.toBeInTheDocument();
  });

  it("viser backendens egen fejltekst", async () => {
    vi.spyOn(api, "previewAnnouncements").mockRejectedValue(new Error("Køen er tom"));
    const user = userEvent.setup();
    render(<AnnouncementQueueSection />);

    await user.click(await screen.findByRole("button", { name: "Forhåndsvis mail" }));
    expect(await screen.findByText("Køen er tom")).toBeInTheDocument();
  });
});

describe("MessageMediaStrip (feature #232)", () => {
  it("viser ingenting uden titler", () => {
    const { container } = render(<MessageMediaStrip media={[]} />);
    expect(container).toBeEmptyDOMElement();
    const { container: none } = render(<MessageMediaStrip />);
    expect(none).toBeEmptyDOMElement();
  });

  it("viser plakat via poster-cachen, titlen som fallback og +N for resten", () => {
    const media = [
      { title: "Med plakat", media_kind: "movie", year: 2020, poster_url: "https://image.tmdb.org/t/p/w500/abc.jpg" },
      { title: "Uden plakat", media_kind: "tv", year: null, poster_url: null },
      { title: "Tredje", media_kind: "movie", year: null, poster_url: null },
    ];
    render(<MessageMediaStrip media={media} max={2} />);
    expect(screen.getByAltText("Med plakat")).toHaveAttribute("src", "/api/posters/w185/abc.jpg");
    expect(screen.getByText("Uden plakat")).toBeInTheDocument();
    expect(screen.queryByText("Tredje")).not.toBeInTheDocument();
    expect(screen.getByText("+1")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "3 titler" })).toBeInTheDocument();
  });
});
