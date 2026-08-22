import { describe, expect, it } from "vitest";

import {
  describeDue,
  eventDateBlock,
  formatClockTime,
  formatLongDate,
  formatMeetingPattern,
  formatShortDate,
  formatTime,
  formatWeekdayDate,
  greetingFor,
  initialsOf,
  isToday,
  isWithinDays,
  standingLabel,
} from "$lib/format";
import type { CourseMeeting } from "$lib/data";

/**
 * The formatting vocabulary, and `describeDue` above all.
 *
 * `describeDue` is the most-used pure function in the app and the load-bearing
 * piece of "components never see a raw timestamp": everything the UI says about
 * a deadline -- the chip, the countdown, the group a task lands in, the
 * screen-reader text -- is one of the five fields it returns. It had no test
 * until this file.
 *
 * ## Two rules this file follows
 *
 * 1. `now` is ALWAYS passed explicitly. Nothing here reads the real clock, so
 *    nothing fails at midnight, on a leap day, or in another timezone. That
 *    parameter exists precisely so this is possible, which is also why it must
 *    never be removed.
 *
 * 2. Every fixture instant is built from LOCAL parts -- `new Date(y, m, d, h)`
 *    -- and only then serialised with `toISOString()`. `new Date("2026-08-17")`
 *    parses as UTC and lands on the 16th for anyone behind it, which would make
 *    these assertions pass or fail depending on the machine running them.
 *
 * `calendarDaysBetween` and `countdownPhrase` are private to format.ts, so they
 * are exercised through the public surfaces that expose them: `days` and
 * `countdown` on the descriptor, plus `isToday` and `isWithinDays`.
 */

/** Monday 17 August 2026, 09:00 local. Every case below measures from here. */
const NOW = new Date(2026, 7, 17, 9, 0);

/**
 * An ISO instant `offsetDays` from NOW's calendar day, at a local wall time.
 *
 * Noon by default, so a case is nowhere near a midnight boundary unless it is
 * deliberately put there.
 */
function due(offsetDays: number, hour = 12, minute = 0, second = 0): string {
  return new Date(2026, 7, 17 + offsetDays, hour, minute, second).toISOString();
}

// ---------------------------------------------------------------------------
// describeDue -- the four branches, and every field of each
// ---------------------------------------------------------------------------

describe("describeDue: overdue", () => {
  it("returns every field for a day-old deadline", () => {
    expect(describeDue(due(-1), NOW)).toEqual({
      urgency: "overdue",
      label: "Overdue",
      countdown: "yesterday",
      days: -1,
      fullLabel: "Was due Sunday, Aug 16",
    });
  });

  it("says Overdue alone, letting the countdown carry the number", () => {
    // The old label read "Overdue by 3 days" directly beside "3 days ago".
    const d = describeDue(due(-3), NOW);
    expect(d.label).toBe("Overdue");
    expect(d.countdown).toBe("3 days ago");
  });

  it("uses the past-tense fullLabel, not the Due one", () => {
    expect(describeDue(due(-2), NOW).fullLabel).toBe("Was due Saturday, Aug 15");
  });

  it("stays overdue however far back it goes", () => {
    const d = describeDue(due(-400), NOW);
    expect(d.urgency).toBe("overdue");
    expect(d.label).toBe("Overdue");
    expect(d.days).toBe(-400);
    expect(d.fullLabel).toBe("Was due Sunday, Jul 13");
  });
});

describe("describeDue: today", () => {
  it("returns every field", () => {
    expect(describeDue(due(0), NOW)).toEqual({
      urgency: "today",
      label: "Today",
      countdown: "today",
      days: 0,
      fullLabel: "Due today",
    });
  });

  it("says Due today rather than naming the date", () => {
    // The one branch whose fullLabel is not built from the date at all.
    expect(describeDue(due(0), NOW).fullLabel).toBe("Due today");
  });
});

describe("describeDue: tomorrow", () => {
  it("returns every field", () => {
    expect(describeDue(due(1), NOW)).toEqual({
      urgency: "upcoming",
      label: "Tomorrow",
      countdown: "tomorrow",
      days: 1,
      fullLabel: "Due tomorrow",
    });
  });

  it("is upcoming, not its own urgency", () => {
    // Only three urgencies exist. Tomorrow is a distinct LABEL, not a distinct
    // urgency, so a caller styling by urgency treats it like any other future.
    expect(describeDue(due(1), NOW).urgency).toBe("upcoming");
  });
});

