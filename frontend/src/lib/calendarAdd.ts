import { addCustomEvent, setItemLabel, setItemUrgent } from "$lib/calendarItems";
import { addQuickItem } from "$lib/quickList";
import { fromDayKey } from "$lib/schedule";
import { addTask } from "$lib/userEdits.svelte";

/**
 * Adding something to a day, as arithmetic.
 *
 * ## Three kinds, three stores, and that IS the component
 *
 * `AddItemForm` is a radio group, three inputs and a submit button. The only
 * thing in it that can be wrong in a way nobody notices is WHERE each kind
 * lands:
 *
 *   task   work with a deadline  -> `thrive:task-added`   (joins Home's Tasks list)
 *   to-do  a scratch item        -> `thrive:quicklist`    (joins the quick list)
 *   event  something happening   -> `thrive:custom-events` (goes nowhere else)
 *
 * A to-do filed as a task appears on Home's list under a heading that says
 * "pulled from every source", which is then untrue. A task filed as an event
 * cannot be ticked, so a deadline silently stops being a deadline. Neither
 * throws, neither fails a type check, and neither is visible on the day it
 * happens -- it is visible a week later on a different page.
 *
 * So the routing lives here, outside the component, where the suite can watch
 * it. `calendarAdd.spec.ts` asserts for each kind that its own store gained a
 * key AND that the other two did not.
 *
 * ## What is deliberately NOT stored
 *
 * The Next version passed `label` and `urgent` into `addCustomEvent` *and* wrote
 * them to the annotation stores, so a custom event carried each flag twice. That
 * is not merely redundant: `mergedSchedule` resolves urgent as
 * `override ?? item.urgent`, so clearing the flag in `ItemDetail` wrote
 * `undefined` to the override and then fell back to the copy on the event --
 * un-marking an event you had marked urgent did nothing at all. Here the
 * annotations are written to the annotation stores only, for all three kinds
 * alike, and the `CustomEvent` fields stay for anything that arrives already
 * carrying them.
 */

export type AddKind = "task" | "todo" | "event";

/** The three kinds in the order the form offers them. */
export const ADD_KINDS: readonly AddKind[] = ["task", "todo", "event"];

export interface ItemDraft {
	/** "YYYY-MM-DD", the day being added to. */
	dayKey: string;
	title: string;
	/** Wall clock "HH:mm". Ignored for a to-do, which has no time. */
	time: string;
	label: string;
	urgent: boolean;
}

/**
 * The default time on the form.
 *
 * 9:00, NOT "now". Adding something to next Tuesday at the current wall-clock
 * time is almost never what was meant, and it would also make this module read
 * the clock for no reason.
 */
export const DEFAULT_ADD_TIME = "09:00";

/**
 * The instant a day key plus a wall clock names, as ISO.
 *
 * Built from local parts through `fromDayKey`, never by concatenating the day
 * key with the time and parsing it -- `new Date("2026-08-17T09:00")` is
 * implementation-defined about timezone and `"...Z"` would be an hour or eight
 * out. Returns null when either part will not parse, so a hand-edited value
 * cannot mint a row on a date nobody chose.
 */
export function instantFor(dayKey: string, time: string): string | null {
	const date = fromDayKey(dayKey);
	if (Number.isNaN(date.getTime())) return null;

	const [hour, minute] = time.split(":").map(Number);
	if (!Number.isFinite(hour) || !Number.isFinite(minute)) return null;

	date.setHours(hour, minute, 0, 0);
	return date.toISOString();
}

/**
 * Put the draft in its store, and return the CALENDAR ITEM id it will render under.
 *
 * The id is returned rather than discarded because the two annotation stores are
 * keyed by calendar item id, so the label and the urgent flag can be attached
 * before the item has ever been rendered. It is also what lets a caller say
 * something true about what it just created.
 *
 * Returns null when there is nothing to add. An empty title is the only such
 * case the form can produce; the others are defensive against a malformed day
 * key, which the calendar cannot currently supply but a hand-built call could.
 *
 * `Date.now()` here is an id NONCE, not a clock read -- it is never parsed back
 * into a day. CONVENTIONS.md names this exception explicitly, and `quickList`
 * and `taskBoard` already rely on it.
 */
export function addCalendarItem(kind: AddKind, draft: ItemDraft): string | null {
	const title = draft.title.trim();
	if (!title) return null;

	const itemId = route(kind, title, draft);
	if (!itemId) return null;

	// Annotations last, over the item that now exists. Empty means absent: an
	// emptied label is a removed label and not-urgent is stored as nothing at all.
	if (draft.label.trim()) setItemLabel(itemId, draft.label);
	if (draft.urgent) setItemUrgent(itemId, true);

	return itemId;
}

/** The routing itself, kept separate so the annotation step cannot obscure it. */
function route(kind: AddKind, title: string, draft: ItemDraft): string | null {
	if (kind === "task") {
		const iso = instantFor(draft.dayKey, draft.time);
		if (!iso) return null;

		const id = `own-${Date.now()}`;
		addTask({
			id,
			title,
			dueDate: iso,
			source: "admin",
			// The urgent flag is a calendar annotation, but a task also has a real
			// priority field and "urgent" is what high priority means on Home. Setting
			// both is not double storage: they are read by two different surfaces.
			priority: draft.urgent ? "high" : "medium",
			done: false,
			subtasks: [],
		});
		return `task-${id}`;
	}

	if (kind === "todo") {
		/*
		 * The due date is what puts it on this day. Without it the to-do exists but
		 * lands in the agenda's "No date" bucket, which is not what someone pressing
		 * "add to this day" asked for.
		 *
		 * The instant is the day's start rather than the form's time, because a
		 * quick-list item is all-day by design -- `todoToItem` renders every one of
		 * them "All day" and the picker never offers a time. Storing 09:00 here would
		 * put a number in the store that nothing reads and that contradicts the row.
		 */
		const iso = instantFor(draft.dayKey, "00:00");
		if (!iso) return null;

		const id = addQuickItem(title, { dueDate: iso });
		return id ? `todo-${id}` : null;
	}

	const id = addCustomEvent({ title, dayKey: draft.dayKey, time: draft.time });
	return `custom-${id}`;
}
