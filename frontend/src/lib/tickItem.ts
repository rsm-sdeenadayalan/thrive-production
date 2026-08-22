import { toggleQuickItem } from '$lib/quickList';
import type { ScheduleItem } from '$lib/schedule';
import { setTaskDone } from '$lib/userEdits.svelte';

/**
 * Tick anything tickable, from anywhere.
 *
 * A calendar row does not know whether it came from a task or a scratch to-do,
 * and it does not need to: `calendarSources` attaches the resolved source row
 * to the item at merge time, so the writer reads `item.task` or
 * `item.quickItem` and writes to the matching store. No id parsing, no array
 * search, no way to miss.
 *
 * ## What this replaced, and why
 *
 * The previous version sliced a prefix off `item.id` and searched an array of
 * server tasks. It missed two whole classes of row:
 *
 *   - Tasks the student added themselves live in `addedStore`, not in the
 *     server's array, so the search found nothing.
 *   - Undated to-dos in the agenda are built as synthetic items whose id was
 *     never prefixed, so the `startsWith("todo-")` test was false.
 *
 * Both failed identically and silently: the `if (found)` guard returned, the
 * checkbox appeared to tick because nothing re-rendered it, and the next render
 * put it back. Attaching the object removes the possibility.
 *
 */
export function tickItem(item: ScheduleItem, done: boolean): void {
	if (item.task) {
		// `setTaskDone` needs the source row so it can store an override rather
		// than the whole truth: unticking a task that ships done has to survive.
		setTaskDone(item.task, done);
		return;
	}

	if (item.quickItem) {
		// `toggleQuickItem` flips whatever it is given, so only call it when the
		// current state is not already what we want.
		if (item.quickItem.done !== done) toggleQuickItem(item.quickItem);
		return;
	}

	/*
	 * Everything else is untickable, and that is a decision rather than a gap.
	 *
	 * Classes, assignments, appointments and events are not things a student
	 * completes. Neither are student-created custom events: they are things that
	 * happen, not things you finish, which is why `customEventToItem` gives them
	 * no `done` field and no source row. If that ever changes, the change is to
	 * give them a source row here, not to add another id-prefix branch.
	 */
}

/**
 * True when this row can be ticked at all.
 *
 * Derived from whether a writable source is attached, not from whether `done`
 * happens to be set. Those can disagree: a synthetic row could carry a `done`
 * flag with nothing to write it back to, which is exactly how the agenda's
 * undated to-dos used to render a checkbox that did nothing.
 */
export function isTickable(item: ScheduleItem): boolean {
	return item.task !== undefined || item.quickItem !== undefined;
}
