/**
 * Feature #228 — "Samlet opdatering". Det testværdige (regel 19): at
 * afsendelse kræver bekræftelse og viser resultatet, at en fjernet titel
 * forsvinder uden at røre resten, at backendens egen fejltekst vises
 * (regel 16 — fx test-tilstand), og at påmindelsen kun vises med en kø.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import AnnouncementQueueSection, { AnnouncementReminder } from "./AnnouncementQueue";

const QUEUE = [
  {
    id: "a1",
    media_kind: "movie",
    item_id: "m1",
    title: "Dune: Part Two",
    poster_url: null,
    added_by: "jan",
    created_at: "2026-09-23T10:00:00Z",
  },
  {
    id: "a2",
    media_kind: "tv",
    item_id: "t1",
    title: "The Bear",
    poster_url: null,
    added_by: "anna",
    created_at: "2026-09-23T11:00:00Z",
  },
];

describe("AnnouncementQueueSection (feature #228)", () => {
  beforeEach(() => {
    vi.spyOn(api, "listAnnouncements").mockResolvedValue(QUEUE);
  });

  it("viser titlerne i køen med type og hvem der tilføjede dem", async () => {
    render(<AnnouncementQueueSection />);
    const dune = (await screen.findByText("Dune: Part Two")).closest("li");
    expect(within(dune).getByText(/Film · tilføjet af jan/)).toBeInTheDocument();
    const bear = screen.getByText("The Bear").closest("li");
    expect(within(bear).getByText(/Serie · tilføjet af anna/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Send samlet opdatering til alle (2 titler)" })
    ).toBeInTheDocument();
  });

  it("sender hele køen efter bekræftelse og viser hvor mange der var med", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const send = vi.spyOn(api, "sendAnnouncements").mockResolvedValue({ sent_count: 2 });
    const user = userEvent.setup();
    render(<AnnouncementQueueSection />);

    await user.click(
      await screen.findByRole("button", { name: "Send samlet opdatering til alle (2 titler)" })
    );
    expect(send).toHaveBeenCalledTimes(1);

    api.listAnnouncements.mockResolvedValue([]);
    // Resultatet hentes igen efter afsendelse — køen er tom.
    expect(await screen.findByText("Sendt til alle — 2 titler var med.")).toBeInTheDocument();
  });

  it("sender intet når bekræftelsen fortrydes", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const send = vi.spyOn(api, "sendAnnouncements").mockResolvedValue({ sent_count: 2 });
    const user = userEvent.setup();
    render(<AnnouncementQueueSection />);

    await user.click(
      await screen.findByRole("button", { name: "Send samlet opdatering til alle (2 titler)" })
    );
    expect(send).not.toHaveBeenCalled();
  });

  it("viser backendens fejltekst når afsendelsen afvises", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "sendAnnouncements").mockRejectedValue(
      new Error("Test-tilstand er slået til — der sendes ingen beskeder")
    );
    const user = userEvent.setup();
    render(<AnnouncementQueueSection />);

    await user.click(
      await screen.findByRole("button", { name: "Send samlet opdatering til alle (2 titler)" })
    );
    expect(
      await screen.findByText("Test-tilstand er slået til — der sendes ingen beskeder")
    ).toBeInTheDocument();
    // Køen står der stadig.
    expect(screen.getByText("Dune: Part Two")).toBeInTheDocument();
  });

  it("fjerner én titel uden at røre de andre", async () => {
    const remove = vi.spyOn(api, "removeAnnouncement").mockResolvedValue(null);
    const user = userEvent.setup();
    render(<AnnouncementQueueSection />);

    await user.click(
      await screen.findByRole("button", { name: "Fjern Dune: Part Two fra den samlede opdatering" })
    );
    expect(remove).toHaveBeenCalledWith("a1");
    await waitFor(() => expect(screen.queryByText("Dune: Part Two")).toBeNull());
    expect(screen.getByText("The Bear")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Send samlet opdatering til alle (1 titel)" })
    ).toBeInTheDocument();
  });

  it("viser en tom-tilstand uden send-knap", async () => {
    api.listAnnouncements.mockResolvedValue([]);
    render(<AnnouncementQueueSection />);
    expect(await screen.findByText(/Ingen titler venter/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Send samlet opdatering/ })).toBeNull();
  });
});

describe("AnnouncementReminder (feature #228)", () => {
  it("vises med antal og åbner køen", async () => {
    vi.spyOn(api, "listAnnouncements").mockResolvedValue(QUEUE);
    const onOpen = vi.fn();
    const user = userEvent.setup();
    render(<AnnouncementReminder onOpen={onOpen} />);

    expect(
      await screen.findByText("2 nye titler venter på den samlede opdatering")
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Se og send" }));
    expect(onOpen).toHaveBeenCalled();
  });

  it("er skjult når køen er tom, og dukker op når en titel lægges i kø", async () => {
    const list = vi.spyOn(api, "listAnnouncements").mockResolvedValue([]);
    render(<AnnouncementReminder onOpen={() => {}} />);
    await waitFor(() => expect(list).toHaveBeenCalled());
    expect(screen.queryByRole("status")).toBeNull();

    list.mockResolvedValue([QUEUE[0]]);
    window.dispatchEvent(new Event("announcements:changed"));
    expect(
      await screen.findByText("1 ny titel venter på den samlede opdatering")
    ).toBeInTheDocument();
  });
});
