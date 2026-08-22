import { afterEach, describe, expect, it, vi } from "vitest";

import { installStorage, uninstallStorage, type FakeStorage } from "$lib/testing/fakeStorage";
import type { ScheduleItem } from "$lib/schedule";

/**
 * The calendar's event boundary, and the key space behind it.
 *
 * ## Why the assertions here look the way they do
 *
 * Phase 7a fixed a HIGH defect in the ignore store: a normaliser applied on both
 * sides of a store, so every read and every write shared the same mangling and
 * the store was perfectly self-consistent about a key nothing else in the app
 * used. **Two round-trip tests passed the whole time it was broken.**
 *
 * So the cases below deliberately never round-trip. Each one either
 *
 *  - asserts the literal STRING that lands in `localStorage`, read back out of
 *    the fake storage rather than through the store's own getter, or
 *  - writes through the path ONE surface really uses and reads through the path
 *    the OTHER really uses.
 *
 * Not sharing a transformation is the property that catches a key-space split.
 * Reinstating the bug -- keying the join store on `item.id` -- turns the first
 * two cases red; a round-trip written over the same pair of functions would stay
 * green, which is the whole point.
 */

/** The calendar item id for raw event `evt-3-1`. Doubly prefixed by construction. */
const ITEM_ID = "evt-evt-3-1";
/** The raw `Event.id`. What Home holds, and what both stores key on. */
const RAW_ID = "evt-3-1";

let storage: FakeStorage;

async function fresh<T>(mod: () => Promise<T>): Promise<T> {
	vi.resetModules();
	storage = installStorage();
	return await mod();
}

afterEach(() => {
	uninstallStorage();
});

function row(over: Partial<ScheduleItem> = {}): ScheduleItem {
	return {
		id: ITEM_ID,
		category: "club",
		title: "Product Club Mixer",
		timeLabel: "5:00 PM",
		detail: "Rady Commons",
		sortMinutes: 1020,
		allDay: false,
		...over,
	};
}

/** What is actually sitting in one localStorage key, parsed. */
function stored(key: string): unknown {
	const raw = storage.dump()[key];
	return raw === undefined ? undefined : JSON.parse(raw);
}

// ---------------------------------------------------------------------------
// The conversion itself
// ---------------------------------------------------------------------------

describe("dayEventRows sheds the calendar's prefix exactly once", () => {
	it("hands back the raw Event.id beside each row", async () => {
		const { dayEventRows } = await fresh(() => import("$lib/calendarEvents"));

		const [result] = dayEventRows([row()], {}, {});

		expect(result.eventId).toBe(RAW_ID);
		// Not `3-1`, which is what calling `eventIdOf` on an already-raw id gives.
		expect(result.eventId).not.toBe("3-1");
		// And the row itself is untouched -- the item id is still the calendar's.
		expect(result.item.id).toBe(ITEM_ID);
	});

	it("resolves joined and ignored against the raw id, not the item id", async () => {
		const { dayEventRows } = await fresh(() => import("$lib/calendarEvents"));

		const underRaw = dayEventRows([row()], { [RAW_ID]: true }, { [RAW_ID]: true })[0];
		expect(underRaw.joined).toBe(true);
		expect(underRaw.ignored).toBe(true);

		// A map keyed the OLD way answers nothing. This is the case that fails if
		// the boundary is removed and the item id is passed straight through.
		const underItem = dayEventRows([row()], { [ITEM_ID]: true }, { [ITEM_ID]: true })[0];
		expect(underItem.joined).toBe(false);
		expect(underItem.ignored).toBe(false);
	});

	it("keeps ignored rows rather than dropping them", async () => {
		// Visibility is `filterSchedule`'s decision, made once upstream against
		// `showIgnored`. A row that reaches here has already survived it, and
		// dropping it now would make the show-ignored switch a one-way door.
		const { dayEventRows } = await fresh(() => import("$lib/calendarEvents"));

		const rows = dayEventRows([row()], {}, { [RAW_ID]: true });

		expect(rows).toHaveLength(1);
		expect(rows[0].ignored).toBe(true);
	});

	it("counts the joined rows on screen, not the whole store", async () => {
		/*
		 * The store holds every event the student has ever said yes to, across every
		 * day. A numerator taken from it against a denominator taken from the list
		 * reads "4/2" on a Tuesday.
		 */
		const { dayEventRows, joinedCount } = await fresh(() => import("$lib/calendarEvents"));

		const joins = { [RAW_ID]: true, "evt-9-9": true, "evt-8-8": true };
		const rows = dayEventRows([row(), row({ id: "evt-evt-4-2" })], joins, {});

		expect(joinedCount(rows)).toBe(1);
	});
});

