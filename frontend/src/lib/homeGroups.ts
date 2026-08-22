import { messages } from '$lib/messages';
import { isTaskDone, type DoneOverrides } from '$lib/userEdits.svelte';
import type { DueDescriptor, KnownDueDescriptor } from '$lib/format';
import type { Task } from '$lib/data';

/**
 * Home's task list, grouped.
 *
 * Read-only: this is the 6a half of what the Next app's `useTaskBoard` did.
 * Reordering, moving between groups, editing a due date, and adding a task are
 * 6b, and they are what the rest of that hook was for. Grouping and counting
 * are separable from editing, so they are separate.
 *
 * Pure, and takes the done overrides as an argument rather than reading the
 * store. Everything here is testable without a browser, and the one thing that
 * genuinely needs the store -- "has the student ticked this" -- is passed in.
 */

/** A task plus the due descriptor the server computed for it. */
export interface HomeRow {
	task: Task;
	due: DueDescriptor;
}

/** A row whose date parsed, so it has a real urgency and a real `days`. */
interface KnownRow extends HomeRow {
	due: KnownDueDescriptor;
}

export type GroupKey = 'unknown' | 'overdue' | 'today' | 'upcoming';

/**
 * Group order, and `unknown` is FIRST on purpose.
 *
 * A task whose due date will not parse has no urgency to sort by, so there is no
 * natural place for it -- which is exactly how it ended up rendered nowhere for a
 * phase. Putting it at the top is the decision: loud is correct, invisible is
 * not. A deadline that silently does not exist is worse than one shouting for
 * attention, and this is the only group a student can actually fix.
 */
export const GROUP_ORDER: GroupKey[] = ['unknown', 'overdue', 'today', 'upcoming'];

export const groupHeading: Record<GroupKey, string> = {
	unknown: messages.taskGroups.unknown,
	overdue: messages.taskGroups.overdue,
	today: messages.taskGroups.today,
	upcoming: messages.taskGroups.upcoming
};

/** Home is a "what's next" surface, so "This week" means it. */
const WEEK = 7;

/**
 * Narrows a row to one whose date parsed.
 *
 * A real type predicate rather than a bare `filter`, because `days` is
 * `number | null` since the Phase 3a-fix guards landed and the sort below
 * subtracts it. Without narrowing, `a.due.days - b.due.days` does not compile --
 * which is the discriminated union doing exactly the job it was built for.
 */
function isKnown(row: HomeRow): row is KnownRow {
	return row.due.urgency !== 'unknown';
}

export interface HomeGroup {
	key: GroupKey;
	heading: string;
	rows: HomeRow[];
}

export interface HomeTaskGroups {
	groups: HomeGroup[];
	done: HomeRow[];
	total: number;
	doneCount: number;
	percent: number;
}

/** Sort keys the student has set by moving rows. See `reorderWithin`. */
export type OrderOverrides = Readonly<Record<string, number>>;

/**
 * Order rows within a group: the student's own placement first, then a fallback.
 *
 * A row the student has never moved keeps the source order and sorts AFTER any
 * they have -- an explicit placement outranks an implicit one. Without that rule
 * a single reordered row would be interleaved by date back into the middle of
 * the list it was just dragged out of, which reads as the drag having failed.
 *
 * `fallback` differs by group, which is the reason this is a factory rather than
 * one comparator: a dated group falls back to how soon it is due, and the
 * `unknown` group has no date to fall back TO and must stay stable instead.
 */
function byOrder<T extends HomeRow>(
	order: OrderOverrides,
	fallback: (a: T, b: T) => number
): (a: T, b: T) => number {
	return (a, b) => {
		const left = order[a.task.id];
		const right = order[b.task.id];

		if (left !== undefined && right !== undefined) return left - right;
		if (left !== undefined) return -1;
		if (right !== undefined) return 1;
		return fallback(a, b);
	};
}

/**
 * Group Home's tasks by urgency, with done pulled out.
 *
 * `total` and `percent` count every task including done ones -- the progress bar
 * reads "6 of 14 done", so the denominator has to be everything.
 *
 * `order` defaults to no overrides, so a caller that cannot reorder -- and every
 * caller before 6b -- gets the provider's ordering unchanged.
 */
export function buildHomeGroups(
	rows: readonly HomeRow[],
	doneOverrides: DoneOverrides,
	order: OrderOverrides = {}
): HomeTaskGroups {
	const done: HomeRow[] = [];
	const open: HomeRow[] = [];

	for (const row of rows) {
		if (isTaskDone(row.task, doneOverrides)) done.push(row);
		else open.push(row);
	}

	const openKnown = open.filter(isKnown);

	const groups: HomeGroup[] = GROUP_ORDER.map((key) => {
		if (key === 'unknown') {
			/*
			 * `days` is null here by construction, so there is nothing to order BY --
			 * these keep the provider's order, which is the only ordering that means
			 * anything for a row with no date.
			 *
			 * They are still sorted, because the student can reorder within this group
			 * even though nothing can be dropped INTO it (see `DatedGroupKey` in
			 * taskBoard.ts). The fallback returns 0 and `Array.prototype.sort` is
			 * stable, so rows the student has never moved keep exactly the order they
			 * arrived in.
			 */
			return {
				key,
				heading: groupHeading[key],
				rows: open.filter((row) => !isKnown(row)).sort(byOrder(order, () => 0))
			};
		}

		return {
			key,
			heading: groupHeading[key],
			rows: openKnown
				.filter(
					(row) =>
						row.due.urgency === key &&
						// "This week" means it. An assignment three weeks out is real, but
						// it is not what Home is for, and letting it in is what made the
						// card fourteen rows long in the first place.
						(key !== 'upcoming' || row.due.days <= WEEK)
				)
				.sort(byOrder(order, (a, b) => a.due.days - b.due.days))
		};
	});

	const total = rows.length;

	return {
		groups,
		done,
		total,
		doneCount: done.length,
		percent: total === 0 ? 0 : (done.length / total) * 100
	};
}

/** Groups with at least one row. The empty ones render nothing, not a heading. */
export function nonEmptyGroups(groups: HomeGroup[]): HomeGroup[] {
	return groups.filter((group) => group.rows.length > 0);
}
