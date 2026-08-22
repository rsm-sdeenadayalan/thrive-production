import { describe, expect, it } from "vitest";

import { DEFAULT_PREFS, normalisePrefs } from "$lib/calendarPrefs";

/**
 * Prefs normalisation.
 *
 * The input to this function is whatever happens to be sitting in a browser's
 * localStorage: a value written by a previous build, a half-completed write, or
 * something a curious student edited by hand. None of those may take the page
 * down, and none may silently hide the calendar's contents.
 */

describe("normalisePrefs", () => {
  it("returns the defaults for nothing stored", () => {
    expect(normalisePrefs(undefined)).toEqual(DEFAULT_PREFS);
  });

  it("defaults to showing everything, not hiding everything", () => {
    // The failure that matters: a bad stored value must never leave the student
    // looking at an empty calendar with no explanation.
    expect(normalisePrefs({}).hidden).toEqual([]);
    expect(normalisePrefs({}).view).toBe("month");
    // Done items show by default here: ticking something on a calendar must
    // not make it vanish under the cursor.
    expect(normalisePrefs({}).showDone).toBe(true);
  });

  it("keeps a valid stored value", () => {
    const stored = {
      hidden: ["club" as const],
      hiddenLabels: ["thesis"],
      showDone: true,
      urgentOnly: true,
      showIgnored: true,
      view: "agenda" as const,
      groupBy: "course" as const,
      dayGroupBy: "time" as const,
    };
    expect(normalisePrefs(stored)).toEqual(stored);
  });

  it("defaults showIgnored to false, so ignored events stay hidden", () => {
    // The calendar keeps them recoverable, but not visible until asked for.
    expect(normalisePrefs({}).showIgnored).toBe(false);
    expect(
      normalisePrefs({ showIgnored: "yes" as unknown as boolean }).showIgnored,
    ).toBe(false);
  });

  it("repairs a non-array hiddenLabels and a non-boolean urgentOnly", () => {
    expect(
      normalisePrefs({ hiddenLabels: "thesis" as unknown as [] }).hiddenLabels,
    ).toEqual([]);
    expect(
      normalisePrefs({ urgentOnly: 1 as unknown as boolean }).urgentOnly,
    ).toBe(false);
  });

  it("defaults the day arrangement to type, not time", () => {
    // The deliberate choice: "what do I owe" before "what happens next".
    expect(normalisePrefs({}).dayGroupBy).toBe("type");
    expect(
      normalisePrefs({ dayGroupBy: "sideways" as unknown as "time" })
        .dayGroupBy,
    ).toBe("type");
  });

  it("repairs a non-array hidden", () => {
    // A previous build could have stored an object here.
    expect(
      normalisePrefs({ hidden: "club" as unknown as [] }).hidden,
    ).toEqual([]);
  });

  it("repairs a non-boolean showDone", () => {
    expect(
      normalisePrefs({ showDone: "yes" as unknown as boolean }).showDone,
    ).toBe(true);
  });

  it("falls back to month for an unknown view", () => {
    expect(
      normalisePrefs({ view: "timeline" as unknown as "month" }).view,
    ).toBe("month");
  });

  it("falls back to day for an unknown groupBy", () => {
    expect(
      normalisePrefs({ groupBy: "colour" as unknown as "day" }).groupBy,
    ).toBe("day");
  });

  it("fills in a field a previous build never wrote", () => {
    // Storage written before `groupBy` existed.
    const partial = { hidden: [], showDone: false, view: "week" as const };
    const result = normalisePrefs(partial);
    expect(result.groupBy).toBe("day");
    expect(result.view).toBe("week");
    expect(result.showDone).toBe(false);
  });
});
