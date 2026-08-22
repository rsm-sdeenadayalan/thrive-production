/**
 * "Show me the row behind this number", as arithmetic.
 *
 * ## What this exists for
 *
 * The stat pills on Home open a popover listing the actual items behind the
 * count, and those items jump to the row on the page. A card that has collapsed
 * behind "show more" may not be rendering that row, so something has to expand
 * it first.
 *
 * ## The direction, and why it matters
 *
 * A popover reaching into a card and setting its collapse state is the wrong
 * way round: the popover would have to know which card owns which row, how that
 * card collapses, and what its limit is. Four cards and one popover means four
 * couplings, and every one of them breaks the next time a card changes its
 * layout.
 *
 * So the popover only ever REQUESTS a reveal, and each card decides for itself
 * whether the request is about one of its own rows and whether it currently
 * needs to open. The card keeps its state; the page carries the intent. See
 * `reveal.svelte.ts` for the channel that carries it.
 *
 * This module is the pure half: no runes, no DOM, no store. `planReveal` is the
 * one question a card asks, and it is the thing worth a test -- a hidden row
 * must ask for expansion and a visible one must not, or the card either fails
 * to reveal or expands for no reason.
 */

/** Which list a target lives in. Also which card will claim the request. */
export type RevealKind = 'task' | 'event';

export interface RevealTarget {
	kind: RevealKind;
	/**
	 * The row's own id: a `Task.id`, or a raw `Event.id`.
	 *
	 * Raw, and never normalised through `eventIdOf()`. That normaliser is for
	 * calendar ITEM ids (`evt-evt-3-1`), a key space Home never touches -- see
	 * CONTEXT.md section 8 and MIGRATION.md section 9 defect 12.
	 */
	id: string;
}

/**
 * One line in a stat pill's popover.
 *
 * A view model, and every field is already a string: `detail` is a formatted due
 * line or an event's date, and `value` is a countdown or a clock time. Nothing
 * here is a timestamp, so the popover has nothing to interpret -- same rule as
 * every other view model on Home (CONVENTIONS.md).
 *
 * The item carries its own `target`, so the popover asks for a reveal without
 * knowing what kind of thing it is listing.
 */
export interface RevealItem {
	target: RevealTarget;
	/** The row's subject: a task title, an event title. */
	title: string;
	/** One line of context under the title. */
	detail: string;
	/** Optional value, set in mono. A time, a countdown -- something scanned. */
	value?: string;
}

/**
 * The DOM id of a revealable row.
 *
 * One function builds both the `id` the row renders and the target the popover
 * asks for, so the two cannot drift. Two string templates in two components is
 * how a jump silently stops landing anywhere.
 */
export function revealRowId(target: RevealTarget): string {
	return `reveal-${target.kind}-${target.id}`;
}

/**
 * What a card should do about a reveal request.
 *
 * `found: false` means the request is not about a row this card holds -- either
 * another card owns it, or the row has since left the list (an event ignored
 * while the popover was open). The card does nothing, which is deliberately
 * different from "found it, and it is already visible".
 */
export type RevealPlan =
	| { found: false }
	| {
			found: true;
			/** Position in the card's full list, for the caller that wants it. */
			index: number;
			/** True when the row sits past the collapsed slice. */
			expand: boolean;
	  };

/**
 * Decide whether a card holds the target row, and whether it must expand.
 *
 * `ids` is the card's FULL list in render order -- not the visible slice. The
 * whole question is whether the target is inside the first `limit` of it, so
 * passing the slice would make the answer always "no".
 *
 * A non-positive limit means nothing is visible collapsed (the done group's
 * arrangement), so any hit needs expanding. Mirrors `collapseList`.
 */
export function planReveal(
	ids: readonly string[],
	limit: number,
	targetId: string
): RevealPlan {
	const index = ids.indexOf(targetId);
	if (index < 0) return { found: false };

	return { found: true, index, expand: index >= Math.max(0, Math.trunc(limit)) };
}

/**
 * How many event rows Upcoming Events must render when expanded.
 *
 * The events pill counts events **this week**; the card shows the next few
 * **upcoming**. Those are two different sets, and until this function existed
 * most of what the pill counted had no row on the page to jump to: 21 events
 * this week against a card showing four.
 *
 * The fix rests on both sets being PREFIXES of the same list. `getEvents()`
 * returns upcoming events sorted ascending by start, and the ignore filter
 * preserves that order, so "the first four" and "everything within seven days"
 * are both prefixes -- and the union of two prefixes is just the longer one.
 * Expanding to `max(collapsedLimit, weekCount)` therefore contains every item
 * the pill can list, with no second list and no set arithmetic.
 *
 * The `max` is not decoration. On a quiet week -- two events in seven days, more
 * beyond -- the week count is SHORTER than the collapsed slice, and expanding to
 * it would remove rows the card already shows. Holding the floor at the
 * collapsed limit means a quiet week simply has nothing to expand, which is the
 * card's behaviour before any of this existed.
 */
export function expandedEventLimit(collapsedLimit: number, weekCount: number): number {
	return Math.max(Math.max(0, Math.trunc(collapsedLimit)), Math.max(0, Math.trunc(weekCount)));
}
