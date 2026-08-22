import type { Action } from 'svelte/action';

export interface ClickOutsideParams {
	onOutside: () => void;
	/**
	 * Nodes that count as inside even though they are not descendants.
	 *
	 * A disclosure's own trigger belongs here. Without it, pressing the trigger to
	 * close fires this listener first, the panel unmounts, and then the trigger's
	 * own click handler reopens the thing the student just dismissed -- a button
	 * that visibly refuses to close. The trigger is not inside the panel in the
	 * DOM, but it is inside the widget, which is the boundary that matters.
	 */
	alsoInside?: (HTMLElement | null | undefined)[];
}

/**
 * Call back when a pointer goes down anywhere outside this node.
 *
 * The sibling of `escapeKey`, and the same shape for the same reason: the
 * listener's lifetime is the element's. Put `use:clickOutside` on something
 * inside an `{#if open}` and it exists exactly when the thing it dismisses
 * does -- there is no open state to keep a listener in step with.
 *
 * `pointerdown` rather than `click`, on two counts. It fires before focus moves,
 * so a dismissal cannot race the focus handling; and a drag that starts outside
 * and ends inside is still a dismissal, which `click` would miss.
 *
 * The listener is on `document` in the CAPTURE phase, so a dismissal is decided
 * before any handler inside the page can stop the event. A popover that stays
 * open because something downstream called `stopPropagation` is the failure this
 * avoids.
 */
export const clickOutside: Action<HTMLElement, ClickOutsideParams> = (node, params) => {
	let current = params;

	function handle(event: PointerEvent) {
		const target = event.target;
		if (!(target instanceof Node)) return;

		if (node.contains(target)) return;
		for (const extra of current.alsoInside ?? []) {
			if (extra?.contains(target)) return;
		}

		current.onOutside();
	}

	document.addEventListener('pointerdown', handle, true);

	return {
		update(next: ClickOutsideParams) {
			current = next;
		},
		destroy() {
			document.removeEventListener('pointerdown', handle, true);
		}
	};
};
