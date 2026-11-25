/**
 * Feature #234 — søgning og status-filter i brugerstyringen. Det testværdige
 * (regel 19): at listen faktisk filtreres, at antal står på filtrene, og at
 * en søgning uden resultater siger det i stedet for en tom liste.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { UsersSection } from "./Settings";

function _user(id, username, extra = {}) {
  return {
    id,
    username,
    full_name: null,
    email: null,
    role: "standard",
    status: "active",
    plex_play_enabled: true,
    settings: {},
    created_at: "2026-01-01T00:00:00Z",
    ...extra,
  };
}

const USERS = [
  _user("u1", "jan", { role: "admin", full_name: "Jan Grøn" }),
  _user("u2", "anna", { status: "pending" }),
  _user("u3", "bo", { email: "bo@example.com" }),
];

function names() {
  return [...document.querySelectorAll(".user-row-name")].map((el) => el.firstChild.textContent);
}

describe("UsersSection — søgning (feature #234)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
    vi.spyOn(api, "listUsers").mockResolvedValue(USERS);
  });

  it("filtrerer på navn og e-mail og viser hvor mange der vises", async () => {
    const user = userEvent.setup();
    render(<UsersSection currentUserId="u1" />);
    const search = await screen.findByRole("searchbox", { name: "Søg efter bruger" });
    expect(names()).toEqual(["jan", "anna", "bo"]);

    await user.type(search, "grøn");
    expect(names()).toEqual(["jan"]);
    expect(screen.getByText("Viser 1 af 3 brugere")).toBeInTheDocument();

    await user.clear(search);
    await user.type(search, "EXAMPLE");
    expect(names()).toEqual(["bo"]);
  });

  it("filtrerer på status med antal på knapperne", async () => {
    const user = userEvent.setup();
    render(<UsersSection currentUserId="u1" />);
    await screen.findByRole("searchbox", { name: "Søg efter bruger" });
    expect(screen.getByRole("button", { name: "Alle (3)" })).toBeInTheDocument();
    // Statusser uden brugere vises ikke.
    expect(screen.queryByRole("button", { name: /Afviste/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Afventer (1)" }));
    expect(names()).toEqual(["anna"]);
    await user.click(screen.getByRole("button", { name: "Alle (3)" }));
    expect(names()).toEqual(["jan", "anna", "bo"]);
  });

  it("siger det når ingen matcher", async () => {
    const user = userEvent.setup();
    render(<UsersSection currentUserId="u1" />);
    await user.type(await screen.findByRole("searchbox", { name: "Søg efter bruger" }), "zzz");
    expect(names()).toEqual([]);
    expect(screen.getByText("Ingen brugere matcher søgningen.")).toBeInTheDocument();
  });
});