describe("describeDue: the days < 7 weekday-name branch", () => {
  it("names the weekday rather than the date", () => {
    // Inside the coming week a weekday is easier to place than "Aug 19".
    expect(describeDue(due(2), NOW).label).toBe("Wed");
    expect(describeDue(due(5), NOW).label).toBe("Sat");
  });

  it("returns every field for a mid-week deadline", () => {
    expect(describeDue(due(2), NOW)).toEqual({
      urgency: "upcoming",
      label: "Wed",
      countdown: "in 2 days",
      days: 2,
      fullLabel: "Due Wednesday, Aug 19",
    });
  });

  it("uses the short weekday in the label and the long one in fullLabel", () => {
    const d = describeDue(due(5), NOW);
    expect(d.label).toBe("Sat");
    expect(d.fullLabel).toBe("Due Saturday, Aug 22");
  });
});

describe("describeDue: the fall through to formatShortDate", () => {
  it("switches to a date once the weekday would be ambiguous", () => {
    // At 7 days out "Mon" could mean today's weekday, so it becomes a date.
    expect(describeDue(due(7), NOW).label).toBe("Aug 24");
    expect(describeDue(due(8), NOW).label).toBe("Aug 25");
  });

  it("returns every field for a distant deadline", () => {
    expect(describeDue(due(14), NOW)).toEqual({
      urgency: "upcoming",
      label: "Aug 31",
      countdown: "in 2 weeks",
      days: 14,
      fullLabel: "Due Monday, Aug 31",
    });
  });

  it("crosses into another month without drifting", () => {
    expect(describeDue(due(45), NOW).label).toBe("Oct 1");
    expect(describeDue(due(45), NOW).fullLabel).toBe("Due Thursday, Oct 1");
  });
});

// ---------------------------------------------------------------------------
// describeDue -- the boundaries themselves
//
// Every one of these is a place an off-by-one would be invisible in normal use
// and wrong exactly once a day.
// ---------------------------------------------------------------------------

describe("describeDue: branch boundaries", () => {
  it("day 0 and day -1 land either side of overdue", () => {
    expect(describeDue(due(0), NOW).urgency).toBe("today");
    expect(describeDue(due(-1), NOW).urgency).toBe("overdue");
  });

  it("day 1 and day 2 land either side of the Tomorrow label", () => {
    expect(describeDue(due(1), NOW).label).toBe("Tomorrow");
    expect(describeDue(due(2), NOW).label).toBe("Wed");
  });

  it("day 6 keeps the weekday and day 7 switches to a date", () => {
    // THE `days < 7` BOUNDARY. Six is the last day inside the week.
    expect(describeDue(due(6), NOW).label).toBe("Sun");
    expect(describeDue(due(7), NOW).label).toBe("Aug 24");
  });

  it("day 6 and day 7 still share the same urgency and countdown shape", () => {
    // Only the label changes at 7. Asserting this stops a future edit from
    // moving the urgency boundary along with the label boundary.
    expect(describeDue(due(6), NOW).urgency).toBe("upcoming");
    expect(describeDue(due(7), NOW).urgency).toBe("upcoming");
    expect(describeDue(due(6), NOW).countdown).toBe("in 6 days");
    expect(describeDue(due(7), NOW).countdown).toBe("in 7 days");
  });

  it("treats exactly midnight as that whole day, not the one before", () => {
    // 00:00:00 today is today. Normalising to local midnight makes this exact
    // rather than a rounding accident.
    expect(describeDue(due(0, 0, 0, 0), NOW).days).toBe(0);
    expect(describeDue(due(0, 0, 0, 0), NOW).urgency).toBe("today");
  });

  it("holds one second before a day rollover", () => {
    expect(describeDue(due(0, 23, 59, 59), NOW).days).toBe(0);
    expect(describeDue(due(0, 23, 59, 59), NOW).label).toBe("Today");
  });

  it("flips one second after a day rollover", () => {
    expect(describeDue(due(1, 0, 0, 0), NOW).days).toBe(1);
    expect(describeDue(due(1, 0, 0, 0), NOW).label).toBe("Tomorrow");
  });

  it("is overdue at 23:59:59 the previous day", () => {
    const d = describeDue(due(-1, 23, 59, 59), NOW);
    expect(d.days).toBe(-1);
    expect(d.urgency).toBe("overdue");
    expect(d.countdown).toBe("yesterday");
  });
});

