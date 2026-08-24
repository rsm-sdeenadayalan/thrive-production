<script lang="ts">
	import CalendarDays from '@lucide/svelte/icons/calendar-days';

	import { messages } from '$lib/messages';
	import { VISIBLE_EVENTS } from '$lib/cardLayout';
	import { collapseList } from '$lib/collapse';
	import { clearIgnoredEvents } from '$lib/ignoredEvents';
	import { ignoreEvents } from '$lib/ignoreUndo.svelte';
	import { expandedEventLimit, planReveal } from '$lib/reveal';
	import { arriveAtRow } from '$lib/arrive';
	import { getRevealChannel } from '$lib/reveal.svelte';
	import { showToast } from '$lib/toast.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import IgnoreUndoBar from '$lib/components/ui/IgnoreUndoBar.svelte';
	import SectionCard from '$lib/components/ui/SectionCard.svelte';
	import ShowMore from '$lib/components/ui/ShowMore.svelte';
	import EventRow from './EventRow.svelte';
	import type { EventRowData } from '$lib/homeView';

	/**
	 * Home's Upcoming Events card.
	 *
	 * Reads the ignore store, so the filtering happens here rather than on the
	 * server. The dates are still classified on the server: every row arrives with
	 * its `dateBlock` already split into month, day and time strings and its
	 * `thisWeek` flag already decided, and nothing here touches a timestamp. Same
	 * arrangement as `TaskStatPills`.
	 *
	 * ## Filter FIRST, then slice. The order is the behaviour.
	 *
	 * The card shows four rows at rest. Slicing to four on the server and filtering
	 * ignored ones here would leave gaps: ignore two of the four and the card shows
	 * two rows while four more sit unseen behind them. Filtering first and slicing
	 * second is what makes the next event MOVE UP.
	 *
	 * ## Collapsed is the next four. Expanded is this week.
	 *
	 * This card had no show-more at all, on the grounds that Home shows the next
	 * four and `/events` is the rest. The stat pill popover is what changed that,
	 * and the reason is a measured contradiction rather than a preference: the pill
	 * counts events THIS WEEK -- 21 against the fixture -- while the card showed
	 * four upcoming, so seventeen of the items the popover listed had no row on this
	 * page to jump to. A list of jumps that mostly cannot jump is worse than no
	 * list.
	 *
	 * So the card's full list is now the reachable prefix: everything inside the
	 * week window, or the collapsed four, whichever is longer. `expandedEventLimit`
	 * carries that arithmetic and the argument for why one `max()` is enough -- both
	 * sets are prefixes of the same ascending list. `/events` is still the rest, and
	 * on a quiet week nothing changes at all, because there is nothing past four to
	 * expand to.
	 *
	 * The pill and the card are now two views of one set, which is the same property
	 * the client-side counting exists to protect: they cannot disagree.
	 *
	 * ## The key is a raw `Event.id`
	 *
	 * `ignoreEvents.isIgnored(event.id)` takes the id straight off the event. No
	 * prefix stripping, no `eventIdOf`. The Next version stripped an `evt-` prefix
	 * inline here, which is one of the three sites that did so while the docs
	 * claimed there was one -- and the reason Home and the calendar disagreed about
	 * what was ignored. MIGRATION.md section 9 defect 12.
	 *
	 * ## No way back, on purpose
	 *
	 * Home is a recommendation feed, so a dismissal should stick and stay out of
	 * the way. The calendar is the record of what exists, so nothing may become
	 * unreachable there. The only way back on Home is the six-second undo strip
	 * and, once nothing is left at all, the empty state.
	 */
	let { rows }: { rows: EventRowData[] } = $props();

	const reveal = getRevealChannel();

	let listEl = $state<HTMLDivElement | null>(null);
	let expanded = $state(false);

	const kept = $derived(rows.filter((entry) => !ignoreEvents.isIgnored(entry.event.id)));

	/** Counted after the ignore filter, so the limit follows what is really left. */
	const weekCount = $derived(kept.filter((entry) => entry.thisWeek).length);

	/** Everything this card is willing to render -- the reachable prefix. */
	const reachable = $derived(kept.slice(0, expandedEventLimit(VISIBLE_EVENTS, weekCount)));

	const collapse = $derived(collapseList(reachable, VISIBLE_EVENTS, expanded));

	/** See the note on the same variable in `TasksCard`. */
	let handledNonce = -1;

	/*
	 * Answer a reveal request, if it is about one of these rows.
	 *
	 * Reads `reachable` and not `collapse`: the latter depends on `expanded`, which
	 * this effect writes, and reading it would make the write re-run the effect.
	 */
	$effect(() => {
		const request = reveal.current();
		if (!request || request.nonce === handledNonce) return;
		if (request.target.kind !== 'event') return;

		const plan = planReveal(
			reachable.map((entry) => entry.event.id),
			VISIBLE_EVENTS,
			request.target.id
		);
		if (!plan.found) return;

		handledNonce = request.nonce;
		if (plan.expand) expanded = true;
		void arriveAtRow(request.target);
	});

	function onIgnore(entry: EventRowData) {
		ignoreEvents.ignore(entry.event.id, entry.event.title);
		showToast(messages.home.events.ignored(entry.event.title));

		/*
		 * Focus would otherwise be left on a button that no longer exists, which
		 * drops it to the top of the document. Move it to the list container, the
		 * nearest thing that still means "you were here".
		 */
		queueMicrotask(() => listEl?.focus());
	}

	function bringBack() {
		clearIgnoredEvents();
		showToast(messages.home.events.broughtBack);
	}
