import { createOverrideStore } from "$lib/overrideStore.svelte";
import { dayKeyOf, type DatedScheduleItem } from "$lib/schedule";

/**
 * What the student adds to, or says about, the calendar.
 *
 * Three separate stores rather than one blob, because they have genuinely
 * different lifetimes:
 *
 *   labels   an annotation ON an item that may not be the student's
 *   urgent   a flag ON an item that may not be the student's
 *   custom   an item the student created, which nothing else knows about
 *
 * ## Why labels and urgent are keyed by CALENDAR item id
 *
 * Not by task id. The ids used here are the ones the calendar builds --
 * `asg-12`, `apt-3`, `task-7`, `todo-x` -- which means a student can flag an
 * assignment urgent or label a booked appointment, neither of which they own
 * and neither of which has anywhere on the server to put that. Keying by task
 * id would have limited both features to the one stream the student can
 * already edit, which is the stream that needed them least.
 *
 * This is one of THREE deliberate key spaces in the app and must not be merged
 * with the others: task id (`userEdits`), calendar item id (here), and raw
 * `Event.id` normalised through `eventIdOf` (`ignoredEvents`). Merging them is
 * the exact shape of the bug the ignore store was refactored to avoid.
 *
 * ## Why custom events are not "events"
 *
 * `getEvents()` returns programme events with an origin (career, rady, club).
 * A thing the student typed has no origin, cannot be registered for, and must
 * not appear to be Rady-issued. It gets its own category so the key can filter
 * it separately and so nothing downstream mistakes it for institutional truth.
 */

/* --- Labels ------------------------------------------------------------- */

const labelStore = createOverrideStore<string>("thrive:item-labels");

/** Was `useItemLabels()`. */
export const itemLabels = () => labelStore.values;

/** An emptied label is a removed label, not a blank chip. */
export function setItemLabel(itemId: string, label: string) {
	const trimmed = label.trim();
	labelStore.set(itemId, trimmed || undefined);
}

/* --- Urgent ------------------------------------------------------------- */

const urgentStore = createOverrideStore<true>("thrive:item-urgent");

/** Was `useItemUrgent()`. */
export const itemUrgent = () => urgentStore.values;

/**
 * Not-urgent is the default, so the absence is stored rather than `false`.
 * That keeps the map small and makes "has the student ever touched this"
 * answerable, which `false` would not.
 */
export function setItemUrgent(itemId: string, urgent: boolean) {
	urgentStore.set(itemId, urgent ? true : undefined);
}

/* --- Custom events ------------------------------------------------------ */

export interface CustomEvent {
	id: string;
	title: string;
	/** "YYYY-MM-DD", local. */
	dayKey: string;
	/** "HH:mm" wall clock. Absent means all-day. */
	time?: string;
	label?: string;
	urgent?: boolean;
	createdAt: number;
}

const customStore = createOverrideStore<CustomEvent>("thrive:custom-events");

/** Was `useCustomEvents()`. Oldest first. */
export function customEvents(): CustomEvent[] {
	return Object.values(customStore.values).sort((a, b) => a.createdAt - b.createdAt);
}

export function readCustomEvents(): CustomEvent[] {
	return Object.values(customStore.read());
}

export function addCustomEvent(
	event: Omit<CustomEvent, "id" | "createdAt"> & { id?: string },
): string {
	// `createdAt` is the sort key and the id seed. Not Math.random: two events
	// added in the same millisecond are vanishingly unlikely, and a deterministic
	// id is easier to reason about when something goes wrong.
	const createdAt = Date.now();
	const id = event.id ?? `custom-${createdAt}`;

	customStore.set(id, { ...event, id, createdAt });
	return id;
}

export function updateCustomEvent(id: string, patch: Partial<CustomEvent>) {
	const existing = customStore.read()[id];
	if (!existing) return;
	customStore.set(id, { ...existing, ...patch, id });
}

/**
 * Delete an event and everything said about it.
 *
 * Leaving the label and urgent overrides behind would orphan them against an
 * id that no longer exists, and they would silently reattach if the id were
 * ever reused. `removeAddedTask` in `userEdits` cleans up the same way.
 *
 * Note the `custom-` prefix: those two stores are keyed by CALENDAR item id,
 * and `customEventToItem` builds this event's item id as `custom-${event.id}`.
 */
