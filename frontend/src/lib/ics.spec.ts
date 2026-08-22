import { describe, expect, it } from "vitest";

import { buildIcs, icsFilename, icsFromEvent, icsFromItem, type IcsEvent } from "$lib/ics";
import type { Event } from "$lib/data";
import type { ScheduleItem } from "$lib/schedule";

/**
 * The .ics export.
 *
 * Worth its own file for one reason: **the output is consumed by software, not
 * by a person.** Every other string in this app is read by a student, who can
 * work around a missing space. A calendar client cannot: an unescaped comma
 * silently splits one field into two, a bare `\n` ends the property early, and
 * an LF where the spec wants CRLF is rejected outright by some importers. All
 * three fail as a file that imports "successfully" and is wrong.
 *
 * Nothing here downloads anything. `downloadIcs` needs a `Blob`, a `URL` and an
 * anchor to click; what it wraps is `buildIcs`, which is pure and is where every
 * one of those failures would live.
 */

const STAMP = "2026-08-17T12:00:00.000Z";

function event(over: Partial<IcsEvent> = {}): IcsEvent {
	return {
		id: "evt-evt-3-1",
		title: "Product Club Mixer",
		start: "2026-08-17T17:00:00.000Z",
		end: "2026-08-17T19:00:00.000Z",
		...over,
	};
}

function item(over: Partial<ScheduleItem> = {}): ScheduleItem {
	return {
		id: "evt-evt-3-1",
		category: "club",
		title: "Product Club Mixer",
		timeLabel: "5:00 PM",
		detail: "Rady Commons",
		sortMinutes: 1020,
		allDay: false,
		startISO: "2026-08-17T17:00:00.000Z",
		endISO: "2026-08-17T19:00:00.000Z",
		...over,
	};
}

/** The file, split the way a parser would split it. */
function lines(text: string): string[] {
	return text.split("\r\n");
}

describe("buildIcs", () => {
	it("wraps events in one VCALENDAR", () => {
		const text = buildIcs([event()], STAMP);
		const out = lines(text);

		expect(out[0]).toBe("BEGIN:VCALENDAR");
		expect(out.at(-1)).toBe("END:VCALENDAR");
		expect(out.filter((line) => line === "BEGIN:VEVENT")).toHaveLength(1);
	});

	it("uses CRLF, never a bare newline", () => {
		// The spec requires it and some importers reject anything else. A `\n` that
		// is not part of a `\r\n` is the failure this catches.
		const text = buildIcs([event(), event({ id: "evt-evt-4-2" })], STAMP);

		expect(text).not.toMatch(/[^\r]\n/);
		expect(text).toContain("\r\n");
	});

	it("stamps times in UTC basic format", () => {
		const out = lines(buildIcs([event()], STAMP));

		expect(out).toContain("DTSTART:20260817T170000Z");
		expect(out).toContain("DTEND:20260817T190000Z");
		expect(out).toContain("DTSTAMP:20260817T120000Z");
	});

	it("takes the stamp from its argument rather than the clock", () => {
		/*
		 * The reason this is a parameter at all. With `new Date()` inside the
		 * builder, this assertion could only be written by faking a global -- and
		 * the module would be reading the clock somewhere a server render can reach.
		 */
		const out = lines(buildIcs([event()], "2020-01-02T03:04:05.000Z"));

		expect(out).toContain("DTSTAMP:20200102T030405Z");
	});

	it("makes the UID out of the item id, so a re-import updates", () => {
		const out = lines(buildIcs([event()], STAMP));

		expect(out).toContain("UID:evt-evt-3-1@thrive.local");
	});

	it("escapes the four structural characters in text values", () => {
		/*
		 * Commas and semicolons separate values; backslashes escape; newlines end
		 * the property. An unescaped comma in a title does not corrupt the file
		 * visibly -- it produces a shorter title and a stray second value, which is
		 * exactly the kind of wrong that gets shipped.
		 */
		const out = lines(
			buildIcs(
				[
					event({
						title: "Coffee, cake; and a chat",
						description: "Line one\nline two",
						location: "Rady \\ Commons",
					}),
				],
				STAMP,
			),
		);

		expect(out).toContain("SUMMARY:Coffee\\, cake\\; and a chat");
		expect(out).toContain("DESCRIPTION:Line one\\nline two");
		expect(out).toContain("LOCATION:Rady \\\\ Commons");
	});

	it("omits location and description rather than emitting empty ones", () => {
		const out = lines(buildIcs([event()], STAMP));

		expect(out.some((line) => line.startsWith("LOCATION:"))).toBe(false);
		expect(out.some((line) => line.startsWith("DESCRIPTION:"))).toBe(false);
	});

	it("emits an empty but valid calendar for no events", () => {
		const out = lines(buildIcs([], STAMP));

		expect(out).toEqual([
			"BEGIN:VCALENDAR",
			"VERSION:2.0",
			"PRODID:-//THRIVE//MSBA prototype//EN",
			"CALSCALE:GREGORIAN",
			"METHOD:PUBLISH",
			"END:VCALENDAR",
		]);
	});
});

