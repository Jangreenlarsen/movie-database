/**
 * Oversætter-motoren (feature #89).
 *
 * De tre ting der kan gå galt uden at nogen opdager det: en manglende
 * oversættelse der falder tilbage til det forkerte, en pladsholder der ikke
 * bliver udfyldt, og et flertal der vælger den forkerte form.
 */

import { describe, expect, it } from "vitest";

import da from "./da.json";
import en from "./en.json";
import { LANGUAGES, SOURCE_LANGUAGE, createTranslator, hasCatalog } from "./index";

describe("katalogerne", () => {
  it("har præcis de samme nøgler på begge sprog", () => {
    // En nøgle der kun findes på det ene sprog viser dansk tekst midt i en
    // engelsk brugerflade — synligt for brugeren, usynligt i koden.
    const onlyDa = Object.keys(da).filter((key) => !(key in en));
    const onlyEn = Object.keys(en).filter((key) => !(key in da));
    expect({ onlyDa, onlyEn }).toEqual({ onlyDa: [], onlyEn: [] });
  });

  it("har de samme pladsholdere i hver oversættelse", () => {
    // En manglende {navn} i den ene oversættelse giver en halvfærdig
    // sætning uden at fejle nogen steder.
    const placeholders = (text) => (text.match(/\{(\w+)\}/g) ?? []).sort();
    const mismatched = Object.keys(da).filter(
      (key) => String(placeholders(da[key])) !== String(placeholders(en[key]))
    );
    expect(mismatched).toEqual([]);
  });

  it("har ingen tomme oversættelser", () => {
    const empty = Object.entries({ ...da, ...en })
      .filter(([, value]) => !String(value).trim())
      .map(([key]) => key);
    expect(empty).toEqual([]);
  });

  it("dækker alle sprog i LANGUAGES", () => {
    for (const language of LANGUAGES) {
      expect(hasCatalog(language.code)).toBe(true);
      expect(language.short).toBeTruthy();
    }
  });
});

describe("createTranslator", () => {
  it("oversætter en kendt nøgle", () => {
    expect(createTranslator("en")("app.nav.movies")).toBe("Movies");
    expect(createTranslator("da")("app.nav.movies")).toBe("Film");
  });

  it("falder tilbage til kildesproget for en nøgle der mangler oversættelse", () => {
    // Dansk skrives først, så en endnu ikke oversat nøgle skal vise dansk
    // tekst frem for en rå nøgle midt i brugerfladen.
    const t = createTranslator("en");
    expect(t("app.nav.cinema")).toBe(da["app.nav.cinema"]);
  });

  it("viser den rå nøgle når den slet ikke findes", () => {
    // Grimt med vilje: en manglende oversættelse skal være til at få øje på
    // frem for at gemme sig som tom tekst.
    expect(createTranslator("da")("findes.slet.ikke")).toBe("findes.slet.ikke");
  });

  it("falder tilbage til kildesproget for et ukendt sprog", () => {
    expect(createTranslator("de")("app.nav.movies")).toBe(da["app.nav.movies"]);
  });

  it("indsætter pladsholdere", () => {
    const t = createTranslator("da");
    expect(t("lib.count", { count: 3 })).toBe("3 film");
  });

  it("lader en pladsholder stå hvis værdien mangler", () => {
    // Bedre end at skrive "undefined" ud til brugeren: det er tydeligt at
    // noget mangler, og det peger på hvilket felt.
    const t = createTranslator("da");
    expect(t("lib.count", {})).toContain("{count}");
  });

  it("indsætter 0 frem for at behandle det som en manglende værdi", () => {
    const t = createTranslator("da");
    expect(t("lib.count", { count: 0 })).toBe("0 film");
  });

  it("bruger kildesproget som standard", () => {
    expect(createTranslator(SOURCE_LANGUAGE)("app.nav.movies")).toBe(da["app.nav.movies"]);
  });
});
