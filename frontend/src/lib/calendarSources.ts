import {
	customEventToItem,
	itemLabels,
	itemUrgent,
	customEvents,
	labelFor,
	urgentFor
} from '$lib/calendarItems';
import { quickItems, type QuickItem } from '$lib/quickList';
import {
	dayKeyOf,
	minutesOf,
	wallClockLabel,
	type DatedScheduleItem,
	type ScheduleData
} from '$lib/schedule';
import {
	addedTasks,
	applyTaskEdits,
	isTaskDone,
	taskDoneOverrides,
	taskDues,
	taskPriorities,
	taskTitles
} from '$lib/userEdits.svelte';
import type { Task } from '$lib/data';

/**
 * The client half of the calendar's data.
 *
 * ## Why this exists at all
 *
 * `buildSchedule.ts` reads the providers on the server and hands down a fully
 * formatted `ScheduleData`. That works because classes, assignments,
 * appointments and events are all server truth.
 *
 * Tasks and to-dos are not:
 *
 *   - A task's due date can be MOVED by the student, and stored only in
 *     localStorage. The server's `dueDate` is then wrong for this person.
 *   - A student can ADD a task that exists nowhere on the server.
 *   - A quick-list to-do has no server row at all. It is localStorage only.
 *
 * So the calendar cannot be fed from one pipeline. This module is the second
 * half: it reads the same stores the Tasks card reads and folds them onto the
 * server's `ScheduleData`.
 *
 * ## Why not just put them on the server
 *
 * The mock stores were module-level and shared by every visitor to the dev
 * server. Writing one student's to-dos there would put them on another
 * student's calendar. Local is the correct answer until the Django backend
 * settles it.
 *
 * ## Hydration
 *
 * Every store read here is empty until `hydrateStores()` has run, so the server
 * and the first client render both see "no personal items" and the student's own
 * rows land on the render after mount. Nothing in this module may be called
 * during a server render expecting personalised output -- it will be correct,
 * just un-personalised.
 *
 * ## The memo moved to the call site
 *
 * `useMergedSchedule` was a hook wrapping all of this in a `useMemo` over nine
 * dependencies. `mergedSchedule` is a plain function instead, because in Svelte
 * the caller is the only place that knows what to key the caching on:
 *
 *     const merged = $derived(mergedSchedule(data, tasks));
 *
 * That reads the same signals, recomputes when any of them actually changes,
 * and needs no dependency array to keep in sync with the body. Threading nine
 * dependencies by hand was a React obligation, not a design.
 */

/**
 * Turn a `Task` into a dated calendar row.
 *
 * Tasks are deadlines, not meetings, so they sort by their due instant exactly
 * the way assignments already do. They are never all-day: a task due "today"
 * still has a time, and treating it as all-day would float it above a class it
 * is actually due after.
 */
export function taskToItem(task: Task, done: boolean): DatedScheduleItem | null {
	const date = new Date(task.dueDate);
	if (Number.isNaN(date.getTime())) return null;

	return {
		id: `task-${task.id}`,
		category: 'task',
		title: task.title,
		dayKey: dayKeyOf(date),
		timeLabel: date.toLocaleTimeString('en-US', {
			hour: 'numeric',
			minute: '2-digit'
		}),
		detail: task.courseCode ?? '',
		sortMinutes: date.getHours() * 60 + date.getMinutes(),
		allDay: false,
		startISO: task.dueDate,
		endISO: task.dueDate,
		done,
		priority: task.priority,
		courseCode: task.courseCode,
		// The resolved row travels with the item, so ticking never has to find it
		// again. This is the whole fix for self-added tasks: they are not in the
		// server's array, but they are right here.
		task
	};
}

/**
 * Quick-list items are all-day by design.
 *
 * A scratch to-do carries a date at most, never a time -- the picker does not
 * offer one. Marking them all-day puts them at the top of a day rather than
 * inventing a midnight slot that would sort them before every class.
 */
export function todoToItem(quick: QuickItem): DatedScheduleItem | null {
	if (!quick.dueDate) return null;

	const date = new Date(quick.dueDate);
	if (Number.isNaN(date.getTime())) return null;

	return {
		id: `todo-${quick.id}`,
		category: 'todo',
		title: quick.title,
		dayKey: dayKeyOf(date),
		timeLabel: 'All day',
		detail: '',
		sortMinutes: 0,
		allDay: true,
		startISO: quick.dueDate,
		endISO: quick.dueDate,
		done: quick.done,
		quickItem: quick
	};
}

