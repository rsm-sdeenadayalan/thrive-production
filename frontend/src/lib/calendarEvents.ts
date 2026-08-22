import { eventIdOf, isEventIgnored, type IgnoredMap } from "$lib/ignoredEvents";
import { isEventJoined, type JoinOverrides } from "$lib/userEdits.svelte";
import type { ScheduleItem } from "$lib/schedule";

/**
 * THE CALENDAR'S EVENT BOUNDARY.
 *
 * `DayEventsSection` renders a day's opt-in events and offers two things that
 * are stored per event rather than per row: "count me in" (`thrive:event-joins`)
 * and "ignore" (`thrive:ignored-events`). Both stores key on the RAW `Event.id`.
 * The calendar holds a CALENDAR ITEM id, which for an event is the raw id with
 * one more `evt-` on the front.
 *
 * So exactly one conversion is needed, and this is the one place it happens.
 *
 * ## Why it is a module and not four lines inside the component
 *
 * Vitest runs in Node with no jsdom here, so nothing renders and logic left in a
 * `.svelte` file is logic no gate can see. That is the same reason `calendarDay`
 * and `calendarViews` exist, and it matters more here than in either: the exact
 * defect this converts around -- an id shedding a prefix it did not have, or not
 * shedding one it did -- was a HIGH bug in the ignore store, fixed in Phase 7a,
 * and it is invisible to types, to `svelte-check`, and to any round-trip test.
 *
 * A test can now assert what STRING this hands the store, without ever calling
 * the store's own reader. See `calendarEvents.spec.ts`.
 *
 * ## `eventIdOf` is called here and nowhere else in the calendar
 *
 * Its input is a calendar item id and only ever that. Handing it a raw
 * `Event.id` does not normalise, it mangles -- a raw event id begins with `evt-`
 * too. `isVisible` in `schedule.ts` strips the same prefix inline, because
 * importing a store into a file the server renders through would poison it; that
 * sibling is documented in both places and there must not be a third.
 */

/** One event on the selected day, with both stores already asked about it. */
export interface DayEventRow {
	item: ScheduleItem;
	/**
	 * The RAW `Event.id`. The key for BOTH stores, and the id Home holds.
	 *
	 * `evt-evt-3-1` (calendar item) -> `evt-3-1` (event). Never `3-1`.
	 */
	eventId: string;
	joined: boolean;
	ignored: boolean;
}

/**
 * A day's events, resolved against the join and ignore stores.
 *
 * Takes the two maps rather than reading them, so this stays pure and a test can
 * hand it a map it wrote by hand. The component reads the stores and passes them
 * in, which is also what makes the reads reactive at the one place they should be.
 *
 * Ignored rows are kept rather than dropped. Whether an ignored event is VISIBLE
 * is `filterSchedule`'s decision, made once upstream against `showIgnored`; by
 * the time a row reaches here it has already survived that. What this flag drives
 * is how the row LOOKS and whether it offers "ignore" or "un-ignore" -- a row
 * revealed by the show-ignored switch has to be recoverable, or the switch is a
 * one-way door.
 */
export function dayEventRows(
	items: ScheduleItem[],
	joins: JoinOverrides,
	ignored: IgnoredMap,
): DayEventRow[] {
	return items.map((item) => {
		const eventId = eventIdOf(item.id);
		return {
			item,
			eventId,
			joined: isEventJoined(eventId, joins),
			ignored: isEventIgnored(eventId, ignored),
		};
	});
}

/**
 * How many of the rows ON SCREEN the student has joined.
 *
 * Counted over the rows given rather than over the store, and that is the
 * behaviour rather than an optimisation: the store holds every event the student
 * has ever said yes to, across every day. A fraction whose numerator came from
 * the store and whose denominator came from the list would read "4/2".
 */
export function joinedCount(rows: DayEventRow[]): number {
	return rows.filter((row) => row.joined).length;
}
