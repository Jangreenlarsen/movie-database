/** Feature #234 — søgning og status-filter i brugerstyringen. */
import { describe, expect, it } from "vitest";

import { countByStatus, filterUsers } from "./userFilter";

const USERS = [
  { id: "1", username: "jan", full_name: "Jan Grøn", email: "jan@example.com", status: "active" },
  { id: "2", username: "anna", full_name: null, email: null, status: "pending" },
  { id: "3", username: "bo", full_name: "Bo Ærø", email: "BO@Example.com", status: "disabled" },
];

describe("filterUsers", () => {
  it("tom eller whitespace-only søgning matcher alle", () => {
    expect(filterUsers(USERS, "")).toHaveLength(3);
    expect(filterUsers(USERS, "   ")).toHaveLength(3);
    expect(filterUsers(USERS, undefined)).toHaveLength(3);
  });

  it("søger i brugernavn, fulde navn og e-mail uden forskel på store/små bogstaver", () => {
    expect(filterUsers(USERS, "ANNA").map((u) => u.id)).toEqual(["2"]);
    expect(filterUsers(USERS, "grøn").map((u) => u.id)).toEqual(["1"]);
    expect(filterUsers(USERS, "ÆRØ").map((u) => u.id)).toEqual(["3"]);
    expect(filterUsers(USERS, "example.com").map((u) => u.id)).toEqual(["1", "3"]);
    expect(filterUsers(USERS, "  bo  ").map((u) => u.id)).toEqual(["3"]);
  });

  it("tåler manglende navn/e-mail", () => {
    expect(filterUsers(USERS, "null")).toEqual([]);
  });

  it("kombinerer søgning og status", () => {
    expect(filterUsers(USERS, "", "pending").map((u) => u.id)).toEqual(["2"]);
    expect(filterUsers(USERS, "example", "active").map((u) => u.id)).toEqual(["1"]);
    expect(filterUsers(USERS, "anna", "active")).toEqual([]);
  });
});

describe("countByStatus", () => {
  it("tæller alle og hver status", () => {
    expect(countByStatus(USERS)).toEqual({ all: 3, pending: 1, active: 1, disabled: 1, rejected: 0 });
  });
});
