import type { QuickItem } from '$lib/quickList';
import { addDays, type GroupMode, type ScheduleItem } from '$lib/schedule';

/**
 * What each view covers, and what a row has to say inside it.
 *
 * `calendarDay.ts` is the SELECTED DAY's arithmetic. This is its sibling for the
 * questions that are about a view rather than a day: how far the agenda looks,
 * whether a row still has to name its own date, and how an undated to-do becomes
 * a row at all.
 *
 * All of it is here rather than in the components for the same reason as
 * `calendarDay`: Vitest runs in Node with no jsdom, so logic inside a `.svelte`
 * file is logic no gate can see. Two of the three functions below encode a
 * decision that is easy to get subtly wrong and impossible to notice.
 */

/**
 * How far forward the agenda looks. Thirty days.
 *
 * Forward only. A backward-looking agenda is a different feature -- history --
 * and smuggling it in here would change what "everything" means without saying
 * so.
 */
export const AGENDA_DAYS = 30;

/**
 * The agenda's range: `days` day keys starting at `from`, inclusive.
 *
 * Anchored on TODAY, not on the selected day. That is deliberate and it is worth
 * stating because the opposite is the intuitive guess: selecting the 4th does not
 * scroll the agenda to the 4th. The agenda answers "what is coming up", and an
 * anchor that moved with the selection would answer a different question every
 * time a student touched the month grid.
 *
 * `addDays` walks through `fromDayKey`, which parses local parts, so this cannot
 * drift across a DST boundary the way adding 86,400,000ms would.
 */
export function agendaRange(from: string, days: number = AGENDA_DAYS): string[] {
	const count = Math.max(0, Math.trunc(days));
	return Array.from({ length: count }, (_, index) => addDays(from, index));
}

/**
 * Does a row in this grouping have to name its own date?
 *
 * Yes for `category` and `course`; no for `day`.
 *
 * ## The gap this closes
 *
 * The Next agenda rendered `ItemRow` identically in all three groupings, and
 * `ItemRow` shows a TIME and no date. Grouped by day that is right -- the group
 * heading is the date, and repeating it on every row is noise. Grouped by type or
 * by course it leaves thirty days of rows each saying "9:30 AM" with nothing
 * anywhere to say WHICH 9:30 AM.
 *
 * A time without a date, in a list spanning a month, is not a smaller amount of
 * information than a date -- it is the wrong half of it.
 */
export function showsRowDate(mode: GroupMode): boolean {
	return mode !== 'day';
}

/**
 * An undated to-do as a calendar row.
 *
 * ## Why this exists as a function
 *
 * `quickItem` MUST be attached. It is the entire mechanism by which the row's
 * checkbox can write anywhere -- `isTickable` asks whether a writable source is
 * present and `tickItem` dispatches on it. The Next version built this object
 * inline in the agenda's markup, which is exactly where a field gets dropped in a
 * refactor, and dropping this one renders a checkbox that appears to tick and
 * reverts on the next render. Silently. It is the bug the whole attached-source-row
 * design exists to prevent, so the construction gets a name and a test.
 *
 * ## `allDay: false` with an empty `timeLabel`
 *
 * A departure from the Next source, which set `allDay: true`. `ItemRow` renders
 * `allDay ? "all day" : timeLabel`, so every undated to-do was labelled "all day"
 * -- and "all day" is a claim about a DAY. These rows have no day; that is what
 * puts them in their own section. An empty time column says "there is no time
 * here", which is true, and the section heading carries the rest.
 */
export function undatedTodoItem(quick: QuickItem): ScheduleItem {
	return {
		id: `todo-${quick.id}`,
		category: 'todo',
		title: quick.title,
		timeLabel: '',
		detail: '',
		sortMinutes: 0,
		allDay: false,
		done: quick.done,
		quickItem: quick
	};
}

/**
 * Which undated to-dos survive the current filter.
 *
 * `filterSchedule` never sees these -- they are not in `ScheduleData`, because
 * they have no day to be in. So the two filter dimensions that can apply to them
 * are applied here, by the same rules, rather than left off.
 *
 * ## `showDone`
 *
 * The obvious one, and the only one the Next version applied.
 *
 * ## `urgentOnly`, and why leaving it out read as broken
 *
 * An undated to-do can never be urgent. Urgent is keyed by calendar item id in
 * `calendarItems`, and it is applied by `mergedSchedule`'s `annotate` -- which
 * runs over `data.dated` only. These rows never pass through it, so `urgent` is
 * always undefined on them.
 *
 * So with "urgent only" switched on, every other row on the page disappeared and
 * the undated to-dos stayed. A filter that visibly does not apply to one section
 * reads as a broken filter.
 *
 * **This is `filterSchedule`'s own recurring-classes rule, applied to the one
 * collection it cannot reach.** `filterSchedule` drops recurring classes under
 * `urgentOnly` for precisely this reason -- a class can never carry the flag
 * either, and "without this, 'urgent only' left every class on screen and read as
 * broken" is the comment at that line. Nothing in `filterSchedule` changed; the
 * same argument is simply finished.
 */
export function visibleUndatedTodos(
	todos: QuickItem[],
	filter: { showDone: boolean; urgentOnly?: boolean }
): QuickItem[] {
	if (filter.urgentOnly) return [];
	return filter.showDone ? todos : todos.filter((todo) => !todo.done);
}
