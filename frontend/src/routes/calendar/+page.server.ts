import { buildScheduleData, nowMinutesAt, todayKey } from '$lib/buildSchedule';
import { getTasks } from '$lib/data';
import type { PageServerLoad } from './$types';

/**
 * The calendar's data, and every date decided here.
 *
 * ## One clock read, one place
 *
 * `new Date()` is called ONCE and three values come off it: the day key the grid
 * marks as today, the minutes-past-midnight the "next up" line measures against,
 * and the ISO instant anything editable reclassifies against. Two reads would be
 * two answers, and a day that is "today" to the grid while the header measures
 * against tomorrow is a page contradicting itself.
 *
 * `todayKey()` reads the clock a second time internally. That is not a second
 * answer to guard against -- it is the same function the rest of the app calls
 * and it is called here rather than in a component, which is the whole rule. The
 * two reads are microseconds apart and can only disagree across a midnight
 * boundary, at which point the page is stale anyway and a reload fixes it.
 *
 * ## Tasks are fetched here and NOT merged here
 *
 * A task's due date can be moved by the student and stored only in
 * `localStorage`; a student can add tasks the server has never seen. Merging on
 * the server would render a date the student has already changed. So the server
 * hands down its rows and `calendarSources.mergedSchedule()` folds the local
 * edits on top, client-side, after mount. Same split the Next app had, for the
 * same reason.
 *
 * ## Why `nowMinutes` comes from here rather than from the browser
 *
 * `calendarSources.nowMinutes()` exists and is one of CONVENTIONS' three
 * sanctioned client clock reads. It stays unused, and that was a decision.
 *
 * In Next, `CalendarView` was a `"use client"` component, so its `useMemo` could
 * only ever run in a browser. In SvelteKit the same component renders on the
 * server first: a `$derived` calling `nowMinutes()` would run during SSR, so the
 * server would paint one "next up" row and the browser would silently swap it —
 * along with which square carries the indigo ring — a moment after hydration.
 * That is precisely the drift CONVENTIONS.md calls "quieter, and worse" than
 * Next's loud hydration mismatch.
 *
 * The value freezes at page load either way, so the client read costs a visible
 * flip and buys nothing. See CONVENTIONS.md; the sanctioned-reads list keeps
 * `nowMinutes` for a caller that genuinely runs only in a handler.
 */
export const load: PageServerLoad = async () => {
	const [data, tasks] = await Promise.all([buildScheduleData(), getTasks()]);

	const now = new Date();

	return {
		/**
		 * The server half of the schedule: assignments, events and appointments
		 * pinned to a day, plus classes as weekday rules. Already formatted.
		 */
		data,
		/** The server's task rows. Merged client-side, never here. */
		tasks,
		/** The day the grid rings and the header calls "today". */
		todayKey: todayKey(),
		/** Minutes past midnight, for "next up". See the note above. */
		nowMinutes: nowMinutesAt(now),
		/** The server's instant, for anything the student can edit. */
		nowISO: now.toISOString()
	};
};