</script>

<!-- Passed to `SectionCard` only when there is something to reveal. The footer
     band draws its own rule and padding, so handing over a snippet that renders
     nothing would leave an empty ruled strip under every short list.

     It goes in the footer rather than in the body because this card SCROLLS at
     rest: a show-more inside the scroll area is unreachable exactly when it is
     wanted. See the note in `SectionCard`. -->
{#snippet showMoreFooter()}
	<ShowMore
		hiddenCount={collapse.hiddenCount}
		expanded={collapse.isExpanded}
		controls="upcoming-events-list"
		onToggle={() => (expanded = !expanded)}
	/>
{/snippet}

<SectionCard
	title={messages.home.events.title}
	description={messages.home.events.description}
	href="/events"
	footer={collapse.canExpand ? showMoreFooter : undefined}
>
	{#if rows.length === 0}
		<EmptyState icon={CalendarDays} message={messages.home.events.empty} />
	{:else if kept.length === 0}
		<p class="text-xs text-muted-ink">
			{messages.home.events.allIgnored}
			<button
				type="button"
				onclick={bringBack}
				class="min-h-11 font-medium text-primary-hover underline-offset-2 hover:underline lg:min-h-9"
			>
				{messages.home.events.bringBack}
			</button>
		</p>
	{:else}
		<div>
			{#if ignoreEvents.undo}
				<div class="mb-2">
					<IgnoreUndoBar
						title={ignoreEvents.undo.title}
						onUndo={() => ignoreEvents.applyUndo()}
					/>
				</div>
			{/if}

			<!-- tabindex -1 makes this focusable programmatically but keeps it out of
			     the tab order, which is what a focus landing spot wants.

			     `space-y-2`, not `divide-y`: each `EventRow` now carries its own
			     border, so a divider line between rows would double it up. The gap
			     is the one every other Home list of action items uses -- see
			     `TaskRow`'s and `CourseCard`'s callers. -->
			<div
				bind:this={listEl}
				id="upcoming-events-list"
				tabindex="-1"
				class="space-y-2 outline-none"
			>
				{#each collapse.visible as entry (entry.event.id)}
					<EventRow
						event={entry.event}
						dateBlock={entry.dateBlock}
						onIgnore={() => onIgnore(entry)}
					/>
				{/each}
			</div>
		</div>
	{/if}
</SectionCard>
