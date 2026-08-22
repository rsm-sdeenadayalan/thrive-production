import { describe, expect, it } from "vitest";

import {
  dayKeyOf,
  filterSchedule,
  groupAgenda,
  groupDayItems,
  isVisible,
  nextUpItem,
  weekGrid,
  type DatedScheduleItem,
  type ScheduleData,
  type ScheduleItem,
} from "$lib/schedule";

/**
 * The calendar's pure layer.
 *
 * These are the functions the month dots, the week columns, the agenda and the
 * day lists all share. If they disagree, the grid promises something the list
 * does not deliver -- which is the exact bug class this file exists to stop.
 */

function item(over: Partial<DatedScheduleItem> = {}): DatedScheduleItem {
  return {
    id: "i1",
    category: "class",
    title: "Item",
    dayKey: "2026-08-17",
    timeLabel: "9:30 AM",
    detail: "",
    sortMinutes: 570,
    allDay: false,
    ...over,
  };
}

function data(dated: DatedScheduleItem[] = []): ScheduleData {
  return {
    dated,
    recurring: [
      {
        id: "c1",
        dayOfWeek: 1, // Monday
        title: "MGT 142",
        detail: "Otterson 1S118",
        startTime: "09:30",
        timeLabel: "9:30 AM",
      },
    ],
  };
}

describe("isVisible", () => {
  it("hides a category the student switched off", () => {
    expect(
      isVisible(item({ category: "club" }), {
        hidden: ["club"],
        showDone: true,
      }),
    ).toBe(false);
  });

  it("hides done items unless showDone", () => {
    const done = item({ category: "task", done: true });
    expect(isVisible(done, { hidden: [], showDone: false })).toBe(false);
    expect(isVisible(done, { hidden: [], showDone: true })).toBe(true);
  });

  it("never hides an untickable item via showDone", () => {
    // A class has no `done` field at all. `!showDone && undefined === true` must
    // not accidentally filter it out.
    expect(isVisible(item(), { hidden: [], showDone: false })).toBe(true);
  });
});

describe("filterSchedule", () => {
  it("drops recurring classes when class is hidden", () => {
    const result = filterSchedule(data(), { hidden: ["class"], showDone: true });
    expect(result.recurring).toHaveLength(0);
  });

  it("keeps recurring classes when class is visible", () => {
    const result = filterSchedule(data(), { hidden: ["club"], showDone: true });
    expect(result.recurring).toHaveLength(1);
  });

  it("filters dated rows by the same rule as isVisible", () => {
    const result = filterSchedule(
      data([
        item({ id: "a", category: "task", done: true }),
        item({ id: "b", category: "task", done: false }),
      ]),
      { hidden: [], showDone: false },
    );

    expect(result.dated.map((row) => row.id)).toEqual(["b"]);
  });
});

describe("nextUpItem", () => {
  const items: ScheduleItem[] = [
    item({ id: "morning", sortMinutes: 540 }),
    item({ id: "noon", sortMinutes: 720 }),
    item({ id: "evening", sortMinutes: 1080 }),
  ];

  it("picks the first item at or after now", () => {
    expect(nextUpItem(items, 600)?.id).toBe("noon");
  });

  it("includes an item starting exactly now", () => {
    expect(nextUpItem(items, 720)?.id).toBe("noon");
  });

  it("returns null once the day is over", () => {
    expect(nextUpItem(items, 1200)).toBeNull();
  });

  it("returns null for an empty day", () => {
    expect(nextUpItem([], 0)).toBeNull();
  });

  it("skips done items", () => {
    const withDone = [
      item({ id: "done", sortMinutes: 600, done: true }),
      item({ id: "next", sortMinutes: 700 }),
    ];
    expect(nextUpItem(withDone, 0)?.id).toBe("next");
  });

  it("skips all-day items, which have no meaningful time", () => {
    const withAllDay = [
      item({ id: "allday", sortMinutes: 0, allDay: true }),
      item({ id: "timed", sortMinutes: 600 }),
    ];
    expect(nextUpItem(withAllDay, 0)?.id).toBe("timed");
  });
});

