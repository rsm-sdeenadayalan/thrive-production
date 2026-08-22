import { tick } from 'svelte';

import { revealRowId, type RevealTarget } from '$lib/reveal';

/**
 * Moving a student to a row. **The one way any surface does this.**
 *
 * ## The standard, and why there is one
 *
 * Home has several things that will want to say "here is the row you asked
 * about": a stat pill's popover jumping to a task (built), 6b's undo returning to
 * a task that was just ticked, and the calendar's "next up" line pointing at the
 * item it names. Each of those could hand-roll a `scrollIntoView` and each would
 * arrive slightly differently -- a different scroll block, a mark or no mark, focus
 * moved or only the viewport. Two arrival treatments on one page is worse than
 * either of them, because a student learns the cue once and then it means
 * something else.
 *
 * So arrival is a function, not a pattern. A surface that knows which row it wants
 * calls `arriveAtRow`. A surface that needs to ASK something else to do it goes
 * through the reveal channel in `reveal.svelte.ts`, which ends up here.
 *
 * ## What counts as an arrival
 *
 * Landing ON a row. Not every focus move is one, and the distinction matters
 * because the wrong things would look identical from the outside:
 *
 *  - `StatPopover` moving focus between its own items is navigation INSIDE a
 *    widget. No row is involved.
 *  - `UpcomingEvents` focusing its list container after an event is ignored is
 *    focus RECOVERY -- the row focus was on has just stopped existing, and the
 *    container is the nearest thing that still means "you were here". There is
 *    nothing to arrive at, and marking the container would say the student had
 *    been taken somewhere when they had in fact just lost their place.
 *
 * ## A plain `.ts`, deliberately
 *
 * This declares no runes. In this repo `.svelte.ts` means "this file declares
 * runes" and nothing else -- see the note in CONTEXT.md section 8 -- so putting DOM
 * code in one would be a claim that is not true. It also means a surface wanting
 * only "move the student to this row" does not have to import the reveal channel
 * to get it.
 */

/** The class `app.css` draws the arrival ring from. */
const ARRIVED = 'thrive-arrived';

/**
 * How long a row stays marked, taken from the stylesheet.
 *
 * Read rather than repeated, so the timer that removes the class and the
 * animation that fades it cannot drift apart -- and so the duration stays a
 * design-system value rather than becoming a number in a TypeScript file.
 * `check-interaction.mjs` reads the same token for the same reason.
 *
 * The fallback only fires if the token is missing or unparseable, which in
 * practice means the stylesheet did not load. Marking for a second in that case
 * is better than not marking at all: the alternative is a feature that silently
 * stops existing.
 */
function arrivalMs(): number {
	const raw = getComputedStyle(document.documentElement)
		.getPropertyValue('--thrive-arrival-duration')
		.trim();

	const value = parseFloat(raw);
	if (Number.isFinite(value) && value > 0) {
		return raw.endsWith('ms') ? value : value * 1000;
	}
	return 1000;
}

let clearMark: ReturnType<typeof setTimeout> | undefined;

/**
 * Mark a row as just-arrived-at, and unmark it a beat later.
 *
 * ## Why a mark at all
 *
 * The jump used to be focus plus a scroll, and on a page where everything is
 * already visible that is indistinguishable from nothing happening. A student
 * chose an item and concluded the click had failed. Focus is the right ACCESSIBLE
 * answer and it stays; this is the additive visual one, for the pointer user who
 * never sees a focus ring.
 *
 * ## Exactly one row at a time
 *
 * Any previous mark is cleared before this one is applied, and the pending timer
 * with it. Two rows both wearing the ring would read as two selections, and the
 * ring is not a selection -- it is an answer to the last question asked. The sweep
 * is document-wide rather than per-caller, which is what makes that true across
 * surfaces as well as within one.
 *
 * ## Why the reflow
 *
 * Arriving twice at the SAME row has to show the cue twice. Removing the class and
 * adding it again inside one task is not a change the browser ever sees, so the
 * animation would not restart. Reading `offsetWidth` between the two forces the
 * style to be recomputed, which is what makes the re-add a real transition.
 */
function markArrival(row: HTMLElement): void {
	for (const previous of document.querySelectorAll(`.${ARRIVED}`)) {
		previous.classList.remove(ARRIVED);
	}
	clearTimeout(clearMark);

	row.classList.remove(ARRIVED);
	void row.offsetWidth;
	row.classList.add(ARRIVED);

	clearMark = setTimeout(() => row.classList.remove(ARRIVED), arrivalMs());
}

/**
 * Arrive at a row: focus it, bring it into view, and say so.
 *
 * FOCUS, not scroll. Scrolling alone leaves a keyboard user exactly where they
 * were with the page moved underneath them, which is worse than not jumping at
 * all -- they have to hunt for what the call did. The row carries `tabindex="-1"`
 * so it can take focus without joining the tab order, which every arrival target
 * has to do; `revealRowId` is how the caller and the row agree on the id.
 *
 * `await tick()` because the caller has often just changed something -- expanded a
 * card, untricked a task -- and the row may not exist in the DOM until Svelte has
 * flushed that.
 *
 * `preventScroll` then an explicit `scrollIntoView({ block: 'nearest' })`: one
 * deliberate scroll instead of the browser's default centring followed by a
 * second correction. `nearest` is what keeps the movement inside a card's own
 * scroll container on desktop rather than jumping the page -- and it is also why
 * the mark is unconditional. A row that needed no scrolling gets no movement at
 * all, so the cue is the only thing that distinguishes an arrival from a dead
 * click.
 *
 * ## The missing row, and why it warns
 *
 * A student never sees an exception over a wayfinding cue, so this returns
 * without doing anything when the row is not in the DOM. But **a silent no-op is
 * the worst failure mode this app has** -- it is what made the reveal read as a
 * dead click in the first place -- and the arrival is exactly the wrong place to
 * hide one, so in development it says so.
 *
 * The realistic cause is timing. This awaits ONE `tick()`, which is enough for
 * every caller today because expanding a card is a single state write. A caller
 * whose row needs two flushes to exist -- 6b's undo moving a task between groups
 * is the candidate -- would land here, do nothing, and look identical to a
 * successful arrival at a row that was already visible. See CONVENTIONS.
 *
 * `import.meta.env.DEV` means the warning does not ship. That is deliberate and
 * it has a cost worth stating: `check:interaction` drives the production build,
 * so **the gate cannot see this branch.** It is a message to whoever is building
 * the next caller, not a covered behaviour.
 */
export async function arriveAtRow(target: RevealTarget): Promise<void> {
	await tick();

	const rowId = revealRowId(target);
	const row = document.getElementById(rowId);

	if (!row) {
		if (import.meta.env.DEV) {
			console.warn(
				`arriveAtRow: no element with id "${rowId}". The row was not in the DOM one ` +
					`tick after the request. Whatever had to change for it to exist has not ` +
					`finished, or it renders no id. Nothing was focused and nothing was marked.`
			);
		}
		return;
	}

	row.focus({ preventScroll: true });
	row.scrollIntoView({ block: 'nearest' });
	markArrival(row);
}
