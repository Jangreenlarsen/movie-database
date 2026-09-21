/**
 * BUGS.md #98 — App.jsx's "/login"-pathname-tjek matcher på ethvert render
 * uanset `user`-state, så et vellykket login uden selv at rydde pathname'et
 * lod brugeren stå på selve login-formularen i stedet for at lande i appen
 * (regel 19, "tilstands-skift i et vindue").
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./api/client";
import App from "./App";

function activeUser(overrides = {}) {
  return {
    id: "u1",
    username: "jan",
    role: "standard",
    status: "active",
    must_change_password: false,
    settings: { theme: "dark", language: "da" },
    ...overrides,
  };
}

describe("App — login på den direkte /login-adresse (BUGS.md #98)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.pushState(null, "", "/login");
    vi.spyOn(api, "health").mockResolvedValue({ version: "0.0.0", build: "0000" });
    vi.spyOn(api, "getLibraryCounts").mockResolvedValue({
      movies: { total: 0, physical: 0, digital: 0, wishlist: 0 },
      tv_shows: { total: 0, physical: 0, digital: 0, wishlist: 0 },
    });
    vi.spyOn(api, "recordVisit").mockResolvedValue();
    vi.spyOn(api, "getInbox").mockResolvedValue([]);
  });

  it("forlader /login og viser appen efter et vellykket login", async () => {
    vi.spyOn(api, "me").mockRejectedValue(new Error("ikke logget ind"));
    vi.spyOn(api, "login").mockResolvedValue(activeUser());
    const user = userEvent.setup();

    render(<App />);

    await user.type(await screen.findByLabelText("Brugernavn"), "jan");
    await user.type(screen.getByLabelText("Adgangskode"), "hunter2");
    await user.click(screen.getByRole("button", { name: "Log ind" }));

    await waitFor(() => expect(window.location.pathname).toBe("/"));
    expect(await screen.findByText("Log ud")).toBeInTheDocument();
    expect(screen.queryByLabelText("Brugernavn")).not.toBeInTheDocument();
  });

  it("navigerer også væk fra /login ved en allerede gyldig session (intet login-tryk)", async () => {
    // Åbner /login direkte mens en gyldig cookie/session allerede findes —
    // samme rodårsag som login-trykket ovenfor (pathname-tjekket matchede
    // uanset `user`), men udløst af `api.me()` alene i stedet for et tryk.
    vi.spyOn(api, "me").mockResolvedValue(activeUser());

    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe("/"));
    expect(await screen.findByText("Log ud")).toBeInTheDocument();
    expect(screen.queryByLabelText("Brugernavn")).not.toBeInTheDocument();
  });
});