// ---------------------------------------------------------------------------
// calendarDaysBetween, through `days`
//
// Private, so it is reached through the descriptor. This is the function whose
// whole purpose is the distinction below, and the easiest one to break later by
// "simplifying" it into an elapsed-time subtraction.
// ---------------------------------------------------------------------------

describe("calendar days, not elapsed hours", () => {
  it("counts a 23:00 to 01:00 pair as one calendar day, not zero", () => {
    // TWO HOURS APART, one calendar day. An elapsed-time implementation would
    // floor this to 0 and call a deadline "today" that is actually tomorrow --
    // the single most load-bearing assertion in this file.
    const lateNow = new Date(2026, 7, 17, 23, 0);
    const d = describeDue(due(1, 1, 0), lateNow);
    expect(d.days).toBe(1);
    expect(d.label).toBe("Tomorrow");
  });

  it("counts a 01:00 to 23:00 pair on the same day as zero", () => {
    // Twenty-two hours apart, same calendar day. The mirror of the above.
    const earlyNow = new Date(2026, 7, 17, 1, 0);
    const d = describeDue(due(0, 23, 0), earlyNow);
    expect(d.days).toBe(0);
    expect(d.urgency).toBe("today");
  });

  it("is zero for the same instant", () => {
    expect(describeDue(NOW.toISOString(), NOW).days).toBe(0);
  });

  it("is one for adjacent days regardless of the times of day", () => {
    expect(describeDue(due(1, 0, 1), NOW).days).toBe(1);
    expect(describeDue(due(1, 23, 59), NOW).days).toBe(1);
  });

  it("crosses a month boundary", () => {
    const endOfAugust = new Date(2026, 7, 31, 9, 0);
    const septemberFirst = new Date(2026, 8, 1, 9, 0).toISOString();
    expect(describeDue(septemberFirst, endOfAugust).days).toBe(1);
  });

  it("crosses a year boundary", () => {
    const newYearsEve = new Date(2026, 11, 31, 9, 0);
    const newYearsDay = new Date(2027, 0, 1, 9, 0).toISOString();
    expect(describeDue(newYearsDay, newYearsEve).days).toBe(1);
  });

  it("counts a span that crosses a year correctly, not modulo the year", () => {
    const midDecember = new Date(2026, 11, 15, 9, 0);
    const midJanuary = new Date(2027, 0, 15, 9, 0).toISOString();
    expect(describeDue(midJanuary, midDecember).days).toBe(31);
  });

  it("counts the leap day in a leap year", () => {
    // 2028 has a 29 February, so 28 Feb to 1 Mar is two days, not one.
    const leapFeb28 = new Date(2028, 1, 28, 9, 0);
    const leapMar1 = new Date(2028, 2, 1, 9, 0).toISOString();
    expect(describeDue(leapMar1, leapFeb28).days).toBe(2);
  });

  it("counts calendar days across a spring DST transition", () => {
    /*
     * In a DST-observing zone this span is 47 hours, not 48, because a clock
     * hour disappears. `Math.round` in calendarDaysBetween is what makes the
     * answer 2 anyway; a `Math.floor` would say 1.
     *
     * The assertion holds in a zone without DST too (a clean 48 hours), so this
     * test is safe everywhere -- it simply only has diagnostic teeth in a zone
     * that observes it. Verified as 47 hours on America/Los_Angeles.
     */
    const beforeSpringForward = new Date(2026, 2, 7, 0, 0);
    const afterSpringForward = new Date(2026, 2, 9, 0, 0).toISOString();
    expect(describeDue(afterSpringForward, beforeSpringForward).days).toBe(2);
  });

  it("counts calendar days across an autumn DST transition", () => {
    // The mirror: 49 hours in a DST zone, and still two calendar days.
    const beforeFallBack = new Date(2026, 9, 31, 0, 0);
    const afterFallBack = new Date(2026, 10, 2, 0, 0).toISOString();
    expect(describeDue(afterFallBack, beforeFallBack).days).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// countdownPhrase, through `countdown`
//
// Private, so it is reached through the descriptor. Words rather than signed
// numbers is the point: "-84d" is a diff, not something a student reads.
// ---------------------------------------------------------------------------

describe("countdown: the word forms", () => {
  it("uses single words for the three nearest days", () => {
    expect(describeDue(due(0), NOW).countdown).toBe("today");
    expect(describeDue(due(1), NOW).countdown).toBe("tomorrow");
    expect(describeDue(due(-1), NOW).countdown).toBe("yesterday");
  });

  it("never returns a signed number", () => {
    for (const offset of [-400, -60, -14, -2, 2, 14, 60, 400]) {
      expect(describeDue(due(offset), NOW).countdown).not.toMatch(/^-/);
    }
  });

  it("puts the past behind and the future in front", () => {
    expect(describeDue(due(-5), NOW).countdown).toBe("5 days ago");
    expect(describeDue(due(5), NOW).countdown).toBe("in 5 days");
  });
});

describe("countdown: the 14-day switch to weeks", () => {
  it("still counts days at 13", () => {
    expect(describeDue(due(13), NOW).countdown).toBe("in 13 days");
  });

  it("switches to weeks at exactly 14", () => {
    expect(describeDue(due(14), NOW).countdown).toBe("in 2 weeks");
  });

  it("switches on the same threshold in the past", () => {
    expect(describeDue(due(-13), NOW).countdown).toBe("13 days ago");
    expect(describeDue(due(-14), NOW).countdown).toBe("2 weeks ago");
  });

  it("rounds weeks to the nearest whole one", () => {
    // 45 / 7 is 6.43, which rounds down to 6.
    expect(describeDue(due(45), NOW).countdown).toBe("in 6 weeks");
  });
});

describe("countdown: the 60-day switch to months", () => {
  it("still counts weeks at 59", () => {
    // 59 / 7 is 8.43, which rounds to 8.
    expect(describeDue(due(59), NOW).countdown).toBe("in 8 weeks");
  });

  it("switches to months at exactly 60", () => {
    expect(describeDue(due(60), NOW).countdown).toBe("in 2 months");
  });

  it("switches on the same threshold in the past", () => {
    expect(describeDue(due(-59), NOW).countdown).toBe("8 weeks ago");
    expect(describeDue(due(-60), NOW).countdown).toBe("2 months ago");
  });

  it("rounds months to the nearest whole one", () => {
    // 61 / 30 is 2.03, so 60 and 61 read the same. 75 / 30 is 2.5, which
    // rounds up to 3.
    expect(describeDue(due(61), NOW).countdown).toBe("in 2 months");
    expect(describeDue(due(75), NOW).countdown).toBe("in 3 months");
  });

  it("keeps counting in months past a year", () => {
    // Observed behaviour, flagged in the report: there is no year branch, so a
    // deadline more than a year out is described in months.
    expect(describeDue(due(400), NOW).countdown).toBe("in 13 months");
    expect(describeDue(due(-400), NOW).countdown).toBe("13 months ago");
  });
});

// ---------------------------------------------------------------------------
// describeDue -- the unparseable guard
//
// Before the guard, every NaN comparison was false, so a broken date fell
// through to the final branch and came back as `upcoming` carrying the strings
// "Invalid Date" and "in NaN months". The strings were the visible half; the
// real damage was `upcoming`, which kept the row out of the overdue group so a
// student never saw the deadline at all.
// ---------------------------------------------------------------------------

/** Inputs `new Date()` cannot parse at all. */
const UNPARSEABLE = [
  "not a date",
  "",
  "   ",
  "2026-13-01", // month out of range
  "2026-08-17T99:00:00", // hour out of range
  "undefined",
  "null",
  "NaN",
];

describe("describeDue: an unparseable date", () => {
  it("returns the unknown state, with every field spelled out", () => {
    expect(describeDue("not a date", NOW)).toEqual({
      urgency: "unknown",
      label: "No date",
      countdown: "",
      days: null,
      fullLabel: "Due date unavailable",
    });
  });

  it("is NOT classified as upcoming", () => {
    // THE BUG THIS GUARD EXISTS FOR. `upcoming` meant the row never appeared in
    // the overdue group, and invisible is worse than wrong.
    for (const input of UNPARSEABLE) {
      expect(describeDue(input, NOW).urgency).not.toBe("upcoming");
      expect(describeDue(input, NOW).urgency).toBe("unknown");
    }
  });

  it("never renders NaN or Invalid Date in any field", () => {
    for (const input of UNPARSEABLE) {
      const d = describeDue(input, NOW);
      for (const field of [d.label, d.countdown, d.fullLabel]) {
        expect(field).not.toMatch(/NaN/);
        expect(field).not.toMatch(/Invalid Date/);
        expect(field).not.toMatch(/undefined/);
      }
    }
  });

  it("reports days as null rather than NaN", () => {
    // null does not typecheck in `a.days - b.days`, so a caller has to narrow.
    // NaN would have flowed straight through and poisoned the arithmetic.
    for (const input of UNPARSEABLE) {
      expect(describeDue(input, NOW).days).toBeNull();
      expect(describeDue(input, NOW).days).not.toBeNaN();
    }
  });

  it("is detectable on the discriminant, with no string matching", () => {
    const d = describeDue("not a date", NOW);
    expect(d.urgency === "unknown").toBe(true);

    // And narrowing on it is what unlocks `days` as a number.
    if (d.urgency === "unknown") {
      expect(d.days).toBeNull();
    } else {
      throw new Error("expected the unknown variant");
    }
  });

  it("handles an empty and a whitespace-only string", () => {
    expect(describeDue("", NOW).urgency).toBe("unknown");
    expect(describeDue("   ", NOW).urgency).toBe("unknown");
  });

  it("stays pure: the answer does not depend on now", () => {
    // Nothing about an unparseable date is relative to anything, so a different
    // `now` must not change the result. This also pins that the guard runs
    // BEFORE the clock is consulted.
    const other = new Date(2030, 0, 1, 3, 0);
    expect(describeDue("not a date", NOW)).toEqual(
      describeDue("not a date", other),
    );
  });

  it("still parses a valid non-ISO date rather than over-rejecting", () => {
    // The guard tests the parse result, not the string's shape, so anything the
    // platform genuinely understands keeps working.
    const d = describeDue("Aug 17 2026", NOW);
    expect(d.urgency).toBe("today");
    expect(d.days).toBe(0);
  });

  it("DOCUMENTS A GAP: a rolled-over date is parseable, so it is not caught", () => {
    /*
     * Not a desired outcome -- a record of current behaviour so the gap is
     * visible rather than discovered later.
     *
     * V8 is inconsistent about invalid ISO dates. "2026-13-01" (bad month) is
     * Invalid Date and the guard catches it, but "2026-02-30" (bad day) rolls
     * forward into March and parses fine, so it arrives here as a real date the
     * student never chose.
     *
     * Catching this needs a round-trip check -- reformat the parsed date and
     * compare it to the input, which is what `customEventToItem` does for day
     * keys -- and that is input validation rather than a parse guard. Out of
     * scope here deliberately.
     *
     * Only the discriminant is asserted, not the date it rolled to. A date-ONLY
     * ISO string parses as UTC, so which local day it lands on depends on the
     * running machine: Mar 1 in America/Los_Angeles, Mar 2 in UTC. Pinning the
     * string made this the one test in the file that failed a timezone spot
     * check -- a live demonstration of exactly why every other fixture here is
     * built from local parts.
     */
    const d = describeDue("2026-02-30", NOW);
    expect(d.urgency).not.toBe("unknown");
    expect(d.days).not.toBeNull();
    expect(d.fullLabel).toMatch(/^Was due /);
  });
});

// ---------------------------------------------------------------------------
// The rest of the exported surface
// ---------------------------------------------------------------------------

describe("formatShortDate", () => {
  it("gives an abbreviated month and an unpadded day", () => {
    expect(formatShortDate(due(-12))).toBe("Aug 5");
    expect(formatShortDate(new Date(2026, 0, 1, 12).toISOString())).toBe("Jan 1");
  });

  it("does not include a year", () => {
    // Observed and flagged: two dates a year apart format identically.
    expect(formatShortDate(new Date(2026, 8, 21, 12).toISOString())).toBe("Sep 21");
    expect(formatShortDate(new Date(2027, 8, 21, 12).toISOString())).toBe("Sep 21");
  });
});

describe("formatWeekdayDate", () => {
  it("adds the weekday to formatShortDate's shape", () => {
    // The booking surface's date. A student reads the weekday to know whether a
    // slot collides with a class; "Aug 24" alone cannot answer that.
    expect(formatWeekdayDate(new Date(2026, 7, 24, 12).toISOString())).toBe(
      "Mon, Aug 24",
    );
    expect(formatWeekdayDate(new Date(2026, 0, 1, 12).toISOString())).toBe(
      "Thu, Jan 1",
    );
  });

  it("agrees with formatShortDate about the date half", () => {
    // Two formatters over one instant. Asserting they agree is what stops them
    // drifting into two different opinions about a month abbreviation.
    const iso = new Date(2026, 8, 21, 12).toISOString();
    expect(formatWeekdayDate(iso).endsWith(formatShortDate(iso))).toBe(true);
  });

  it("does not include a year either", () => {
    expect(formatWeekdayDate(new Date(2026, 8, 21, 12).toISOString())).toBe(
      "Mon, Sep 21",
    );
  });
});

describe("formatLongDate", () => {
  it("gives weekday, full month, and day", () => {
    expect(formatLongDate(new Date(2026, 7, 17))).toBe("Monday, August 17");
  });
});

describe("formatTime", () => {
  it("renders a 12-hour clock with a meridiem", () => {
    expect(formatTime(due(0, 9, 30))).toBe("9:30 AM");
  });

  it("renders midnight as 12 AM and noon as 12 PM", () => {
    expect(formatTime(due(0, 0, 5))).toBe("12:05 AM");
    expect(formatTime(due(0, 12, 0))).toBe("12:00 PM");
  });
});

describe("formatClockTime", () => {
  it("converts a wall-clock string with no timezone involved", () => {
    expect(formatClockTime("09:30")).toBe("9:30 AM");
    expect(formatClockTime("13:05")).toBe("1:05 PM");
    expect(formatClockTime("23:59")).toBe("11:59 PM");
  });

  it("maps hour 0 and hour 12 onto 12", () => {
    expect(formatClockTime("00:15")).toBe("12:15 AM");
    expect(formatClockTime("12:00")).toBe("12:00 PM");
  });

  it("passes the minutes through as written", () => {
    // The minute half is never parsed, so it keeps its own zero padding.
    expect(formatClockTime("09:00")).toBe("9:00 AM");
  });

  it("accepts a one-digit hour", () => {
    // Lenient on the hour, because "9:30" already worked and is a reasonable
    // thing to hold. Strict on the minute -- see below.
    expect(formatClockTime("9:30")).toBe("9:30 AM");
  });

  it("returns --:-- for a shape that is not HH:mm", () => {
    // Was "NaN:undefined PM", every part of which reached the DOM.
    for (const input of ["abc", "", "   ", "0930", ":30", "9:", "09:30:00", "9:30 AM", "-1:30"]) {
      expect(formatClockTime(input)).toBe("--:--");
    }
  });

  it("returns --:-- for a one-digit minute", () => {
    // "9:5" is not a time. The old version passed the minute half through
    // unparsed and emitted "9:5 AM".
    expect(formatClockTime("9:5")).toBe("--:--");
  });

  it("returns --:-- for an out-of-range hour or minute", () => {
    expect(formatClockTime("24:00")).toBe("--:--");
    expect(formatClockTime("99:99")).toBe("--:--");
    expect(formatClockTime("12:60")).toBe("--:--");
  });

  it("never emits NaN or undefined for any malformed input", () => {
    for (const input of ["abc", "", "9:5", "24:00", "12:60", ":30", "0930"]) {
      const result = formatClockTime(input);
      expect(result).not.toMatch(/NaN/);
      expect(result).not.toMatch(/undefined/);
    }
  });

  it("still accepts both ends of the valid range", () => {
    expect(formatClockTime("00:00")).toBe("12:00 AM");
    expect(formatClockTime("23:59")).toBe("11:59 PM");
  });
});

describe("formatMeetingPattern with a malformed time", () => {
  it("shows the marker rather than propagating NaN into the pattern", () => {
    // formatMeetingPattern composes formatClockTime, so the guard has to hold
    // through it: this used to read "Mon NaN:undefined PM".
    expect(
      formatMeetingPattern([
        {
          dayOfWeek: 1,
          startTime: "oops",
          endTime: "10:50",
          location: "Otterson 1S118",
        },
      ]),
    ).toBe("Mon --:--");
  });
});

describe("initialsOf", () => {
  it("takes the first and last initial of a full name", () => {
    expect(initialsOf("Amber Hanna")).toBe("AH");
  });

  it("gives a single letter for a single name", () => {
    // "Merna" as "ME" reads as the word "me" in a circle, not as initials.
    expect(initialsOf("Merna")).toBe("M");
  });

  it("returns empty for an empty or blank name", () => {
    expect(initialsOf("")).toBe("");
    expect(initialsOf("   ")).toBe("");
  });

  it("skips the middle of a three-part name and collapses extra spaces", () => {
    expect(initialsOf("  ada  betty  cole  ")).toBe("AC");
  });
});

describe("greetingFor", () => {
  it("switches at noon and at 18:00", () => {
    expect(greetingFor(new Date(2026, 7, 17, 0, 0))).toBe("Good morning");
    expect(greetingFor(new Date(2026, 7, 17, 11, 59))).toBe("Good morning");
    expect(greetingFor(new Date(2026, 7, 17, 12, 0))).toBe("Good afternoon");
    expect(greetingFor(new Date(2026, 7, 17, 17, 59))).toBe("Good afternoon");
    expect(greetingFor(new Date(2026, 7, 17, 18, 0))).toBe("Good evening");
  });
});

describe("eventDateBlock", () => {
  it("returns the three strings an event row renders", () => {
    expect(eventDateBlock(due(0, 17, 30))).toEqual({
      month: "Aug",
      day: "17",
      time: "Mon 5:30 PM",
    });
  });

  it("gives the day unpadded, as a string", () => {
    expect(eventDateBlock(new Date(2026, 8, 5, 9, 0).toISOString()).day).toBe("5");
  });
});

describe("formatMeetingPattern", () => {
  function meeting(over: Partial<CourseMeeting> = {}): CourseMeeting {
    return {
      dayOfWeek: 1,
      startTime: "09:30",
      endTime: "10:50",
      location: "Otterson 1S118",
      ...over,
    };
  }

  it("says Schedule TBD rather than returning an empty string", () => {
    expect(formatMeetingPattern([])).toBe("Schedule TBD");
  });

  it("renders a single meeting", () => {
    expect(formatMeetingPattern([meeting()])).toBe("Mon 9:30 AM");
  });

  it("groups days that share a start time", () => {
    expect(
      formatMeetingPattern([meeting({ dayOfWeek: 1 }), meeting({ dayOfWeek: 3 })]),
    ).toBe("Mon/Wed 9:30 AM");
  });

  it("gives each distinct start time its own segment", () => {
    expect(
      formatMeetingPattern([
        meeting({ dayOfWeek: 1, startTime: "09:30" }),
        meeting({ dayOfWeek: 4, startTime: "14:00" }),
      ]),
    ).toBe("Mon 9:30 AM, Thu 2:00 PM");
  });

  it("handles both ends of the weekday range", () => {
    // 0 is Sunday and 6 is Saturday, matching Date.prototype.getDay().
    expect(
      formatMeetingPattern([meeting({ dayOfWeek: 0 }), meeting({ dayOfWeek: 6 })]),
    ).toBe("Sun/Sat 9:30 AM");
  });
});

describe("isToday", () => {
  it("is true anywhere inside the local calendar day", () => {
    expect(isToday(due(0, 0, 0), NOW)).toBe(true);
    expect(isToday(due(0, 23, 59), NOW)).toBe(true);
  });

  it("is false one second into the next day", () => {
    expect(isToday(due(1, 0, 0), NOW)).toBe(false);
  });

  it("is false for yesterday", () => {
    expect(isToday(due(-1, 23, 59), NOW)).toBe(false);
  });
});

describe("isWithinDays", () => {
  it("includes today", () => {
    expect(isWithinDays(due(0), 7, NOW)).toBe(true);
  });

  it("includes the last day of the window", () => {
    // Inclusive: delta <= days.
    expect(isWithinDays(due(7), 7, NOW)).toBe(true);
  });

  it("excludes the day after the window", () => {
    expect(isWithinDays(due(8), 7, NOW)).toBe(false);
  });

  it("excludes the past, so an overdue item is not within the next week", () => {
    expect(isWithinDays(due(-1), 7, NOW)).toBe(false);
  });

  it("treats a zero-day window as today only", () => {
    expect(isWithinDays(due(0), 0, NOW)).toBe(true);
    expect(isWithinDays(due(1), 0, NOW)).toBe(false);
  });
});

describe("standingLabel", () => {
  it("has a human label for every Standing value", () => {
    expect(standingLabel).toEqual({
      onTrack: "On track",
      watch: "Watch",
      needsHelp: "Needs help",
    });
  });
});
