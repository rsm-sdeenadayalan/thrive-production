import { createOverrideStore } from "$lib/overrideStore.svelte";
import type { Priority, Task } from "$lib/data";

/**
 * The student's own edits, persisted.
 *
 * Seven stores, all overrides over provider truth (see `overrideStore.svelte.ts`).
 * The things a student can actually do in THRIVE are the things that must not
 * evaporate on navigation.
 *
 * `taskNotes.svelte.ts` keeps its own store for the same reason it always did --
 * notes are free text, not an override of anything.
 *
 * `.svelte.ts` because the undo slot below is `$state`.
 */

const doneStore = createOverrideStore<boolean>("thrive:task-done");
/** Keyed on the RAW `Event.id`, not on a task id. See `isEventJoined`. */
const joinStore = createOverrideStore<boolean>("thrive:event-joins");
const titleStore = createOverrideStore<string>("thrive:task-titles");
const priorityStore = createOverrideStore<Priority>("thrive:task-priority");
const dueStore = createOverrideStore<string>("thrive:task-due");
const orderStore = createOverrideStore<number>("thrive:task-order");
/** Tasks the student created. Not overrides -- these have no source row. */
const addedStore = createOverrideStore<Task>("thrive:task-added");

export type DoneOverrides = Readonly<Record<string, boolean>>;
export type JoinOverrides = Readonly<Record<string, boolean>>;

/*
 * Reactive readers.
 *
 * These were `use*` hooks in React. The prefix is gone because nothing about
 * them is a hook any more: there are no call-order rules, they work outside a
 * component, and they can be called conditionally. Read one inside a component
 * or a `$derived` and that reader re-runs when the store changes.
 */

/** Every done-override the student has made, keyed by task id. */
export const taskDoneOverrides = () => doneStore.values;

/** Every event the student has said yes to, keyed by RAW `Event.id`. */
export const eventJoins = () => joinStore.values;

/** Titles the student has rewritten, keyed by task id. */
export const taskTitles = () => titleStore.values;

/** Priorities the student has reset, keyed by task id. */
export const taskPriorities = () => priorityStore.values;

export const taskDues = () => dueStore.values;
export const taskOrder = () => orderStore.values;
export const addedTasks = () => addedStore.values;

/**
 * Is this task done, accounting for the student's edits?
 *
 * The provider answers unless the student has said otherwise.
 */
export function isTaskDone(task: Task, overrides: DoneOverrides): boolean {
	return overrides[task.id] ?? task.done;
}

/**
 * Record (or clear) a done-override.
 *
 * Matching the source value FORGETS the override rather than storing it, so the
 * store only ever holds genuine divergence and a task that later changes at the
 * source is not pinned to a stale answer. This is the property that makes
 * "I unticked something that ships as done" expressible at all.
 */
export function setTaskDone(task: Task, done: boolean) {
	doneStore.set(task.id, done === task.done ? undefined : done);
}

/**
 * Has the student said "count me in" for this event?
 *
 * ## The key is a RAW `Event.id`, settled in Phase 7c
 *
 * `evt-3-1`. Never the calendar item id `evt-evt-3-1`, and never `3-1`.
 *
 * The Next tree keyed this store on the CALENDAR ITEM id -- MIGRATION.md §9
 * defect 13 -- which is the same defect that was fixed in the ignore store in
 * 7a, sitting in a second store. It was invisible there because the join store
 * had exactly one consumer, and one consumer can be self-consistent under any
 * key space at all.
 *
 * 7c built that consumer, so the decision was made with it in front of us:
 *
 *  - **The two stores are asked about the same thing by the same row.** A
 *    `DayEventsSection` row offers "count me in" and "ignore" side by side.
 *    Under the old shape it would hold TWO ids for one event and have to
 *    remember which control took which -- the precise arrangement that produced
 *    two stores wearing one name last time.
 *  - **Home already holds the other id.** `EventRow` has a "count me in" button
 *    sitting inert, with a comment saying it is inert *because this key space
 *    was unsettled*. Home holds an `Event`, so it holds `event.id` -- raw. Wiring
 *    it under the item-id shape would have written a key the calendar never reads.
 *  - **Nothing argues the other way.** A join is a fact about an EVENT, not about
 *    a row on a particular day. Labels and urgent are keyed by calendar item id
 *    for the opposite reason: those annotate a row the student may not own, on
 *    streams that have no event behind them at all.
 *
 * So there are still three key spaces, not four: task id (`userEdits`'s six
 * other stores), calendar item id (`calendarItems`), and raw `Event.id`
 * (`ignoredEvents` and this one). The calendar sheds its prefix at its own
 * boundary, in `calendarEvents.ts`, exactly once.
 *
 * Keys written under the old shape stay in `localStorage` and are inert. Not
 * migrated, and the same reasoning as 7a: absence means "never joined" here, so
 * a stale key is harmless rather than corrupt, and this is mock data in dev. A
 * student who joined an event before this change is asked once more.
 */
export function isEventJoined(id: string, joins: JoinOverrides): boolean {
	return joins[id] ?? false;
}

/**
 * Say yes, or take it back. Takes a RAW `Event.id` -- see the note above.
 *
 * Nothing is sent anywhere; this is local intent only. No normalising happens
 * here, deliberately: a caller holding a calendar item id converts at its own
 * boundary, where it is the only party that knows which kind of id it has. The
 * ignore store states the same rule for the same reason.
 */
