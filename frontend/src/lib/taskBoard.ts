import { describeDue } from '$lib/format';
import type { GroupKey } from '$lib/homeGroups';
import type { TaskRowData } from '$lib/homeView';
import type { Priority, Task } from '$lib/data';

/**
 * The task list, RESOLVED: the student's own tasks and edits over the server's
 * rows.
 *
 * This is the half of the Next `useTaskBoard` hook that is not grouping.
 * `homeGroups.ts` took the read-only half in 6a -- grouping, counting, the
 * progress percentage -- and this is the half that only exists once a student
 * can change something: merging in tasks they created, applying title, priority
 * and due-date overrides, and reclassifying anything whose date moved.
 *
 * Pure, and every store map arrives as an argument. Nothing here reads a store,
 * a clock, or the DOM, which is what makes the whole of it testable in Node.
 *
 * ## Where "today" comes from
 *
 * CONVENTIONS.md classifies every date on the server. Letting a student move a
 * due date means something has to reclassify it without a round trip, so the
 * rule is NARROWED rather than broken: the server still decides what "now" is
 * and passes that instant down as `nowISO`, and `describeDue` -- pure, with `now`
 * as a parameter -- re-runs against that same instant.
 *
 * **Nothing in this file calls `new Date()` with no argument.** `new Date(iso)`
 * is parsing a string the server sent, not asking the browser what day it is.
 * That distinction is the whole of the narrowed exception, and it is the thing to
 * check in review here.
 *
 * ## Why the row type is `TaskRowData` and not a third name
 *
 * `homeView.TaskRowData` and `homeGroups.HomeRow` are already the same shape
 * under two names -- one is what the load function returns, the other is what the
 * card consumes. Adding a third would not help. This uses the load function's
 * name because these rows come from the payload and go back out to two different
 * consumers (`TasksCard` and `TaskStatPills`), and the payload is the thing they
 * have in common.
 */

/**
 * A group a task can actually be MOVED to.
 *
 * `unknown` ("Needs a date") is deliberately excluded, and this type is how that
 * decision is enforced rather than remembered. You cannot move a task into
 * having no date: `Task.dueDate` is required and `setTaskDue` only ever writes an
 * ISO instant, so "drop it in Needs a date" has nothing to write. That group is a
 * SOURCE -- rows leave it when the student gives them a date -- and never a
 * destination.
 *
 * Excluding it in the type means `dateForGroup` cannot be called with it by
 * accident, and a future drop target has to say out loud that it is doing
 * something this file says is impossible.
 */
export type DatedGroupKey = Exclude<GroupKey, 'unknown'>;

/** Narrows a group key to one that can be dropped into. */
export function isDatedGroup(key: GroupKey): key is DatedGroupKey {
	return key !== 'unknown';
}

/**
 * The wall-clock time to carry over when only a task's DAY is changing.
 *
 * A problem set due at 11:59pm that moves to today is still due at 11:59pm, and
 * stamping it with the current time would quietly make it overdue. So the hour
 * and minute come from the date the task already had.
 *
 * ## The fallback is not defensive decoration
 *
 * `new Date('not-a-date').getHours()` is `NaN`, `setHours(NaN, NaN)` yields an
 * Invalid Date, and `Invalid Date.toISOString()` **throws a RangeError**. The one
 * group guaranteed to hit that is `unknown` -- "Needs a date" exists BECAUSE a due
 * date did not parse, and the entire point of surfacing it is that a student can
 * fix it. So every route out of that group (the date input, the three shortcuts, a
 * drag into a dated group) ran through an unparseable `fromISO`.
 *
 * Falling back to the reference instant's own clock keeps the guarantee that
 * matters -- a real instant comes out -- and loses nothing, because a date that
 * never parsed had no time of day to preserve.
 */
