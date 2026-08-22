<script lang="ts">
	import ArrowRight from '@lucide/svelte/icons/arrow-right';

	import MiniCalendar from '$lib/components/calendar/MiniCalendar.svelte';
	import { messages } from '$lib/messages';
	import type { ScheduleData } from '$lib/schedule';

	/**
	 * The student's month, beside the booking panel, and it is CLICKABLE.
	 *
	 * ## Why it stopped being read-only
	 *
	 * It shipped for one commit as a non-interactive reference — cells as `<div>`s,
	 * no focus, no hover, `aria-hidden`, and a caption saying "Nothing here is
	 * clickable". That was internally consistent and still wrong: a month grid with
	 * dots on it invites a click, and a grid that refuses one reads as broken. A
	 * caption cannot out-argue an affordance.
	 *
	 * ## What clicking does, and what it deliberately does not
	 *
	 * It moves "Your day", which sits DIRECTLY BENEATH this grid so the result of a
	 * click is in the same glance as the click. It was above until this commit, and
	 * a control below the thing it changes is how a working feature came to be
	 * reported as broken.
	 *
	 * Nothing else moves. The booking chips, the meeting type and the available
	 * times are untouched, because BOOKING and BROWSING are two different questions
	 * on this page:
	 *
	 *  - the chips ask "which day am I booking" and drive the times
	 *  - this grid asks "what does my month look like" and drives "Your day"
	 *
	 * The coupling runs one way on purpose: choosing a CHIP also moves "Your day",
	 * because seeing what a slot would collide with is the whole reason that pane
	 * exists. Choosing a day here does not move the chips, because a student
	 * looking at next Thursday has not changed their mind about booking Tuesday.
	 *
	 * ## The grid, reused rather than reimplemented
	 *
	 * `MiniCalendar`, unmodified. It already has the roving tabindex, the arrow /
	 * Home / End / PageUp / PageDown grid navigation, and the two documented
	 * client-side date formats. Writing a second keyboard grid for a second month
	 * view is exactly the fork that component's `size` and `showTodayButton` props
	 * exist to prevent.
	 *
	 * ## It pages, and the selection survives paging
	 *
	 * Read-only-and-frozen was defensible while nothing was a control. Now that the
	 * cells are, refusing to page would be incoherent: the arrow keys already walk
	 * into the next month and pull the view with them, so the chevrons would be the
	 * only way that was refused.
	 *
	 * Paging does not touch the selection — a month is a view, a day is a choice.
	 * Land on a month the selected day is not in and no cell is marked current,
	 * which `MiniCalendar` already handles by falling its tab stop back to the first
	 * day of the visible month. "Your day" keeps showing the chosen day throughout,
	 * because it reads the day rather than the month.
	 */
	let {
		data,
		todayKey,
		selectedKey,
		monthKey,
		onSelect,
		onMonthChange
	}: {
		data: ScheduleData;
		todayKey: string;
		/** The browsed day, which is what "Your day" is showing. */
		selectedKey: string;
		monthKey: string;
		onSelect: (dayKey: string) => void;
		onMonthChange: (monthKey: string) => void;
	} = $props();

	const copy = messages.appointments.monthBrowser;
</script>

<section aria-labelledby={copy.headingId} class="space-y-1.5">
	<div class="flex flex-wrap items-baseline justify-between gap-2">
		<h3 id={copy.headingId} class="text-base font-medium text-ink">{copy.title}</h3>

		<!-- Kept: this grid shows the month, the real calendar does everything else. -->
		<a
			href="/calendar"
			class="inline-flex min-h-11 items-center gap-1 rounded-sm px-1 text-3xs text-muted-ink hover:text-ink"
		>
			{copy.seeCalendar}
			<ArrowRight aria-hidden="true" class="size-3.5 shrink-0" />
		</a>
	</div>

	<!--
		One line saying what a click does, rather than the old one saying that
		nothing does. Kept now that "Your day" sits directly beneath rather than
		above: the answer is visible in the same glance, but the line also says WHICH
		pane moves, which a grid on a page with two day-shaped things on it still
		owes the reader.
	-->
	<p class="text-3xs text-muted-ink">{copy.note}</p>

	<MiniCalendar {data} {todayKey} {selectedKey} {monthKey} {onSelect} {onMonthChange} />
</section>