describe("icsFromItem", () => {
	it("maps a dated row", () => {
		expect(icsFromItem(item())).toEqual({
			id: "evt-evt-3-1",
			title: "Product Club Mixer",
			start: "2026-08-17T17:00:00.000Z",
			end: "2026-08-17T19:00:00.000Z",
			location: "Rady Commons",
			description: undefined,
		});
	});

	it("falls back to the start when there is no end", () => {
		const mapped = icsFromItem(item({ endISO: undefined }));

		expect(mapped?.end).toBe("2026-08-17T17:00:00.000Z");
	});

	it("returns null for a row with no instant", () => {
		/*
		 * A recurring class meeting is a weekday RULE, not an instant, so it carries
		 * no `startISO`. An .ics with no DTSTART is not a shorter calendar file, it
		 * is an invalid one -- so the download is refused and both callers disable
		 * the control and say why.
		 */
		expect(icsFromItem(item({ startISO: undefined }))).toBeNull();
	});

	it("drops an empty detail rather than exporting a blank location", () => {
		// `detail` is `""` on plenty of rows -- a to-do has no location at all.
		expect(icsFromItem(item({ detail: "" }))?.location).toBeUndefined();
	});
});

describe("icsFromEvent", () => {
  /*
   * Home's mapper. A second one rather than a shared one, because the two inputs
   * are different shapes: an `Event` has a real `location` and a required `start`,
   * a `ScheduleItem` has a `detail` that means different things per stream and an
   * OPTIONAL `startISO`. The tests below are what stop the two drifting apart on
   * the one rule they DO share.
   */
  function evt(over: Partial<Event> = {}): Event {
    return {
      id: "evt-3-1",
      title: "Product Club Mixer",
      type: "club",
      start: "2026-08-17T17:00:00.000Z",
      end: "2026-08-17T19:00:00.000Z",
      location: "Rady Commons",
      relevantToGoal: false,
      ...over,
    };
  }

  it("maps an event", () => {
    expect(icsFromEvent(evt())).toEqual({
      id: "evt-3-1",
      title: "Product Club Mixer",
      start: "2026-08-17T17:00:00.000Z",
      end: "2026-08-17T19:00:00.000Z",
      location: "Rady Commons",
      description: undefined,
    });
  });

  it("falls back to the start when there is no end, exactly as the item mapper does", () => {
    // The one rule the two mappers share, so it is asserted on both. An event with
    // no distinct end is a marker at its start, not an event of unknown length.
    expect(icsFromEvent(evt({ end: undefined }))?.end).toBe("2026-08-17T17:00:00.000Z");
  });

  it("keys the UID on the RAW Event.id, which is what Home holds", () => {
    // Not the calendar's `evt-evt-3-1`. Re-importing the same event from either
    // surface should update one entry rather than making two.
    const out = buildIcs([icsFromEvent(evt())], STAMP).split("\r\n");
    expect(out).toContain("UID:evt-3-1@thrive.local");
  });

  it("drops an empty location rather than exporting a blank one", () => {
    expect(icsFromEvent(evt({ location: "" })).location).toBeUndefined();
  });

  it("never returns null, because an Event always has a start", () => {
    // Which is why it has no boolean return and `downloadItemIcs` does: a
    // recurring class meeting is a weekday rule with no instant, and an `Event`
    // cannot be one.
    expect(icsFromEvent(evt())).not.toBeNull();
  });
});

describe("icsFilename", () => {
	it("adds the extension once", () => {
		expect(icsFilename("evt-evt-3-1")).toBe("evt-evt-3-1.ics");
		expect(icsFilename("evt-evt-3-1.ics")).toBe("evt-evt-3-1.ics");
	});
});
