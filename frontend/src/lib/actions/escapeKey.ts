import type { Action } from 'svelte/action';

/**
 * Call back when Escape is pressed, for as long as the node is mounted.
 *
 * A Svelte action rather than a translated `useEffect`. The React version was:
 *
 *     useEffect(() => {
 *       if (!moreOpen) return;
 *       function onKeyDown(e) { ... }
 *       document.addEventListener("keydown", onKeyDown);
 *       return () => document.removeEventListener("keydown", onKeyDown);
 *     }, [moreOpen]);
 *
 * -- an effect that had to re-check the open state it was already keyed on, and
 * whose dependency array is what kept the listener in step with it. Attaching
 * the behaviour to the element instead makes the lifetime the element's: put
 * `use:escapeKey` on something inside an `{#if open}` and the listener exists
 * exactly when the thing it dismisses does. Nothing to keep in step.
 *
 * The listener is on `document` rather than the node because a dismissable
 * region has to answer Escape from anywhere, including when focus has not
 * entered it yet.
 */
export const escapeKey: Action<HTMLElement, () => void> = (_node, onEscape) => {
	let callback = onEscape;

	function handle(event: KeyboardEvent) {
		if (event.key === 'Escape') callback();
	}

	document.addEventListener('keydown', handle);

	return {
		update(next: () => void) {
			callback = next;
		},
		destroy() {
			document.removeEventListener('keydown', handle);
		}
	};
};
