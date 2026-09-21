/**
 * BUGS.md #95 — `DateField` er den eneste vagtpost mod at
 * "Vælg dato"-hjælpeteksten enten (a) aldrig vises på iOS, hvor den native
 * `<input type="date">` ellers er fuldstændig usynlig når den er tom, eller
 * (b) vises oven i den allerede-fungerende native placeholder på desktop,
 * hvor den bare ville se ud som dobbelt tekst (regel 19).
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DateField from "./DateField";

function stubPlatform({ ios }) {
  vi.stubGlobal(
    "navigator",
    ios
      ? { userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)", platform: "iPhone", maxTouchPoints: 5 }
      : { userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", platform: "Win32", maxTouchPoints: 0 }
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DateField", () => {
  it("viser hjælpeteksten på iOS når feltet er tomt", () => {
    stubPlatform({ ios: true });
    render(<DateField value="" onChange={() => {}} />);
    expect(screen.getByText("Vælg dato")).toBeInTheDocument();
  });

  it("skjuler hjælpeteksten på iOS så snart en dato er valgt", () => {
    stubPlatform({ ios: true });
    render(<DateField value="2026-09-21" onChange={() => {}} />);
    expect(screen.queryByText("Vælg dato")).not.toBeInTheDocument();
  });

  it("viser ALDRIG hjælpeteksten uden for iOS — den native placeholder virker allerede der", () => {
    stubPlatform({ ios: false });
    render(<DateField value="" onChange={() => {}} />);
    expect(screen.queryByText("Vælg dato")).not.toBeInTheDocument();
  });

  it("sender stadig ændringer videre til onChange", () => {
    stubPlatform({ ios: false });
    const onChange = vi.fn();
    const { container } = render(<DateField value="" onChange={onChange} />);
    fireEvent.change(container.querySelector('input[type="date"]'), { target: { value: "2026-09-21" } });
    expect(onChange).toHaveBeenCalled();
  });
});