describe("groupAgenda", () => {
  const days = ["2026-08-17", "2026-08-18"]; // Monday, Tuesday

  it("groups by day and drops empty days", () => {
    const groups = groupAgenda(
      data([item({ id: "a", dayKey: "2026-08-18" })]),
      days,
      "day",
    );

    // Monday still has the recurring class, Tuesday has the dated item.
    expect(groups.map((group) => group.key)).toEqual(days);
    expect(groups[0].items).toHaveLength(1);
    expect(groups[1].items).toHaveLength(1);
  });

  it("expands recurring classes into the range", () => {
    const groups = groupAgenda(data(), ["2026-08-17"], "category");
    expect(groups[0].heading).toBe("Class");
    expect(groups[0].items[0].title).toBe("MGT 142");
  });

  it("groups by category in legend order, not insertion order", () => {
    const groups = groupAgenda(
      data([
        item({ id: "t", category: "todo", dayKey: "2026-08-18" }),
        item({ id: "a", category: "appointment", dayKey: "2026-08-18" }),
      ]),
      days,
      "category",
    );

    // legendOrder puts class, then appointment, then todo.
    expect(groups.map((group) => group.key)).toEqual([
      "class",
      "appointment",
      "todo",
    ]);
  });

  it("groups by course and puts everything courseless in one bucket, last", () => {
    const groups = groupAgenda(
      data([
        item({ id: "x", category: "task", courseCode: "MGT 253" }),
        item({ id: "y", category: "todo" }),
      ]),
      ["2026-08-17"],
      "course",
    );

    expect(groups[0].key).toBe("MGT 253");
    const last = groups[groups.length - 1];
    expect(last.key).toBe("__none");
    // The recurring class has no courseCode either, so it lands here too.
    expect(last.items.length).toBeGreaterThanOrEqual(2);
  });

  it("returns no groups for an empty range", () => {
    expect(groupAgenda({ dated: [], recurring: [] }, days, "day")).toEqual([]);
  });
});

describe("groupDayItems", () => {
  it("orders groups by kind of obligation, not by time or legend order", () => {
    const groups = groupDayItems([
      item({ id: "apt", category: "appointment", sortMinutes: 60 }),
      item({ id: "todo", category: "todo" }),
      item({ id: "task", category: "task" }),
      item({ id: "asg", category: "assignment" }),
      item({ id: "cls", category: "class", sortMinutes: 1400 }),
    ]);

    expect(groups.map((group) => group.key)).toEqual([
      "classes",
      "due",
      "tasks",
      "todos",
      "appointments",
    ]);
  });

  it("drops empty groups rather than heading over nothing", () => {
    const groups = groupDayItems([item({ category: "class" })]);
    expect(groups).toHaveLength(1);
    expect(groups[0].heading).toBe("Classes");
  });

  it("excludes events, which keep their own section", () => {
    const groups = groupDayItems([
      item({ id: "e1", category: "club" }),
      item({ id: "e2", category: "career" }),
    ]);
    expect(groups).toEqual([]);
  });

  it("returns nothing for an empty day", () => {
    expect(groupDayItems([])).toEqual([]);
  });
});

/**
 * NEW IN THE SVELTEKIT PORT, not one of the 83 ported tests.
 *
 * `dayKeyOf` absorbed `localDayKey(iso)` from format.ts, so it now takes a Date
 * or an ISO string. Every ported test passes a Date, which left the string
 * branch -- the half that was localDayKey -- with no coverage at all.
 *
 * What matters is not that each branch works but that the two AGREE. The whole
 * reason for collapsing them was that two functions computing one string
 * eventually disagree about a timezone edge; a test that only exercised one
 * path would not have caught that.
 */
describe("dayKeyOf, the collapsed local-day key", () => {
  it("agrees between a Date and the same instant as an ISO string", () => {
    const evening = new Date(2026, 7, 17, 22, 30);
    expect(dayKeyOf(evening)).toBe(dayKeyOf(evening.toISOString()));
  });

  it("builds the key from LOCAL parts, not UTC", () => {
    // 10:30pm local on the 17th. `toISOString().slice(0, 10)` would say the
    // 18th anywhere behind UTC, which is the bug localDayKey existed to avoid
    // and which this function now has to keep avoiding for both signatures.
    const evening = new Date(2026, 7, 17, 22, 30);
    expect(dayKeyOf(evening)).toBe("2026-08-17");
    expect(dayKeyOf(evening.toISOString())).toBe("2026-08-17");
  });

  it("pads a single-digit month and day", () => {
    expect(dayKeyOf(new Date(2026, 0, 5, 12, 0))).toBe("2026-01-05");
  });
});

describe("weekGrid", () => {
  it("returns seven days starting Sunday", () => {
    // 2026-08-19 is a Wednesday.
    expect(weekGrid("2026-08-19")).toEqual([
      "2026-08-16",
      "2026-08-17",
      "2026-08-18",
      "2026-08-19",
      "2026-08-20",
      "2026-08-21",
      "2026-08-22",
    ]);
  });

  it("does not shift when the day is already Sunday", () => {
    expect(weekGrid("2026-08-16")[0]).toBe("2026-08-16");
  });

  it("crosses a month boundary without drifting", () => {
    expect(weekGrid("2026-09-01")).toEqual([
      "2026-08-30",
      "2026-08-31",
      "2026-09-01",
      "2026-09-02",
      "2026-09-03",
      "2026-09-04",
      "2026-09-05",
    ]);
  });
});