export function setEventJoined(id: string, joined: boolean) {
	// Not joined is the default, so store the absence rather than `false`.
	joinStore.set(id, joined ? true : undefined);
}

/* --- Editing a task in place ------------------------------------------ */

/**
 * The task as the student sees it: source values, with their edits applied.
 *
 * Returning a whole `Task` rather than loose fields means everything
 * downstream -- `rowPriorityOf`, `taskLabels`, the notes key -- keeps working
 * unchanged on the edited version.
 */
export function applyTaskEdits(
	task: Task,
	titles: Readonly<Record<string, string>>,
	priorities: Readonly<Record<string, Priority>>,
): Task {
	const title = titles[task.id];
	const priority = priorities[task.id];
	if (title === undefined && priority === undefined) return task;

	return {
		...task,
		title: title ?? task.title,
		priority: priority ?? task.priority,
	};
}

/** An emptied title is a reverted title, not a blank row. */
export function setTaskTitle(task: Task, title: string) {
	const trimmed = title.trim();
	titleStore.set(task.id, !trimmed || trimmed === task.title ? undefined : trimmed);
}

export function setTaskPriority(task: Task, priority: Priority) {
	priorityStore.set(task.id, priority === task.priority ? undefined : priority);
}

/* --- Due dates, order, and tasks the student added -------------------- */

/**
 * Move a task to a new due date.
 *
 * Stored as a full ISO instant, not a day: the rest of THRIVE sorts and
 * classifies on instants, and a date-only string would land at UTC midnight
 * and read as the previous day for anyone behind UTC.
 */
export function setTaskDue(task: Task, iso: string) {
	const added = addedStore.read()[task.id];
	if (added) {
		// A student-created task has no source row to diverge from, so the edit
		// belongs on the task itself rather than in the override map.
		addedStore.set(task.id, { ...added, dueDate: iso });
		return;
	}
	dueStore.set(task.id, iso === task.dueDate ? undefined : iso);
}

/** Sort key within a group. Sparse on purpose -- see `reorderWithin`. */
export function setTaskOrder(id: string, order: number | undefined) {
	orderStore.set(id, order);
}

export function addTask(task: Task) {
	addedStore.set(task.id, task);
}

export function removeAddedTask(id: string) {
	addedStore.set(id, undefined);
	// Leave no orphaned overrides behind pointing at an id that no longer exists.
	dueStore.set(id, undefined);
	orderStore.set(id, undefined);
	titleStore.set(id, undefined);
	priorityStore.set(id, undefined);
	doneStore.set(id, undefined);
}

/**
 * Rewrite the sort keys for one group after a move.
 *
 * Keys are written for the whole group rather than just the moved row: a
 * single key cannot express "between these two" once several rows share the
 * provider's implicit order, and rewriting the group is cheap at this size.
 */
export function reorderWithin(ids: string[]) {
	ids.forEach((id, index) => orderStore.set(id, index));
}

/* --- Ticking a task, with a way back ---------------------------------- */

/**
 * How long the undo offer stands.
 *
 * Long enough to notice a mis-tap and reach for it one-handed, short enough
 * that it is gone before it becomes furniture.
 */
const UNDO_MS = 6000;

/** The last toggle, held only so it can be taken back. */
export interface TaskUndo {
	task: Task;
	markedDone: boolean;
}

let undo = $state<TaskUndo | null>(null);
let timer: ReturnType<typeof setTimeout> | null = null;

/**
 * Done state plus undo, shared by every surface that lists tasks.
 *
 * Home and /assignments render the identical task row, so they must also agree
 * on what "done" means and how long a mistake stays reversible.
 *
 * ## One slot, app-wide
 *
 * In React this was `useTaskToggle()`, a hook holding the undo in `useState`,
 * so each calling component had its own slot. Here it is a module singleton, so
 * there is exactly one offer standing at a time no matter how many surfaces are
 * mounted.
 *
 * That matches what the rest of the app already does deliberately -- `toast` is
 * "a single slot, not a queue", and the ignore undo is documented as one slot
 * where a second dismissal replaces the first. In practice only one task
 * surface is mounted at a time, so the two behave identically today.
 *
 * The `useEffect` that used to clear the timer on unmount is gone: a module
 * singleton has no unmount, and the timer is armed from the event handler
 * rather than from an effect, exactly as before.
 */
export const taskToggle = {
	isDone(task: Task): boolean {
		return isTaskDone(task, doneStore.values);
	},

	/** The task with the student's title and priority edits applied. */
	resolve(task: Task): Task {
		return applyTaskEdits(task, titleStore.values, priorityStore.values);
	},

	/** The offer currently standing, if any. */
	get undo(): TaskUndo | null {
		return undo;
	},

	toggle(task: Task): void {
		const markedDone = !this.isDone(task);
		setTaskDone(task, markedDone);

		if (timer) clearTimeout(timer);
		undo = { task, markedDone };
		timer = setTimeout(() => {
			undo = null;
		}, UNDO_MS);
	},

	applyUndo(): void {
		if (!undo) return;
		setTaskDone(undo.task, !undo.markedDone);
		if (timer) clearTimeout(timer);
		undo = null;
	},
};
