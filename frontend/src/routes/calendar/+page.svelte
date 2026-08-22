<script lang="ts">
	import CalendarView from '$lib/components/calendar/CalendarView.svelte';
	import { messages } from '$lib/messages';
	import { pageTitle } from '$lib/title';
	import type { PageData } from './$types';

	/**
	 * The Calendar page.
	 *
	 * A header and one component. Everything else -- the month grid, the selected
	 * day, the day's sections -- hangs off `CalendarView`, which is the only
	 * stateful node on the page.
	 *
	 * ## Why the page is this thin
	 *
	 * The state that matters here is `selectedKey`, and every view reads and writes
	 * it. Hoisting it to the page would put it above the only consumer and buy
	 * nothing; splitting it between page and view would let a month grid and a day
	 * panel disagree about which day is selected. So it lives in exactly one place
	 * and the page is a header plus a mount point.
	 *
	 * Note what is NOT here: no reveal channel. Home needs one because its stat
	 * pills have to ask a card it cannot see into to open a collapsed row. The
	 * calendar has no collapsed rows and nothing asking about them -- and if the
	 * "next up" line ever becomes a jump, that is `arriveAtRow` on a row this
	 * subtree already owns, not a channel. See CONVENTIONS.md on asking versus
	 * doing.
	 *
	 * ## This h1 already had its weight
	 *
	 * It is the ONE page title in the Next app carrying `font-bold` -- MIGRATION.md
	 * section 9 defect 4: the other twelve render at 400. Every heading in this
	 * port sets its weight at the call site.
	 */
	let { data }: { data: PageData } = $props();

	const copy = messages.calendar;
</script>

<svelte:head><title>{pageTitle(copy.documentTitle)}</title></svelte:head>

<!--
	`max-w-page`, the same measure every other route uses.

	It was `max-w-wide` (96rem) on the reasoning that the month grid, the week
	columns and the agenda all take whatever width they are given. True, and it was
	the wrong way to give it to them: at 1920 the calendar sat in a 127px gutter
	while every other route had 248px, which reads as cramped rather than generous.

	The width the grid lost here is taken back from the CHROME instead — one header
	row rather than three pieces of furniture, and the Key behind a disclosure
	rather than permanently holding a third of the page. See `CalendarView`.
-->
<div class="mx-auto w-full max-w-page space-y-3">
	<CalendarView
		data={data.data}
		tasks={data.tasks}
		todayKey={data.todayKey}
		nowMinutes={data.nowMinutes}
	/>
</div>