export function deleteCustomEvent(id: string) {
	customStore.set(id, undefined);
	labelStore.set(`custom-${id}`, undefined);
	urgentStore.set(`custom-${id}`, undefined);
}

/* --- Resolving an annotation over a row --------------------------------- */

/**
 * The label a row actually shows: the student's, or whatever it came with.
 *
 * ONE rule, in one place, because it now has two callers that must not
 * disagree. `mergedSchedule` applies it to every row on the calendar;
 * `ItemDetail` applies it to the row it is showing, so the field a student
 * types into reflects the same answer the row behind the dialog does.
 *
 * Written inline in both places, this is the kind of pair that stays in step
 * until someone adds a third state to one of them.
 */
export function labelFor(
	itemId: string,
	base: string | undefined,
	labels: Readonly<Record<string, string>>,
): string | undefined {
	return labels[itemId] ?? base;
}

/**
 * Is this row urgent?
 *
 * The student's flag wins over whatever the row arrived with, and DONE
 * SUPPRESSES IT outright. A finished thing is not urgent, and a coral pill on a
 * struck-through row is the sort of contradiction the reserved palette exists to
 * prevent -- which is why the suppression lives in the shared rule rather than
 * in the merge, where the dialog could not see it.
 */
export function urgentFor(
	itemId: string,
	base: boolean | undefined,
	urgent: Readonly<Record<string, true>>,
	done: boolean | undefined,
): boolean {
	return (urgent[itemId] ?? base) === true && done !== true;
}

/* --- Mapping ------------------------------------------------------------ */

/** "9:30 AM" from wall-clock "HH:mm". Local by construction, no timezone. */
function clockLabel(hhmm: string): string {
	const [hour, minute] = hhmm.split(":").map(Number);
	if (Number.isNaN(hour) || Number.isNaN(minute)) return "All day";
	const suffix = hour < 12 ? "AM" : "PM";
	const display = hour % 12 === 0 ? 12 : hour % 12;
	return `${display}:${String(minute).padStart(2, "0")} ${suffix}`;
}

/**
 * A custom event as a calendar row.
 *
 * Returns null on a malformed day key rather than rendering an item onto some
 * arbitrary day, which is how a hand-edited store would otherwise put a
 * student's note on a date they never chose.
 */
export function customEventToItem(event: CustomEvent): DatedScheduleItem | null {
	const parts = event.dayKey.split("-").map(Number);
	if (parts.length !== 3 || parts.some(Number.isNaN)) return null;

	const [year, month, day] = parts;
	const date = new Date(year, month - 1, day);
	if (Number.isNaN(date.getTime())) return null;
	// A key like "2026-02-31" parses into March. Reject rather than silently move.
	if (dayKeyOf(date) !== event.dayKey) return null;

	const allDay = !event.time;
	const [hour, minute] = allDay ? [0, 0] : event.time!.split(":").map(Number);

	return {
		id: `custom-${event.id}`,
		category: "custom",
		title: event.title,
		dayKey: event.dayKey,
		timeLabel: allDay ? "All day" : clockLabel(event.time!),
		detail: "",
		sortMinutes: allDay ? 0 : hour * 60 + minute,
		allDay,
		startISO: new Date(year, month - 1, day, hour, minute).toISOString(),
		endISO: new Date(year, month - 1, day, hour, minute).toISOString(),
		label: event.label,
		urgent: event.urgent,
		custom: true,
		/*
		 * THE SOURCE ROW TRAVELS WITH THE ITEM, exactly as `taskToItem` and
		 * `todoToItem` attach theirs.
		 *
		 * `ItemDetail` needs the event's own id to delete it, and the calendar item
		 * id is not it: this line builds `custom-${event.id}` and `event.id` is
		 * itself `custom-<timestamp>`, so the item id carries the prefix twice
		 * (MIGRATION.md §9 defect 14 -- cosmetic, internally consistent, and not
		 * being changed here because existing stores would go stale for nothing).
		 *
		 * The Next version recovered the event id with
		 * `item.id.replace(/^custom-/, "")`, which is resolving a row by parsing its
		 * id -- the one thing CONVENTIONS.md says never to do, and the thing that
		 * silently broke ticking for self-added tasks. Attaching the row means the
		 * delete button cannot be wrong about which event it deletes.
		 */
		customEvent: event,
	};
}
