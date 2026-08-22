import type { Action } from "svelte/action";

/**
 * Modal focus behaviour, as one action: move in, stay in, put it back.
 *
 * The third of the three dismissal/focus actions, and the same shape as
 * `escapeKey` and `clickOutside` for the same reason: THE LISTENER'S LIFETIME IS
 * THE ELEMENT'S. Put `use:focusTrap` on something inside an `{#if open}` and the
 * trap exists exactly when the thing it traps does. There is no open state to
 * keep it in step with, which is what the React version needed three
 * `useEffect`s and a ref to arrange.
 *
 * ## The three obligations of a dialog, and why they are one action
 *
 * 1. **Focus moves in on open.** Otherwise a keyboard tab starts at the top of
 *    the document and walks the whole page behind the scrim before arriving.
 * 2. **Focus is trapped while open.** Tabbing to something underneath a modal
 *    surface means operating a page you cannot see, with no way to tell you have
 *    left.
 * 3. **Focus returns to whatever opened it on close.** A student who pressed the
 *    details button on row nine and dismissed the dialog must land back on row
 *    nine, not at the top of the document.
 *
 * They are one action because they are one contract, and because (1) and (3) are
 * two halves of a single fact -- the element that had focus at mount is the
 * element that gets it back at destroy. Split across two actions, that fact
 * would live in neither.
 *
 * ## What it does NOT do
 *
 * It does not close anything, and it does not decide what a dialog is. Escape is
 * `escapeKey`, an outside press is `clickOutside`, and `aria-modal` plus the
 * scrim are markup. Each of those is a separate decision a caller can make
 * differently -- a non-dismissible dialog is a real thing -- and folding them in
 * here would make one of them un-declinable.
 *
 * It also does not make the page behind it inert. `aria-modal="true"` tells a
 * screen reader, the scrim tells a pointer, and this tells the keyboard; the
 * `inert` attribute on the rest of the document would be the fourth and would
 * mean this action reaching outside its own node, which is what makes an action
 * hard to reason about.
 */

/**
 * What can hold focus, in document order.
 *
 * Queried LIVE on every Tab rather than captured at mount, and that is
 * load-bearing rather than tidy: `ItemDetail`'s delete control replaces itself
 * with a two-button confirmation step, so the set of focusable elements changes
 * while the trap is up. A list captured at mount would hand Tab to a button that
 * no longer exists and focus would fall out of the dialog at the worst possible
 * moment.
 *
 * `:not([disabled])` because a disabled control is not a tab stop, and the
 * "add to calendar" button on an item with no instant is exactly that.
 */
const FOCUSABLE = [
	"a[href]",
	"button:not([disabled])",
	"input:not([disabled])",
	"select:not([disabled])",
	"textarea:not([disabled])",
	'[tabindex]:not([tabindex="-1"])',
].join(",");

function focusableWithin(node: HTMLElement): HTMLElement[] {
	return [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
		// `offsetParent` is null for anything `display: none`, which is how a
		// control inside a collapsed branch would otherwise become a tab stop.
		(element) => element.offsetParent !== null || element === document.activeElement,
	);
}

export interface FocusTrapParams {
	/**
	 * Where focus should land on open.
	 *
	 * A selector rather than an element, because the element does not exist yet
	 * when the action's parameters are evaluated. Defaults to the first focusable
	 * thing in the node, which is rarely what a dialog wants: `ItemDetail` sends
	 * focus to its close button, since the common case is READING and stealing
	 * focus into a text input makes Escape feel like it cancelled an edit that
	 * never started.
	 */
	initial?: string;
}

export const focusTrap: Action<HTMLElement, FocusTrapParams | undefined> = (
	node,
	params,
) => {
	/*
	 * Captured before anything is moved. `document.activeElement` at this moment
	 * is still the control that opened the dialog, because the action runs during
	 * mount and nothing has taken focus yet.
	 */
	const opener = document.activeElement;

	const target = params?.initial
		? node.querySelector<HTMLElement>(params.initial)
		: null;
	(target ?? focusableWithin(node)[0] ?? node).focus();

	function handle(event: KeyboardEvent) {
		if (event.key !== "Tab") return;

		const focusable = focusableWithin(node);
		if (focusable.length === 0) {
			// Nothing to move to, so the only correct answer is not to move.
			event.preventDefault();
			return;
		}

		const first = focusable[0];
		const last = focusable[focusable.length - 1];
		const active = document.activeElement;

		/*
		 * Wrap at the ends, and catch the case where focus is somewhere outside
		 * entirely -- which happens when the previously focused element was removed
		 * from the DOM and the browser fell back to `<body>`.
		 */
		if (!(active instanceof HTMLElement) || !node.contains(active)) {
			event.preventDefault();
			(event.shiftKey ? last : first).focus();
			return;
		}

		if (event.shiftKey && active === first) {
			event.preventDefault();
			last.focus();
		} else if (!event.shiftKey && active === last) {
			event.preventDefault();
			first.focus();
		}
	}

	// Capture phase, so a handler inside the dialog cannot swallow Tab before the
	// trap sees it. The same reasoning `clickOutside` gives for its own listener.
	document.addEventListener("keydown", handle, true);

	return {
		destroy() {
			document.removeEventListener("keydown", handle, true);

			/*
			 * Put focus back, if there is still anywhere to put it.
			 *
			 * `isConnected` is the guard that matters: deleting a custom event from
			 * inside the dialog destroys the row whose button opened it, so the opener
			 * is gone by the time this runs. Focusing a detached element throws
			 * nothing and does nothing, leaving focus on `<body>` -- so the check is
			 * what makes the failure visible rather than silent, and the caller is
			 * left to decide where focus goes instead.
			 */
			if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
		},
	};
};
