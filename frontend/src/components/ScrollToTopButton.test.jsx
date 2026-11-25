/**
 * Feature #235 — "Til toppen". Det testværdige (regel 19): at knappen kun
 * vises når man er scrollet ned, forsvinder igen øverst, og at den scroller
 * blødt — men øjeblikkeligt ved reduceret bevægelse.
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ScrollToTopButton from "./ScrollToTopButton";

function scrollWindowTo(y) {
  act(() => {
    window.scrollY = y;
    window.dispatchEvent(new Event("scroll"));
  });
}

describe("ScrollToTopButton (feature #235)", () => {
  let originalMatchMedia;

  beforeEach(() => {
    originalMatchMedia = window.matchMedia;
    window.scrollY = 0;
    window.scrollTo = vi.fn();
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
    window.scrollY = 0;
  });

  it("vises kun når man er scrollet forbi tærsklen", () => {
    render(<ScrollToTopButton threshold={600} />);
    expect(screen.queryByRole("button", { name: "Til toppen" })).not.toBeInTheDocument();

    scrollWindowTo(601);
    expect(screen.getByRole("button", { name: "Til toppen" })).toBeInTheDocument();

    scrollWindowTo(100);
    expect(screen.queryByRole("button", { name: "Til toppen" })).not.toBeInTheDocument();
  });

  it("vises med det samme hvis siden allerede er scrollet ned ved visning", () => {
    window.scrollY = 2000;
    render(<ScrollToTopButton />);
    expect(screen.getByRole("button", { name: "Til toppen" })).toBeInTheDocument();
  });

  it("scroller blødt til toppen", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });
    window.scrollY = 2000;
    render(<ScrollToTopButton />);
    fireEvent.click(screen.getByRole("button", { name: "Til toppen" }));
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
  });

  it("virker når det er body der scroller og ikke vinduet (sådan er appens CSS)", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });
    document.body.scrollTo = vi.fn();
    render(<ScrollToTopButton threshold={600} />);
    expect(screen.queryByRole("button", { name: "Til toppen" })).not.toBeInTheDocument();

    act(() => {
      document.body.scrollTop = 1500;
      // Et scroll-event på body bobler ikke; komponenten fanger det i capture.
      document.body.dispatchEvent(new Event("scroll", { bubbles: false }));
    });
    fireEvent.click(screen.getByRole("button", { name: "Til toppen" }));
    expect(document.body.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });

    document.body.scrollTop = 0;
    delete document.body.scrollTo;
  });

  it("scroller uden animation ved reduceret bevægelse", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true });
    window.scrollY = 2000;
    render(<ScrollToTopButton />);
    fireEvent.click(screen.getByRole("button", { name: "Til toppen" }));
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "auto" });
  });
});
