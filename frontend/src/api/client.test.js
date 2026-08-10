/**
 * BUGS.md #54 — fejlbeskeder fra backend.
 *
 * Denne fil findes fordi fejlen slap igennem: `readableDetail` blev skrevet
 * som en rettelse, men der var ingen frontend-testsuite til at låse den
 * fast. De to former for `detail` — streng fra vores egne fejl, liste fra
 * FastAPIs validering — er præcis det der gik galt, og skal derfor være det
 * første der er dækket.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";

function mockResponse({ ok = false, status = 400, body }) {
  return {
    ok,
    status,
    json: async () => {
      if (body === undefined) throw new Error("no json body");
      return body;
    },
  };
}

describe("fejlbeskeder fra backend", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("viser vores egne HTTPException-beskeder som de er", async () => {
    fetch.mockResolvedValue(
      mockResponse({ status: 409, body: { detail: "Brugernavnet er taget" } })
    );

    await expect(api.health()).rejects.toThrow("Brugernavnet er taget");
  });

  it("trækker beskeden ud af FastAPIs 422-liste", async () => {
    // Det var her fejlen lå: listen blev givet direkte til `new Error(...)`,
    // og brugeren så "[object Object]".
    fetch.mockResolvedValue(
      mockResponse({
        status: 422,
        body: {
          detail: [
            {
              type: "value_error",
              loc: ["body", "username"],
              msg: "Value error, Brugernavn må kun indeholde bogstaver, tal, - og _",
            },
          ],
        },
      })
    );

    await expect(api.health()).rejects.toThrow(
      "Brugernavn må kun indeholde bogstaver, tal, - og _"
    );
  });

  it("fjerner Pydantics 'Value error, '-præfiks", async () => {
    fetch.mockResolvedValue(
      mockResponse({
        status: 422,
        body: { detail: [{ msg: "Value error, Feltet må ikke være tomt" }] },
      })
    );

    await expect(api.health()).rejects.toThrow(/^Feltet må ikke være tomt$/);
  });

  it("samler flere fejl, så et felt ikke skjuler et andet", async () => {
    fetch.mockResolvedValue(
      mockResponse({
        status: 422,
        body: {
          detail: [{ msg: "Brugernavn er for kort" }, { msg: "Adgangskode er for kort" }],
        },
      })
    );

    await expect(api.health()).rejects.toThrow(
      "Brugernavn er for kort · Adgangskode er for kort"
    );
  });

  it("falder tilbage til status og sti når svaret ikke har en brugbar besked", async () => {
    fetch.mockResolvedValue(mockResponse({ status: 500 }));

    await expect(api.health()).rejects.toThrow("API request failed: 500 /health");
  });

  it("falder også tilbage ved en tom fejl-liste", async () => {
    fetch.mockResolvedValue(mockResponse({ status: 422, body: { detail: [] } }));

    await expect(api.health()).rejects.toThrow("API request failed: 422 /health");
  });

  it("bærer statuskoden med på fejlen", async () => {
    fetch.mockResolvedValue(mockResponse({ status: 403, body: { detail: "Ingen adgang" } }));

    await expect(api.health()).rejects.toMatchObject({ status: 403 });
  });
});

describe("svar uden indhold", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("returnerer null ved 204 frem for at forsøge at læse JSON", async () => {
    // En 204 har ingen krop; `response.json()` ville kaste.
    fetch.mockResolvedValue({ ok: true, status: 204, json: async () => {
      throw new Error("ingen krop");
    } });

    await expect(api.markMessageRead("abc")).resolves.toBeNull();
  });
});
