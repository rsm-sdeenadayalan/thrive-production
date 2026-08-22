/**
 * One transient confirmation line, app-wide.
 *
 * Deliberately a single slot rather than a queue: the only thing that raises a
 * toast in THRIVE is copying a row between the two lists, and two of those in
 * quick succession should replace each other rather than stack into a column
 * the student has to wait out.
 *
 * Not persisted -- a confirmation that survives a reload has stopped being a
 * confirmation. So there is no hydration here and nothing to gate: the server
 * renders no toast because there is never a toast to render.
 */

const VISIBLE_MS = 3000;

let current = $state<string | null>(null);
let timer: ReturnType<typeof setTimeout> | null = null;

export function showToast(message: string) {
	current = message;
	if (timer) clearTimeout(timer);
	timer = setTimeout(() => {
		current = null;
	}, VISIBLE_MS);
}

/** The line currently showing, or null. Was `useToast()`. */
export const toast = () => current;

/**
 * Drop the current toast immediately.
 *
 * Not in the Next version, which had no way to dismiss early. Added because
 * the tests need to reset a module singleton between cases and a 3000ms wait
 * is not a test strategy. Harmless to the UI, which never calls it.
 */
export function clearToast() {
	if (timer) clearTimeout(timer);
	timer = null;
	current = null;
}
