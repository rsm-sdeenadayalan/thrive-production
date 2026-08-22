import { describe, expect, it } from "vitest";

import type { SlotView } from "$lib/appointmentsView";
import {
  availabilityByDay,
  firstBookableDay,
  openSlotCount,
  orderedDayKeys,
  publishedByDay,
  slotsForDay,
} from "$lib/availability";

/**
 * What an advisor has open, as arithmetic.
 *
 * Nothing here reads a clock and nothing takes "today" — which is the shape of
 * what this module became. For one phase it owned a one-calendar-month BOOKING
 * WINDOW separate from the fixture, and this file froze a Monday in a 31-day
 * month to assert the coupling between the two. The chip strip made the window
 * and the published set the same thing, so `bookingWindowEnd`, `isBookableDay`
 * and `openCountInWindow` are gone and so are their tests. There is no longer a
 * second opinion for them to arbitrate.
 */

/** A slot, with only the fields the functions under test look at. */
function slot(
  id: string,
  dayKey: string,
  overrides: Partial<SlotView> = {},
): SlotView {
  return {
    id,
    advisorId: "adv-gsa",
    dayKey,
    timeLabel: "9:30 AM",
    mode: "in person",
    available: true,
    startISO: `${dayKey}T09:30:00.000Z`,
    endISO: `${dayKey}T10:00:00.000Z`,
    ...overrides,
  };
}

describe("availabilityByDay", () => {
  it("counts the open slots on each day", () => {
    const open = availabilityByDay([
      slot("a", "2026-08-21"),
      slot("b", "2026-08-21"),
      slot("c", "2026-08-24"),
    ]);

    expect(open).toEqual({ "2026-08-21": 2, "2026-08-24": 1 });
  });

  it("counts only what is available", () => {
    const open = availabilityByDay([
      slot("a", "2026-08-21", { available: false }),
      slot("b", "2026-08-21"),
    ]);

    expect(open["2026-08-21"]).toBe(1);
  });

  it("leaves a fully booked day ABSENT rather than present as zero", () => {
    // One spelling of "nothing here", so `openByDay[key] ?? 0` is the only read
    // any consumer needs and a `0` entry cannot mean something subtly different
    // from a missing one.
    const open = availabilityByDay([
      slot("a", "2026-08-21", { available: false }),
    ]);

    expect(open).toEqual({});
    expect("2026-08-21" in open).toBe(false);
  });
});

describe("publishedByDay", () => {
  it("counts every slot, taken or not", () => {
    const published = publishedByDay([
      slot("a", "2026-08-21", { available: false }),
      slot("b", "2026-08-21"),
      slot("c", "2026-08-24"),
    ]);

    expect(published).toEqual({ "2026-08-21": 2, "2026-08-24": 1 });
  });

  it("is what tells a fully booked day from a day not worked", () => {
    /*
     * The pair is the point. A Saturday and a fully-booked Tuesday both have an
     * open count of zero; only `publishedByDay` separates them. A chip says
     * "Full" about one and does not exist for the other, and calling a Saturday
     * full would be a lie.
     */
    const slots = [
      slot("a", "2026-08-25", { available: false }),
      slot("b", "2026-08-25", { available: false }),
    ];

    expect(availabilityByDay(slots)["2026-08-25"]).toBeUndefined();
    expect(publishedByDay(slots)["2026-08-25"]).toBe(2);
    // A Saturday: absent from both, so no chip at all.
    expect(publishedByDay(slots)["2026-08-29"]).toBeUndefined();
  });

  it("leaves a day with no slots absent rather than zero", () => {
    expect(publishedByDay([])).toEqual({});
  });
});

describe("orderedDayKeys", () => {
  it("sorts chronologically, which for a day key is lexicographically", () => {
    /*
     * "YYYY-MM-DD" is zero-padded and big-endian, so string order IS date order.
     * No parsing, and no timezone can get between the comparison and the answer.
     */
    const keys = orderedDayKeys({
      "2026-09-02": 1,
      "2026-08-31": 1,
      "2026-09-10": 1,
    });

    expect(keys).toEqual(["2026-08-31", "2026-09-02", "2026-09-10"]);
  });

  it("crosses a year boundary correctly", () => {
    expect(orderedDayKeys({ "2027-01-04": 1, "2026-12-31": 1 })).toEqual([
      "2026-12-31",
      "2027-01-04",
    ]);
  });

  it("is empty for an advisor who publishes nothing", () => {
    expect(orderedDayKeys({})).toEqual([]);
  });
});

describe("openSlotCount", () => {
  it("counts what is still free, across every day", () => {
    expect(
      openSlotCount([
        slot("a", "2026-08-21"),
        slot("b", "2026-08-21", { available: false }),
        slot("c", "2026-08-24"),
      ]),
    ).toBe(2);
  });

  it("is zero for a fully booked advisor", () => {
    expect(openSlotCount([slot("a", "2026-08-21", { available: false })])).toBe(
      0,
    );
  });
});

describe("firstBookableDay", () => {
  const days = ["2026-08-21", "2026-08-24", "2026-08-25"];

  it("returns the first day when the first day has room", () => {
    expect(firstBookableDay(days, { "2026-08-21": 2 })).toBe("2026-08-21");
  });

  it("skips a full first day", () => {
    /*
     * The case this exists for. Today is usually the first chip and is frequently
     * empty by mid-afternoon, because passed slots drop out of `available`.
     * Opening there would show an empty times list beside chips that do have
     * room, which reads as broken rather than as "not today".
     */
    expect(firstBookableDay(days, { "2026-08-24": 3 })).toBe("2026-08-24");
  });

  it("respects the order it was given rather than the map's", () => {
    // Object key order is insertion order, which is not the calendar's. The day
    // keys are the ordering authority.
    expect(
      firstBookableDay(days, { "2026-08-25": 1, "2026-08-24": 1 }),
    ).toBe("2026-08-24");
  });

  it("is null when every published day is full", () => {
    expect(firstBookableDay(days, {})).toBeNull();
  });

  it("is null when there are no days at all", () => {
    expect(firstBookableDay([], { "2026-08-21": 5 })).toBeNull();
  });
});

describe("slotsForDay", () => {
  const slots = [
    slot("a", "2026-08-21", { mode: "zoom" }),
    slot("b", "2026-08-21", { mode: "in person" }),
    slot("c", "2026-08-21", { mode: "zoom", available: false }),
    slot("d", "2026-08-24", { mode: "zoom" }),
  ];

  it("takes one day only", () => {
    expect(slotsForDay(slots, "2026-08-24", "any").map((s) => s.id)).toEqual([
      "d",
    ]);
  });

  it("narrows by meeting type", () => {
    expect(slotsForDay(slots, "2026-08-21", "zoom").map((s) => s.id)).toEqual([
      "a",
      "c",
    ]);
    expect(
      slotsForDay(slots, "2026-08-21", "in person").map((s) => s.id),
    ).toEqual(["b"]);
  });

  it("KEEPS taken slots", () => {
    // They render struck through and disabled. Omitting them would make a busy
    // morning look like an advisor who does not work mornings.
    expect(slotsForDay(slots, "2026-08-21", "any").map((s) => s.id)).toContain(
      "c",
    );
  });

  it("is empty for a day with nothing published", () => {
    expect(slotsForDay(slots, "2026-08-29", "any")).toEqual([]);
  });
});
