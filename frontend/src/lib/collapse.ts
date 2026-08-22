/**
 * The fit-on-one-screen rule, as arithmetic.
 *
 * ## The problem this solves
 *
 * Home rendered fourteen task rows beside a card showing one class. The right
 * column was empty space, the grid's second row started below the fold, and the
 * two cards a student had not scrolled to may as well not have existed. The card
 * with the most data decided the height of the whole page.
 *
 * So every card now shows a bounded number of rows and offers the rest. The
 * point is not to hide things -- it is that four cards visible at once and one
 * click from full beats one card visible and three below the fold.
 *
 * ## Why this is a function and not a `slice` in each component
 *
 * Four cards collapse, and they have to agree on the edge cases or the page
 * reads as four different behaviours: what happens at exactly the limit, whether
 * "show 1 more" is worth a control, what the count in the label counts. Getting
 * that wrong is invisible in the common case and wrong on the boundary, which
 * is the shape of every bug worth a test.
 *
 * Pure, and takes no clock and no store -- see `collapse.spec.ts`.
 */

export interface CollapseState<T> {
	/** The rows to render right now. */
	visible: T[];
	/** How many are held back. 0 when expanded or when everything fits. */
	hiddenCount: number;
	/**
	 * Whether to render the show-more control at all.
	 *
	 * False when everything fits, so a card with three rows and a limit of four
	 * does not grow a control that would collapse nothing.
	 */
	canExpand: boolean;
	/** True when the control would currently read "show less". */
	isExpanded: boolean;
}

/**
 * Apply the collapse rule to a list.
 *
 * `limit` is the collapsed row count and comes from the design system, not from
 * a number typed into a component -- see `$lib/cardLayout`.
 *
 * A non-positive limit is treated as "show nothing collapsed", which is what the
 * done group wants: it is entirely behind its count until asked for.
 */
export function collapseList<T>(
	rows: readonly T[],
	limit: number,
	expanded: boolean
): CollapseState<T> {
	const safeLimit = Math.max(0, Math.trunc(limit));
	const overflows = rows.length > safeLimit;

	if (expanded || !overflows) {
		return {
			visible: [...rows],
			hiddenCount: 0,
			// Still expandable when it overflows -- that is what lets the control
			// say "show less" and get back to the collapsed height.
			canExpand: overflows,
			isExpanded: expanded && overflows
		};
	}

	return {
		visible: rows.slice(0, safeLimit),
		hiddenCount: rows.length - safeLimit,
		canExpand: true,
		isExpanded: false
	};
}

/**
 * Whether a group of rows should be collapsed behind its count by default.
 *
 * Done tasks are: they are the record of what is finished, not the list of what
 * to do, and on a capped card they would push the things that still need doing
 * out of view. That is the one group where the default is "show none".
 */
export function isCollapsedByDefault(group: 'done' | 'open'): boolean {
	return group === 'done';
}