export interface MergedSchedule {
	data: ScheduleData;
	/**
	 * To-dos the student never dated. Surfaced by the agenda, not the grid.
	 *
	 * The whole `QuickItem` rather than a flattened triple, so the agenda can
	 * attach it to the synthetic row it builds and ticking works there too. The
	 * flattened version was the reason undated to-dos silently would not tick.
	 */
	undatedTodos: QuickItem[];
}

/**
 * Fold the student's tasks, to-dos and custom events onto the server's schedule.
 *
 * `serverTasks` comes from `getTasks()` through the page's `load`, so the server
 * rows are still the source of truth for anything the student has not edited.
 *
 * Call this inside a `$derived` -- see the note at the top of the module.
 */
export function mergedSchedule(server: ScheduleData, serverTasks: Task[]): MergedSchedule {
	const titles = taskTitles();
	const priorities = taskPriorities();
	const dues = taskDues();
	const added = addedTasks();
	const doneOverrides = taskDoneOverrides();
	const quick = quickItems();
	const labels = itemLabels();
	const urgent = itemUrgent();
	const custom = customEvents();

	// Student-created tasks sit alongside the server's, keyed by id so an added
	// task cannot be listed twice if it ever gains a server row.
	const byId = new Map<string, Task>();
	for (const task of serverTasks) byId.set(task.id, task);
	for (const task of Object.values(added)) byId.set(task.id, task);

	const taskItems: DatedScheduleItem[] = [];

	for (const source of byId.values()) {
		// Edits first, then the due-date override, so a renamed AND rescheduled
		// task lands correctly on both counts.
		const edited = applyTaskEdits(source, titles, priorities);
		const dueDate = dues[source.id] ?? edited.dueDate;
		const task: Task = { ...edited, dueDate };

		const item = taskToItem(task, isTaskDone(task, doneOverrides));
		if (item) taskItems.push(item);
	}

	const todoItems: DatedScheduleItem[] = [];
	const undatedTodos: MergedSchedule['undatedTodos'] = [];

	for (const item of quick) {
		if (!item.dueDate) {
			undatedTodos.push(item);
			continue;
		}

		const row = todoToItem(item);
		if (row) todoItems.push(row);
	}

	const customItems = custom
		.map(customEventToItem)
		.filter((item): item is DatedScheduleItem => item !== null);

	/*
	 * Labels and urgent are applied LAST, over everything.
	 *
	 * They are keyed by calendar item id rather than by source id, which is
	 * what lets a student flag an assignment or label an appointment -- rows
	 * they do not own and cannot otherwise touch. Applying them here, once,
	 * means no individual mapper has to know they exist.
	 *
	 * Urgent is suppressed on a done item. A finished thing is not urgent, and
	 * a coral pill on a struck-through row is the sort of contradiction the
	 * reserved palette exists to prevent.
	 *
	 * Both rules come from `calendarItems` rather than being written here, because
	 * `ItemDetail` has to answer the same two questions about the row it is showing
	 * and a second copy would drift the day either of them grows a case.
	 */
	const annotate = (item: DatedScheduleItem): DatedScheduleItem => {
		const label = labelFor(item.id, item.label, labels);
		const isUrgent = urgentFor(item.id, item.urgent, urgent, item.done);

		/*
		 * Return the original only when NOTHING differs, rather than when neither
		 * value is set.
		 *
		 * The `!label && !isUrgent` shortcut this replaces is subtly wrong once the
		 * done-suppression moved into `urgentFor`: a row arriving urgent AND done,
		 * with no label, would take the shortcut and keep the flag the suppression
		 * exists to remove. Only custom events can arrive carrying `urgent`, and
		 * they are never done, so it was unreachable -- but "unreachable" is a
		 * property of today's mappers, not of this function.
		 */
		if (label === item.label && isUrgent === (item.urgent === true)) return item;

		return {
			...item,
			label,
			urgent: isUrgent ? true : undefined
		};
	};

	return {
		data: {
			dated: [...server.dated, ...taskItems, ...todoItems, ...customItems].map(annotate),
			recurring: server.recurring
		},
		undatedTodos
	};
}

/**
 * Minutes past midnight, right now.
 *
 * ONE OF ONLY TWO CLIENT-SIDE CLOCK READS IN THE APP, and it is deliberate.
 * Only ever called from a click handler or inside a memo on the client, never
 * during a server render, so it cannot desynchronise hydration. Exported so
 * `nextUpItem` stays pure and testable while callers stay honest about time.
 *
 * See CONVENTIONS.md. This is an exception to the rule, not a licence.
 */
export function nowMinutes(): number {
	const now = new Date();
	return now.getHours() * 60 + now.getMinutes();
}

/** Re-exported so callers building a week strip do not import two modules. */
export { minutesOf, wallClockLabel };
