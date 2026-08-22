import { describe, expect, it } from "vitest";

import {
  customEventToItem,
  labelFor,
  urgentFor,
  type CustomEvent,
} from "$lib/calendarItems";
import { isVisible, type ScheduleItem } from "$lib/schedule";

/**
 * Student-created items, and the two annotations that can land on anything.
 *
 * The store functions themselves need localStorage; the mapper and the filter
 * rules are pure and are where the decisions actually live.
 */

function event(over: Partial<CustomEvent> = {}): CustomEvent {
  return {
    id: "c1",
    title: "Coffee with Shankar",
    dayKey: "2026-08-19",
    time: "14:30",
    createdAt: 0,
    ...over,
  };
}

function item(over: Partial<ScheduleItem> = {}): ScheduleItem {
  return {
    id: "i1",
    category: "task",
    title: "Item",
    timeLabel: "9:30 AM",
    detail: "",
    sortMinutes: 570,
    allDay: false,
    ...over,
  };
}

describe("customEventToItem", () => {
  it("maps a timed event onto its day", () => {
    const result = customEventToItem(event());
    expect(result?.dayKey).toBe("2026-08-19");
    expect(result?.allDay).toBe(false);
    expect(result?.sortMinutes).toBe(14 * 60 + 30);
    expect(result?.timeLabel).toBe("2:30 PM");
  });

  it("treats a missing time as all-day rather than midnight", () => {
    const result = customEventToItem(event({ time: undefined }));
    expect(result?.allDay).toBe(true);
    expect(result?.timeLabel).toBe("All day");
    expect(result?.sortMinutes).toBe(0);
  });

  it("carries label, urgent and the custom marker", () => {
    const result = customEventToItem(
      event({ label: "thesis", urgent: true }),
    );
    expect(result?.label).toBe("thesis");
    expect(result?.urgent).toBe(true);
    expect(result?.custom).toBe(true);
    expect(result?.category).toBe("custom");
  });

  it("prefixes the id so it cannot collide with a server row", () => {
    expect(customEventToItem(event({ id: "abc" }))?.id).toBe("custom-abc");
  });

  it("attaches the event itself, so deleting never parses an id", () => {
    /*
     * The same rule `taskToItem` and `todoToItem` follow, and the reason is
     * sharper here: the item id carries `custom-` TWICE, because the event's own
     * id already begins with it. The Next version recovered the event id with
     * `item.id.replace(/^custom-/, "")` -- resolving a row by parsing its id,
     * which is the thing that silently broke ticking for self-added tasks.
     */
    const source = event({ id: "custom-1755000000000" });
    const result = customEventToItem(source);

    expect(result?.id).toBe("custom-custom-1755000000000");
    expect(result?.customEvent).toBe(source);
    // And the id the delete button needs is on the row, not in the string.
    expect(result?.customEvent?.id).toBe("custom-1755000000000");
  });

  it("rejects a malformed day key instead of guessing a day", () => {
    expect(customEventToItem(event({ dayKey: "nope" }))).toBeNull();
    expect(customEventToItem(event({ dayKey: "2026-08" }))).toBeNull();
  });

  it("rejects a date that does not exist rather than rolling it forward", () => {
    // `new Date(2026, 1, 31)` silently becomes 3 March. Storing an event on
    // "2026-02-31" must not put it on a day the student never picked.
    expect(customEventToItem(event({ dayKey: "2026-02-31" }))).toBeNull();
  });
});

/*
 * The two resolvers have TWO callers as of 7c -- `mergedSchedule`, which applies
 * them to every row on the calendar, and `ItemDetail`, which applies them to the
 * row it is showing so its controls agree with the row behind the scrim.
 *
 * Written inline in both places (which is what the Next tree did), the dialog
 * read `item.urgent` off a snapshot and never moved: un-marking urgent there
 * appeared to do nothing until the dialog was reopened. One rule, tested once.
 */
describe("labelFor and urgentFor", () => {
  it("the student's label wins over whatever the row arrived with", () => {
    expect(labelFor("i1", "from the row", { i1: "mine" })).toBe("mine");
    expect(labelFor("i1", "from the row", {})).toBe("from the row");
    expect(labelFor("i1", undefined, {})).toBeUndefined();
  });

  it("keys strictly by calendar item id", () => {
    // The third key space. A label written against a task id is not this label.
    expect(labelFor("i1", undefined, { "task-i1": "wrong" })).toBeUndefined();
  });

  it("the student's urgent flag wins, in both directions", () => {
    expect(urgentFor("i1", false, { i1: true }, false)).toBe(true);
    expect(urgentFor("i1", true, {}, false)).toBe(true);
    expect(urgentFor("i1", false, {}, false)).toBe(false);
  });

  it("done suppresses urgent, whichever side set it", () => {
    /*
     * A finished thing is not urgent, and a coral pill on a struck-through row is
     * the contradiction the reserved palette exists to prevent. In the shared rule
     * rather than in the merge, so the dialog's checkbox cannot disagree with the
     * row's pill.
     */
    expect(urgentFor("i1", true, { i1: true }, true)).toBe(false);
    expect(urgentFor("i1", true, {}, true)).toBe(false);
  });

  it("treats an absent done as not done", () => {
    // `done` is undefined on everything that is not tickable -- a class, an
    // appointment, a custom event. None of those may lose its urgent flag.
    expect(urgentFor("i1", true, {}, undefined)).toBe(true);
  });
});

describe("urgent and label filtering", () => {
  it("urgentOnly keeps only flagged items", () => {
    const filter = { hidden: [], showDone: true, urgentOnly: true };
    expect(isVisible(item({ urgent: true }), filter)).toBe(true);
    expect(isVisible(item(), filter)).toBe(false);
  });

  it("hides an item whose label is switched off", () => {
    const filter = { hidden: [], showDone: true, hiddenLabels: ["thesis"] };
    expect(isVisible(item({ label: "thesis" }), filter)).toBe(false);
    expect(isVisible(item({ label: "capstone" }), filter)).toBe(true);
  });

  it("never hides an unlabelled item via a label filter", () => {
    // Otherwise "filter by label" quietly means "hide everything unlabelled",
    // which is not what switching one chip off looks like it does.
    expect(
      isVisible(item(), { hidden: [], showDone: true, hiddenLabels: ["x"] }),
    ).toBe(true);
  });
});
