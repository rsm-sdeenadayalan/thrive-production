<script lang="ts">
	import { dayCountParts, type SquareGroup } from '$lib/calendarDay';
	import SquareGrid from '$lib/components/calendar/SquareGrid.svelte';
	import { messages } from '$lib/messages';
	import type { ScheduleItem } from '$lib/schedule';

	/**
	 * The day's summary, in the owner's reference shape.
	 *
	 *     12          4 classes · 3 tasks · 2 clubs
	 *     next up: 2:00 PM  Data Visualization
	 *     ▢▢▣ ▢▢▢▢
	 *
	 * The figure is bold sans because it is the one thing to read first.
	 *
	 * ## The two faces, and what moved
	 *
	 * The Next version set the figure, the breakdown, the fraction and the whole
	 * "next up" line in mono, on the reasoning that it was all "machine truth".
	 * Under the tightened rule only VALUES take `.thrive-numeric`: the figure, the
	 * "n of m done" fraction and the clock time. The breakdown ("4 classes") and
	 * the words "next up:" are sentences, so they take DM Sans -- which is also
	 * what stops this panel reading as a terminal.
	 *
	 * `next up:` puts indigo on the TIME, the reserved "this is where you are now"
	 * colour, and the same item is marked in the square strip so the two agree.
	 *
	 * ## What the figure counts
	 *
	 * Everything on the day, events included -- so a day can read "12" while this
	 * phase renders ten rows beneath it, because the events section is Phase 7c.
	 * The alternative was filtering events out of the count and out of the month
	 * dots, which would break "one filter, applied once" and change what the grid
	 * shows twice. Accepted deliberately; see BUGS.md.
	 */
	let {
		heading,
		isToday,
		items,
		nextUp,
		squares
	}: {
		/** Already formatted by the parent. Nothing here interprets a date. */
		heading: string;
		isToday: boolean;
		/** Every item on the day, for the figure and the breakdown. */
		items: ScheduleItem[];
		nextUp: ScheduleItem | null;
		squares: SquareGroup[];
	} = $props();

	const copy = messages.calendar.header;

	const done = $derived(items.filter((item) => item.done === true).length);
	/*
	 * `done !== undefined` rather than `isTickable`, deliberately, and it is a
	 * different question from the one `DaySection` asks.
	 *
	 * A section's fraction is the denominator of the checkboxes it renders, so it
	 * must ask whether a writable source is attached. This line is a summary of
	 * the day, where anything carrying a done state counts toward "how much of
	 * today is finished" whether or not this surface can write it.
	 */
	const tickable = $derived(items.filter((item) => item.done !== undefined).length);

	/**
	 * "4 classes · 3 tasks".
	 *
	 * The counting and the two word-forms come from `dayCountParts`, which is
	 * where they can be tested; this line only asks `messages` to turn each pair
	 * into a fragment and to join them. Splitting it there is why "1 classes" is
	 * now a test failure rather than something to spot on screen.
	 */
	const countsLine = $derived(
		copy.countsLine(
			dayCountParts(items).map((part) => copy.countPart(part.count, part.singular, part.plural))
		)
	);
</script>

<section aria-labelledby={copy.headingId} class="thrive-panel">
	<div class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
		<h2 id={copy.headingId} class="text-lg font-bold text-ink">{heading}</h2>
		{#if isToday}
			<!-- Indigo, because "today" is literally "this is where you are now".
			     A word, so no numeric treatment. -->
			<span class="rounded-xs bg-indigo px-2 py-0.5 text-3xs text-on-primary">
				{copy.todayChip}
			</span>
		{/if}
	</div>

	<!-- The figure and its breakdown, on one baseline. -->
	<div class="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
		<p class="thrive-numeric text-3xl font-bold text-ink">
			{items.length}
			<!-- A bare 40px number reads as a heading to a screen reader and as
			     nothing at all without the breakdown beside it. -->
			<span class="sr-only">{copy.dayFigureLabel(items.length)}</span>
		</p>
		<p class="text-xs text-muted-ink">
			{items.length === 0 ? copy.nothing : countsLine}
		</p>
	</div>

	{#if tickable > 0}
		<p class="thrive-numeric mt-1 text-xs text-muted-ink">
			{copy.doneOfTickable(done, tickable)}
		</p>
	{/if}

	{#if nextUp}
		<p class="mt-2 text-sm text-muted-ink">
			{copy.nextUpLabel}
			<!-- The time is a value and the reserved locator colour; the title is
			     something a person wrote. -->
			<span class="thrive-numeric text-indigo">{nextUp.timeLabel}</span>
			<span class="text-ink">{nextUp.title}</span>
		</p>
	{/if}

	<SquareGrid groups={squares} nextId={nextUp?.id} class="mt-3" />
</section>
