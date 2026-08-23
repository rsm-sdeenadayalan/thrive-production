/**
 * Personal notes on a task.
 *
 * Its own store rather than one built on `createOverrideStore`, kept that way
 * deliberately: a note is free text the student wrote, not an override of a
 * provider value. There is no "source note" for it to diverge from, so the
 * forget-on-match rule that defines an override store has nothing to compare
 * against here. Every other property still applies, and is implemented below.
 *
 * `localStorage` rather than anything server-side: a module-level store in a
 * node process is shared by every visitor, which is fine for seeded fixtures
 * and wrong for something described as "self notes".
 *
 * In API mode the same contract is served by the server seed primed from the
 * root layout.
 */

import { overlayEnabled, seedFor, syncOverlay } from "./overlaySync";

const KEY = "thrive:task-notes";

type NoteMap = Record<string, string>;

let notes = $state<NoteMap>({});
let hydrated = false;

function storage(): Storage | null {
	try {
		return typeof localStorage === "undefined" ? null : localStorage;
	} catch {
		return null;
	}
}

/**
 * Load the saved notes. Idempotent, and a no-op where there is no storage.
 *
 * Same contract as `overrideStore`: empty on the server and on the first client
 * render, real on the render after mount.
 */
export function hydrateTaskNotes(): void {
	if (hydrated) return;

	const seeded = seedFor(KEY);
	if (seeded) {
		hydrated = true;
		notes = seeded as NoteMap;
		return;
	}

	const store = storage();
	if (!store) return;

	hydrated = true;

	const raw = store.getItem(KEY);
	if (!raw) return;

	try {
		const parsed: unknown = JSON.parse(raw);
		/*
		 * HARDENED RELATIVE TO THE NEXT SOURCE.
		 *
		 * The Next version cast the parse result straight to a NoteMap with no
		 * shape check, so a stored array or number came through as one. Its
		 * sibling `overrideStore` did check. Nothing in the app wrote a bad value,
		 * so the gap was latent, but "corrupt input cannot take the page down" is
		 * a property of this layer and not of one module in it.
		 */
		notes =
			parsed && typeof parsed === "object" && !Array.isArray(parsed)
				? (parsed as NoteMap)
				: {};
	} catch {
		// A corrupt or unavailable store must not take the page down; the student
		// simply starts from no notes.
		notes = {};
	}
}

export function setNote(taskId: string, note: string) {
	// Load before writing, or this would persist one note over all the others.
	hydrateTaskNotes();

	const next = { ...notes };
	const trimmed = note.trim();

	if (trimmed) {
		next[taskId] = trimmed;
	} else {
		// An emptied note is a deleted note, not an empty string to render around.
		delete next[taskId];
	}

	notes = next;

	syncOverlay(KEY, taskId, trimmed || undefined);
	if (overlayEnabled()) return;

	const store = storage();
	if (!store) return;

	try {
		store.setItem(KEY, JSON.stringify(next));
	} catch {
		// Out of quota or blocked (private mode). The in-memory value still holds
		// the note for this session rather than silently discarding the edit.
	}
}

/**
 * All notes, as reactive state.
 *
 * Was `useTaskNotes()`. Every row editing the same store stays in step because
 * there is one store, not because of anything a hook does.
 */
export const taskNotes = () => notes;

/** One task's note plus a setter, the shape a row actually wants. */
export function taskNote(taskId: string) {
	return {
		get value(): string {
			return notes[taskId] ?? "";
		},
		save(note: string) {
			setNote(taskId, note);
		},
	};
}
