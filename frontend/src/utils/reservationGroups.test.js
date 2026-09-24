// Feature #227 — grupperingen bag "Mine pladser" og admins tilmeldte-liste.
import { describe, expect, it } from "vitest";

import {
  GLOBAL_GROUP_ID,
  freeSeatNumbers,
  groupReservationsByScreening,
} from "./reservationGroups";

const res = (id, screeningId, seatNumber, extra = {}) => ({
  id,
  screening_id: screeningId,
  seat_id: `S${seatNumber}`,
  seat_number: seatNumber,
  screening_title: `Film ${screeningId}`,
  screening_at: "2099-10-01T20:00:00",
  ...extra,
});

describe("groupReservationsByScreening", () => {
  it("samler flere sæder til samme visning i én gruppe, sorteret efter sæde", () => {
    const groups = groupReservationsByScreening([
      res("a", "s1", 7),
      res("b", "s1", 6),
      res("c", "s2", 12),
    ]);
    expect(groups).toHaveLength(2);
    expect(groups[0].screeningId).toBe("s1");
    expect(groups[0].reservations.map((r) => r.seat_number)).toEqual([6, 7]);
    expect(groups[1].reservations.map((r) => r.id)).toEqual(["c"]);
  });

  it("bevarer backendens rækkefølge af visninger", () => {
    const groups = groupReservationsByScreening([res("a", "later", 1), res("b", "sooner", 2)]);
    expect(groups.map((g) => g.screeningId)).toEqual(["later", "sooner"]);
  });

  it("springer globale hold (uden visning) over", () => {
    const groups = groupReservationsByScreening([res("a", null, 14, { scope: "global" })]);
    expect(groups).toEqual([]);
  });

  it("samler globale hold i én \"alle visninger\"-gruppe med includeGlobal (BUGS.md #100)", () => {
    const groups = groupReservationsByScreening(
      [
        res("g2", null, 14, { scope: "global", is_hold: true }),
        res("g1", null, 3, { scope: "global", is_hold: true }),
        res("a", "s1", 7),
      ],
      { includeGlobal: true }
    );
    expect(groups.map((g) => g.screeningId)).toEqual([GLOBAL_GROUP_ID, "s1"]);
    expect(groups[0].global).toBe(true);
    expect(groups[0].title).toBeNull();
    expect(groups[0].reservations.map((r) => r.seat_number)).toEqual([3, 14]);
    expect(groups[1].global).toBe(false);
  });

  it("tåler en tom eller manglende liste", () => {
    expect(groupReservationsByScreening([])).toEqual([]);
    expect(groupReservationsByScreening(undefined)).toEqual([]);
  });
});

describe("freeSeatNumbers", () => {
  const seats = [
    { id: "S1", number: 1 },
    { id: "S2", number: 2 },
    { id: "S3", number: 3 },
  ];

  it("fjerner sæder taget på visningen og globale hold, men ikke andre visningers", () => {
    const reservations = [
      { seat_id: "S1", screening_id: "mine", scope: "screening" },
      { seat_id: "S2", screening_id: null, scope: "global" },
      { seat_id: "S3", screening_id: "other", scope: "screening" },
    ];
    expect(freeSeatNumbers(seats, reservations, "mine").map((s) => s.id)).toEqual(["S3"]);
  });
});