// ---------------------------------------------------------------------------
// THE STORED KEY. Not a round trip.
// ---------------------------------------------------------------------------

describe("the join store's key space, pinned at the string", () => {
	it("stores the RAW Event.id when written through the calendar's own path", async () => {
		/*
		 * The whole path `DayEventsSection` takes, and then a read that shares
		 * nothing with it: straight out of the fake `localStorage`, parsed, and
		 * compared to a literal.
		 *
		 * `eventJoins()` is deliberately not used. It would return whatever
		 * `setEventJoined` wrote under whatever key the boundary produced, which is
		 * true of a correct implementation and equally true of a broken one.
		 */
		vi.resetModules();
		storage = installStorage();

		const { dayEventRows } = await import("$lib/calendarEvents");
		const { setEventJoined } = await import("$lib/userEdits.svelte");

		const [entry] = dayEventRows([row()], {}, {});
		setEventJoined(entry.eventId, true);

		expect(stored("thrive:event-joins")).toEqual({ "evt-3-1": true });
	});

	it("stores the same key the IGNORE store does, from the same row", async () => {
		/*
		 * The argument for the decision, as an assertion.
		 *
		 * One row offers "count me in" and "ignore" side by side. If those two
		 * controls wrote different id spaces, this component would be holding two
		 * ids for one event and would have to remember which control took which --
		 * the exact arrangement that produced the 7a defect. So: same row, both
		 * writes, and the two stores must show the identical string.
		 */
		vi.resetModules();
		storage = installStorage();

		const { dayEventRows } = await import("$lib/calendarEvents");
		const { setEventJoined } = await import("$lib/userEdits.svelte");
		const { setEventIgnored } = await import("$lib/ignoredEvents");

		const [entry] = dayEventRows([row()], {}, {});
		setEventJoined(entry.eventId, true);
		setEventIgnored(entry.eventId, true);

		const joins = stored("thrive:event-joins") as Record<string, unknown>;
		const ignored = stored("thrive:ignored-events") as Record<string, unknown>;

		expect(Object.keys(joins)).toEqual(Object.keys(ignored));
		expect(Object.keys(joins)).toEqual([RAW_ID]);
	});

	it("what the calendar writes, Home can read without stripping anything", async () => {
		/*
		 * The cross-surface half. Home holds an `Event`, so its id is already raw and
		 * it calls `isEventJoined(event.id, joins)` with no normalising at all --
		 * `EventRow`'s "count me in" is inert today, and this is the read it will
		 * make when it is wired.
		 *
		 * Write through the calendar's path, read through Home's. Neither side
		 * shares a transformation with the other.
		 */
		vi.resetModules();
		storage = installStorage();

		const { dayEventRows } = await import("$lib/calendarEvents");
		const { eventJoins, isEventJoined, setEventJoined } = await import("$lib/userEdits.svelte");

		const [entry] = dayEventRows([row()], {}, {});
		setEventJoined(entry.eventId, true);

		// `RAW_ID` is a literal here on purpose: it stands in for `event.id` off a
		// fixture, and deriving it would be the shared transformation this avoids.
		expect(isEventJoined(RAW_ID, eventJoins())).toBe(true);
		expect(isEventJoined(ITEM_ID, eventJoins())).toBe(false);
	});

	it("leaving writes the same key it joined under, so nothing is stranded", async () => {
		const { dayEventRows } = await fresh(() => import("$lib/calendarEvents"));
		const { setEventJoined } = await import("$lib/userEdits.svelte");

		const [entry] = dayEventRows([row()], {}, {});
		setEventJoined(entry.eventId, true);
		setEventJoined(entry.eventId, false);

		// Deleted, not stored as false -- the same rule the ignore store follows,
		// and what makes "has the student ever touched this" answerable.
		expect(stored("thrive:event-joins")).toEqual({});
	});
});