function clockFrom(fromISO: string, fallback: Date): { hours: number; minutes: number } {
	const from = new Date(fromISO);
	if (!Number.isNaN(from.getTime())) return { hours: from.getHours(), minutes: from.getMinutes() };

	// The fallback can itself be unusable -- `fromDateInputValue` defaults it to the
	// same string. Local midnight then, because the one thing this must never do is
	// hand back NaN and let `toISOString()` throw at a student.
	if (!Number.isNaN(fallback.getTime())) {
		return { hours: fallback.getHours(), minutes: fallback.getMinutes() };
	}
	return { hours: 0, minutes: 0 };
}

/**
 * Where a task lands when dropped on a group.
 *
 * "This week" is deliberately not tomorrow. Dropping something into it means
 * "not urgent", and landing on tomorrow would put it straight back at the top of
 * the list the student was trying to move it out of.
 */
export function dateForGroup(groupKey: DatedGroupKey, fromISO: string, nowISO: string): string {
	const now = new Date(nowISO);
	const target = new Date(now);

	if (groupKey === 'overdue') target.setDate(now.getDate() - 1);
	else if (groupKey === 'upcoming') target.setDate(now.getDate() + 3);

	const { hours, minutes } = clockFrom(fromISO, now);
	target.setHours(hours, minutes, 0, 0);
	return target.toISOString();
}

/**
 * "YYYY-MM-DD" for a date input, in LOCAL time rather than UTC.
 *
 * `toISOString().slice(0, 10)` is the bug this avoids: it shifts an evening item
 * onto the next day anywhere behind UTC, so a task due at 8pm would open its
 * editor showing tomorrow. Same rule as `dayKeyOf` in `schedule.ts`.
 *
 * Returns `""` for a date that will not parse, which is what a `<input
 * type="date">` reads as "no value selected". The alternative is the literal
 * string `"NaN-NaN-NaN"`, which the input silently rejects -- leaving a field that
 * looks broken on exactly the rows that most need using.
 */
export function toDateInputValue(iso: string): string {
	const date = new Date(iso);
	if (Number.isNaN(date.getTime())) return '';

	const month = `${date.getMonth() + 1}`.padStart(2, '0');
	const day = `${date.getDate()}`.padStart(2, '0');
	return `${date.getFullYear()}-${month}-${day}`;
}

/**
 * A date input's "YYYY-MM-DD" back to an instant, keeping the old clock time.
 *
 * `fallbackISO` supplies the clock when the task's own date will not parse -- the
 * "Needs a date" case. Callers pass `nowISO`, so a task given its first real date
 * lands at the current time of day rather than throwing.
 */
export function fromDateInputValue(value: string, fromISO: string, fallbackISO = fromISO): string {
	const [year, month, day] = value.split('-').map(Number);
	const { hours, minutes } = clockFrom(fromISO, new Date(fallbackISO));
	const next = new Date(year, month - 1, day, hours, minutes);
	return next.toISOString();
}

/**
 * Shift a date by whole days, keeping the task's own clock time.
 *
 * The three shortcuts in `DueDateEditor` are all this function: today, tomorrow,
 * next week. Measured from `nowISO` -- the server's instant -- rather than from
 * the task's current date, because "tomorrow" means tomorrow and not "the day
 * after whatever this was already set to".
 */
export function shiftFromNow(days: number, fromISO: string, nowISO: string): string {
	const next = new Date(nowISO);
	next.setDate(next.getDate() + days);
	const { hours, minutes } = clockFrom(fromISO, new Date(nowISO));
	next.setHours(hours, minutes, 0, 0);
	return next.toISOString();
}

/** What `AddTaskForm` collects. Title is the only field that must be filled. */
export interface NewTaskInput {
	title: string;
	/** "YYYY-MM-DD" from the date input, or empty for "due now". */
	dueDay: string;
	label: string;
	priority: Priority;
}

/**
 * A fresh id for a student-created task.
 *
 * The one impure function in this file, kept to one line so the rest stays
 * testable. `Date.now()` here is a nonce, not a date classification -- it is
 * never parsed back into a day, and the same shape is already accepted in
 * `quickList.ts` for the same reason.
 *
 * Prefixed so a student-created id can never collide with a fixture's, and so
 * the origin is readable in `localStorage`. The counter breaks ties: adding two
 * tasks inside one millisecond is not hypothetical when a form stays open.
 */
