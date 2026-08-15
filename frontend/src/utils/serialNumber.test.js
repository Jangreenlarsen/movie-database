/**
 * Serienummer-visning (feature #92, #93, #96).
 *
 * Reglerne har ændret sig tre gange på én dag — kun fysiske, så også
 * digitale med egen serie, og til sidst uden `#`. Hver ændring rørte de
 * samme to funktioner, så de er værd at have låst fast.
 */

import { describe, expect, it } from "vitest";

import {
  DIGITAL_SERIAL_PREFIX,
  MOVIE_SERIAL_PREFIX,
  TV_SERIAL_PREFIX,
  duplicateSerialSuffix,
  formatSerial,
  isDigitalMediaType,
  serialPrefix,
} from "./serialNumber";

describe("serialPrefix", () => {
  it("vælger efter ressource når posten er fysisk", () => {
    expect(serialPrefix("Fysisk", "movie")).toBe(MOVIE_SERIAL_PREFIX);
    expect(serialPrefix("Fysisk", "tv")).toBe(TV_SERIAL_PREFIX);
  });

  it("lader medietypen vinde over ressourcen for digitale", () => {
    // Den digitale serie går på tværs af film og serier (feature #93), så
    // begge skal give D — ikke M og T.
    expect(serialPrefix("Digital", "movie")).toBe(DIGITAL_SERIAL_PREFIX);
    expect(serialPrefix("Digital", "tv")).toBe(DIGITAL_SERIAL_PREFIX);
  });

  it("behandler en manglende medietype som fysisk", () => {
    // Poster fra før medietype blev påkrævet (feature #92) — de kan lige så
    // godt være fysiske udgaver hvor feltet aldrig blev udfyldt.
    expect(serialPrefix(undefined, "movie")).toBe(MOVIE_SERIAL_PREFIX);
    expect(serialPrefix(null, "tv")).toBe(TV_SERIAL_PREFIX);
  });
});

describe("formatSerial", () => {
  it("skriver nummeret uden #", () => {
    // Feature #96 — Jans krav: serienummeret må ikke indeholde #.
    expect(formatSerial(42, 4, "M")).toBe("M0042");
    expect(formatSerial(42, 4, "M")).not.toContain("#");
  });

  it("respekterer den valgte cifferbredde", () => {
    expect(formatSerial(7, 0, "D")).toBe("D7");
    expect(formatSerial(7, 2, "D")).toBe("D07");
    expect(formatSerial(1234, 2, "D")).toBe("D1234");
  });

  it("viser en tankestreg når posten ikke har et nummer", () => {
    // Ønskelisten og — indtil feature #93 — digitale poster har intet
    // nummer. Uden dette blev der vist "MNaN" på kortene.
    expect(formatSerial(null, 4, "M")).toBe("—");
    expect(formatSerial(undefined, 4, "M")).toBe("—");
  });

  it("viser nummer 0 frem for at forveksle det med 'intet nummer'", () => {
    // 0 er falsy i JavaScript; en ren truthiness-check ville skjule det.
    expect(formatSerial(0, 3, "M")).toBe("M000");
  });
});

describe("duplicateSerialSuffix", () => {
  // BUGS.md #67 — dublet-advarslen viste et bart "#42" uden M/T/D-præfiks,
  // fordi den formaterede serienummeret selv i stedet for at bruge
  // formatSerial/serialPrefix. Låser formatet fast fremover.
  it("viser præfikset for en digital duplet, ikke et bart tal", () => {
    expect(duplicateSerialSuffix({ serial_number: 42, media_type: "Digital" }, "movie", 4)).toBe(
      " (D0042)"
    );
  });

  it("viser M/T-præfikset for en fysisk duplet, efter ressourcen", () => {
    expect(duplicateSerialSuffix({ serial_number: 7, media_type: "Fysisk" }, "movie", 0)).toBe(
      " (M7)"
    );
    expect(duplicateSerialSuffix({ serial_number: 7, media_type: "Fysisk" }, "tv", 0)).toBe(
      " (T7)"
    );
  });

  it("indeholder aldrig #, samme regel som formatSerial", () => {
    expect(duplicateSerialSuffix({ serial_number: 42, media_type: "Fysisk" }, "movie", 4)).not.toContain(
      "#"
    );
  });

  it("er tom streng uden noget nummer (fx et dublet-fund på ønskelisten)", () => {
    expect(duplicateSerialSuffix({ serial_number: null, media_type: null }, "movie", 4)).toBe("");
  });
});

describe("isDigitalMediaType", () => {
  // Feature #158 — Print-sidens digital/fysisk-opdeling. En forkert
  // klassificering her ville lægge en post på den forkerte udskrift, uden at
  // nogen opdager det før de mangler den fysisk på hylden.
  it("kalder kun 'Digital' digital", () => {
    expect(isDigitalMediaType("Digital")).toBe(true);
  });

  it("behandler alt andet som fysisk, samme regel som serialPrefix", () => {
    expect(isDigitalMediaType("Fysisk")).toBe(false);
    expect(isDigitalMediaType(undefined)).toBe(false);
    expect(isDigitalMediaType(null)).toBe(false);
    expect(isDigitalMediaType("")).toBe(false);
  });
});
