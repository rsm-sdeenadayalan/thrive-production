import { createOverrideStore } from '$lib/overrideStore.svelte';
import type { DayGroupMode, GroupMode, ScheduleCategory } from '$lib/schedule';

/**
 * What the student has done to the calendar's controls, persisted.
 *
 * A filter that resets on every navigation is a filter nobody uses twice. If a
 * student has decided they never want to see UCSD-wide events, that decision
 * should outlive a click on Home.
 *
 * Built on `createOverrideStore` under one fixed key, the same compromise
 * `floatingPanel.ts` makes: this is UI state rather than an override over
 * provider truth, but that module is the single persistence mechanism and one
 * seam to change later beats two.
 *
 * ## The memo is gone, on purpose
 *
 * The React version wrapped `normalisePrefs` in a `useMemo` keyed on the raw
 * stored value, and that memo WAS load-bearing there: `useSyncExternalStore`
 * handed back a referentially stable snapshot, `normalisePrefs` built a fresh
 * object from it, and so without the memo every render produced a new
 * `prefs.hidden` array and busted every downstream `useMemo` -- including the
 * schedule filter running across 42 month-grid cells.
 *
 * None of that applies here. Svelte tracks the signal, not the object identity,
 * so a reader re-runs when the stored value actually changes and not otherwise.
 * Keeping the memo would be caching against a problem that no longer exists.
 */

export type CalendarViewMode = 'month' | 'week' | 'agenda';

export interface CalendarPrefs {
	/** Categories switched off. Stored rather than derived so a new category
	 *  added later defaults to visible instead of silently hidden. */
	hidden: ScheduleCategory[];
	/** Labels switched off. Open-ended: whatever the student has typed. */
	hiddenLabels: string[];
	showDone: boolean;
	/** When true, only items flagged urgent survive anywhere on the page. */
	urgentOnly: boolean;
	/**
	 * Reveal events the student has ignored.
	 *
	 * Off by default, and it lives here rather than on the ignore store because
	 * it is a view preference, not a fact about the events. The calendar is the
	 * record of what exists, so this is the switch that makes ignored events
	 * recoverable; Home has no equivalent by design.
	 */
	showIgnored: boolean;
	view: CalendarViewMode;
	/** Agenda only. Kept even when the view is month, so switching back
	 *  restores what the student last chose. */
	groupBy: GroupMode;
	/**
	 * How the selected day's items are arranged: by type (classes, then due,
	 * then tasks...) or as one chronological list.
	 *
	 * Defaults to `type`. A day view's instinct is chronological, but the
	 * question a student actually opens it with is usually "what do I owe" --
	 * and grouping answers that first while `time` stays one click away.
	 */
	dayGroupBy: DayGroupMode;
}

export const DEFAULT_PREFS: CalendarPrefs = {
	hidden: [],
	hiddenLabels: [],
	/**
	 * TRUE on the calendar, unlike everywhere else.
	 *
	 * Found by driving the page: with done items hidden, ticking a task made it
	 * disappear under the cursor. That loses the strike-through, loses any way
	 * back, and makes the header's "0 of 2 done" count meaningless -- the
	 * denominator shrinks as you work. A calendar day is a record of the day,
	 * and a finished thing still happened.
	 */
	showDone: true,
	urgentOnly: false,
	showIgnored: false,
	view: 'month',
	groupBy: 'day',
	dayGroupBy: 'type'
};

/**
 * Merge over the defaults rather than trusting what is in storage.
 *
 * A half-written or hand-edited value must not take the page down, and a build
 * that adds a field must not read `undefined` out of a store written by the
 * previous build.
 *
 * Exported for tests: this is the only genuinely risky logic in the module,
 * because its input is whatever happens to be in a browser's localStorage.
 * It has caught four separate new-field omissions.
 */
export function normalisePrefs(stored: Partial<CalendarPrefs> | undefined): CalendarPrefs {
	if (!stored) return DEFAULT_PREFS;

	return {
		hidden: Array.isArray(stored.hidden) ? stored.hidden : [],
		hiddenLabels: Array.isArray(stored.hiddenLabels) ? stored.hiddenLabels : [],
		showDone: typeof stored.showDone === 'boolean' ? stored.showDone : true,
		urgentOnly: typeof stored.urgentOnly === 'boolean' ? stored.urgentOnly : false,
		showIgnored: typeof stored.showIgnored === 'boolean' ? stored.showIgnored : false,
		view:
			stored.view === 'week' || stored.view === 'agenda' || stored.view === 'month'
				? stored.view
				: 'month',
		groupBy:
			stored.groupBy === 'category' || stored.groupBy === 'course' || stored.groupBy === 'day'
				? stored.groupBy
				: 'day',
		dayGroupBy: stored.dayGroupBy === 'time' ? 'time' : 'type'
	};
}

/* --- The store ---------------------------------------------------------- */

/**
 * One fixed key inside the override store, rather than a key per field.
 *
 * Prefs are read and written as a whole object -- `setCalendarPrefs` takes a
 * partial and merges -- so splitting them across seven override keys would buy
 * nothing and make `normalisePrefs` impossible to apply in one place.
 */
const KEY = 'value';
const store = createOverrideStore<CalendarPrefs>('thrive:calendar-prefs');

/**
 * The current prefs, reactive and always normalised. Was `useCalendarPrefs()`.
 *
 * Before hydration this returns `DEFAULT_PREFS`, which is the correct
 * un-personalised answer: everything visible, month view, done items shown.
 */
export const calendarPrefs = (): CalendarPrefs => normalisePrefs(store.values[KEY]);

/** Read outside a reactive context. */
export function readCalendarPrefs(): CalendarPrefs {
	return normalisePrefs(store.read()[KEY]);
}

export function setCalendarPrefs(next: Partial<CalendarPrefs>) {
	store.set(KEY, { ...readCalendarPrefs(), ...next });
}

/** Toggle one category. Convenience, because every caller wants exactly this. */
export function toggleCategory(category: ScheduleCategory) {
	const { hidden } = readCalendarPrefs();
	setCalendarPrefs({
		hidden: hidden.includes(category)
			? hidden.filter((entry) => entry !== category)
			: [...hidden, category]
	});
}

/** Toggle one label. Same shape as `toggleCategory`, different dimension. */
export function toggleLabel(label: string) {
	const { hiddenLabels } = readCalendarPrefs();
	setCalendarPrefs({
		hiddenLabels: hiddenLabels.includes(label)
			? hiddenLabels.filter((entry) => entry !== label)
			: [...hiddenLabels, label]
	});
}

export function showAllCategories() {
	setCalendarPrefs({ hidden: [], hiddenLabels: [] });
}