let nonce = 0;
export function mintTaskId(): string {
	nonce += 1;
	return `own-${Date.now().toString(36)}-${nonce.toString(36)}`;
}

/**
 * Build the task a student just described.
 *
 * Returns `null` for an empty title, which is the only required field. Every
 * other field has a working default -- due now, medium priority, no label --
 * because the cost of a task never written down is higher than the cost of one
 * filed slightly wrong, and all of it is editable on the row afterwards.
 *
 * `id` is a parameter rather than minted inside, so the whole function is pure
 * and a test can assert the shape without stubbing a clock.
 */
export function newTaskFrom(input: NewTaskInput, nowISO: string, id: string): Task | null {
	const title = input.title.trim();
	if (!title) return null;

	const label = input.label.trim();

	return {
		id,
		title,
		dueDate: input.dueDay ? fromDateInputValue(input.dueDay, nowISO) : nowISO,
		source: 'admin',
		priority: input.priority,
		done: false,
		subtasks: [],
		courseCode: label || undefined
	};
}

/**
 * The rows as the student sees them.
 *
 * Merges tasks they created, applies their title / priority / due-date edits, and
 * reclassifies ONLY the rows whose date actually moved -- the server's descriptor
 * is the authority for everything else, and re-deriving it would be both wasted
 * work and a second answer to a question already settled.
 *
 * A student-created task carries no server descriptor at all, so it is described
 * here against the same instant everything else was.
 *
 * The identity shortcut matters more than it looks: an untouched row is returned
 * BY REFERENCE, so `{#each}` keyed on the task id sees the same object and does
 * not tear down a row because a sibling was edited. With every row rebuilt, an
 * open note panel three rows down would lose its draft on someone else's tick.
 */
export function resolveRows(
	rows: readonly TaskRowData[],
	added: Readonly<Record<string, Task>>,
	titles: Readonly<Record<string, string>>,
	priorities: Readonly<Record<string, Priority>>,
	dues: Readonly<Record<string, string>>,
	nowISO: string
): TaskRowData[] {
	const now = new Date(nowISO);

	const merged: TaskRowData[] = [
		...rows,
		...Object.values(added).map((task) => ({ task, due: describeDue(task.dueDate, now) }))
	];

	return merged.map((row) => {
		const { task } = row;
		const title = titles[task.id];
		const priority = priorities[task.id];
		const dueDate = dues[task.id];

		if (title === undefined && priority === undefined && dueDate === undefined) return row;

		return {
			task: {
				...task,
				title: title ?? task.title,
				priority: priority ?? task.priority,
				dueDate: dueDate ?? task.dueDate
			},
			due: dueDate === undefined ? row.due : describeDue(dueDate, now)
		};
	});
}

/**
 * The new index a row lands on after being dragged within its own group.
 *
 * Removing the row first shifts everything after it up by one, so a drop BELOW
 * the original slot has to account for its own absence. Off by one here means a
 * row dropped two places down lands one place down, which is the kind of thing
 * that reads as "drag is janky" rather than as a bug.
 */
export function dropIndexWithin(fromIndex: number, dropIndex: number): number {
	return dropIndex > fromIndex ? dropIndex - 1 : dropIndex;
}

/**
 * The ids of one group, with `fromIndex` moved to `toIndex`.
 *
 * Returns the whole group's ids because that is what `reorderWithin` persists: a
 * single sort key cannot express "between these two" while the rows around it
 * share the provider's implicit order. Pure, so the arithmetic is testable
 * without a store.
 */
export function reorderedIds(ids: readonly string[], fromIndex: number, toIndex: number): string[] {
	const next = [...ids];
	if (fromIndex === toIndex) return next;
	if (fromIndex < 0 || fromIndex >= next.length) return next;

	const [moved] = next.splice(fromIndex, 1);
	next.splice(Math.max(0, Math.min(toIndex, next.length)), 0, moved);
	return next;
}
