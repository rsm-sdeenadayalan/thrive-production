import { createPanelStore } from "$lib/floatingPanel";
import { createOverrideStore } from "$lib/overrideStore.svelte";

/**
 * The floating quick list: a personal scratch list, deliberately separate from
 * Home's Tasks card.
 *
 * Tasks on Home come from somewhere -- a course, a deadline, an advisor -- and
 * carry a due date, a priority, and a source. These do not. They are the things
 * a student writes on the back of their hand, and mixing them into the list
 * that says "pulled from every source" would make that claim untrue.
 *
 * Items can be *copied* between the two lists, never linked. See `copiedFrom`.
 */

export interface QuickItem {
	id: string;
	title: string;
	done: boolean;
	/** Sort key. The map the store keeps has no order of its own. */
	createdAt: number;
	/**
	 * Set when this item was copied in from the Tasks card.
	 *
	 * A note about provenance, not a link: nothing reads it to keep the two in
	 * step, because they are deliberately not in step. Ticking or deleting here
	 * has no effect there, and the field exists so a future reader of the store
	 * can tell where a row came from.
	 */
	copiedFrom?: string;
	/**
	 * Optional. Most things on a scratch list never get one, so the chip and the
	 * picker stay out of the row until there is a date to show.
	 */
	dueDate?: string;
	/** Personal note, revealed by expanding the row. */
	note?: string;
}

const items = createOverrideStore<QuickItem>("thrive:quicklist");
const panel = createPanelStore("thrive:quicklist-panel");

/** Was `useQuickListPanel()`. */
export const quickListPanel = panel.panel;
export const setQuickListPanel = panel.setPanel;
export const readQuickListPanel = panel.readPanel;

/**
 * Every item, oldest first. Reactive.
 *
 * Sorts on read rather than caching. React needed `useQuickItems` to hand back
 * a stable array so downstream memos did not bust; nothing in Svelte depends on
 * that, and a list this size sorts for free.
 */
export function quickItems(): QuickItem[] {
	return Object.values(items.values).sort((a, b) => a.createdAt - b.createdAt);
}

/** Read outside a reactive context, for the copy actions. */
export function readQuickItems(): QuickItem[] {
	return Object.values(items.read()).sort((a, b) => a.createdAt - b.createdAt);
}

/** Returns the new item's id, or null for an empty title. */
export function addQuickItem(
	title: string,
	extra: Pick<QuickItem, "copiedFrom" | "dueDate"> = {},
): string | null {
	const trimmed = title.trim();
	if (!trimmed) return null;

	// Date.now() twice in one millisecond would collide, so the counter breaks
	// ties. Adding two items faster than the clock ticks is not hypothetical
	// when the second one comes from a "copy" button.
	const id = `q-${Date.now().toString(36)}-${nextSuffix()}`;
	items.set(id, {
		id,
		title: trimmed,
		done: false,
		createdAt: Date.now(),
		...extra,
	});

	return id;
}

let suffix = 0;
function nextSuffix() {
	suffix += 1;
	return suffix.toString(36);
}

export function toggleQuickItem(item: QuickItem) {
	items.set(item.id, { ...item, done: !item.done });
}

/** Set or clear the due date. An empty value clears it rather than storing "". */
export function setQuickItemDue(item: QuickItem, iso: string | undefined) {
	items.set(item.id, { ...item, dueDate: iso });
}

/** An emptied note is a deleted note, not an empty string to render around. */
export function setQuickItemNote(item: QuickItem, note: string) {
	const trimmed = note.trim();
	items.set(item.id, { ...item, note: trimmed || undefined });
}

export function deleteQuickItem(id: string) {
	items.set(id, undefined);
}

export function clearDoneQuickItems() {
	for (const item of Object.values(items.read())) {
		if (item.done) items.set(item.id, undefined);
	}
}
