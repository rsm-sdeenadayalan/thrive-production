<script lang="ts">
	import CalendarCheck from '@lucide/svelte/icons/calendar-check';

	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import Tag from '$lib/components/ui/Tag.svelte';
	import { messages } from '$lib/messages';
	import {
		categoryLabel,
		fromDayKey,
		scheduleItemsForDay,
		type ScheduleData
	} from '$lib/schedule';

	/**
	 * The student's own day, beside the advisor's availability.
	 *
	 * It exists so a slot can be judged against what it would collide with,
	 * before it is taken rather than after.
	 *
	 * ## What it shows, and the exclusion that is the point
	 *
	 * Classes and appointments only -- the things that OCCUPY an hour. An
	 * assignment due at 11:59pm does not block a 2pm meeting, and listing
	 * deadlines here would make a free afternoon look busy, which is the one thing
	 * this pane must not do.
	 *
	 * `scheduleItemsForDay` would also hand back assignments -- it is the calendar
	 * page's "commitments" set, which includes work due for its own good reason (a
	 * dot with no row beneath it reads as a bug). So the filter below is
	 * deliberate and narrower, and the copy says so on screen rather than leaving
	 * a student to wonder where their deadlines went.
	 *
	 * ## The heading formats a day key on the client
	 *
	 * The documented exception, same shape as the calendar's day heading: the grid
	 * reaches any day in the window with no round trip, so there is no finite set
	 * of days a `load` could have pre-formatted. What is formatted is a key
	 * already built from local parts by `fromDayKey`, so what varies between
	 * server and client is locale wording, never which day it is. See
	 * CONVENTIONS.md.
	 */
	let {
		data,
		dayKey,
		todayKey
	}: {
		data: ScheduleData;
		/** The day the calendar is pointing at. May be null before anything is chosen. */
		dayKey: string | null;
		todayKey: string;
	} = $props();

	const copy = messages.appointments.myDay;

	const items = $derived(
		dayKey
			? scheduleItemsForDay(data, dayKey).filter(
					(item) => item.category === 'class' || item.category === 'appointment'
				)
			: []
	);

	const heading = $derived(
		dayKey
			? fromDayKey(dayKey).toLocaleDateString('en-US', {
					weekday: 'long',
					month: 'short',
					day: 'numeric'
				})
			: ''
	);
</script>

<section aria-labelledby={copy.headingId} class="thrive-panel p-3 lg:p-2.5">
	<!--
		THE DATE IS THE PANE'S SUBJECT, not an annotation in the corner.

		It used to be `text-2xs text-muted-ink` on the far right of the heading row,
		which is how a click here could read as a no-op: classes recur weekly in this
		data, so two Mondays three weeks apart show the same title at the same time,
		and the ONLY thing that distinguished them was the smallest, faintest text on
		the panel. Move the day and the pane looked identical.

		So the day now sits under the title at body weight, in ink rather than muted,
		and it is what changes when the grid above is clicked. `aria-live` is on this
		line as well as the list, because on a day whose items happen to match the
		last one, the date is the only thing that moved and it is the thing worth
		announcing.
	-->
	<h2 id={copy.headingId} class="text-base font-medium text-ink">{copy.title}</h2>

	{#if dayKey}
		<p
			data-my-day-date
			aria-live="polite"
			class="mt-0.5 flex flex-wrap items-center gap-1.5 text-sm font-medium text-ink"
		>
			{heading}
			{#if dayKey === todayKey}
				<Tag tone="primary">{copy.todayChip}</Tag>
			{/if}
		</p>
	{/if}

	<!-- Stated, not left to be noticed. A student who knows they have three things
	     due needs to be told why none of them are here. Carries a hook so a gate
	     cannot mistake it for the date line: "the first <p> in the section" was
	     exactly how the old assertion read the wrong element. -->
	<p data-my-day-scope class="mt-1 text-3xs text-muted-ink">{copy.scope}</p>

	{#if items.length === 0}
		<EmptyState icon={CalendarCheck} message={copy.empty} class="mt-2.5" />
	{:else}
		<!--
			A live region, because the list repaints without being touched: the
			student's attention is on the calendar or the times list, and this pane
			changes underneath that. `polite`, so it waits for a gap rather than
			interrupting the day they are still choosing.
		-->
		<ul aria-live="polite" class="mt-2.5 divide-y divide-line">
			{#each items as item (item.id)}
				<li class="flex items-start gap-2.5 py-2 lg:py-1.5">
					<!-- Times are values and they line up in a column, so the numeric
					     face with tabular figures. -->
					<span class="thrive-numeric w-16 shrink-0 pt-0.5 text-2xs text-muted-ink">
						{item.timeLabel}
					</span>

					<span class="min-w-0 flex-1">
						<span class="flex flex-wrap items-center gap-1.5">
							<span class="min-w-0 text-sm font-medium break-words text-ink">{item.title}</span>
							<!-- Through `Tag`, not the `categoryTag` class map: every chip in
							     THRIVE comes from the one component, and only two categories
							     ever reach this pane. -->
							<Tag tone={item.category === 'appointment' ? 'primary' : 'neutral'}>
								{categoryLabel[item.category]}
							</Tag>
						</span>

						{#if item.detail}
							<span class="mt-0.5 block truncate text-3xs text-muted-ink">{item.detail}</span>
						{/if}
					</span>
				</li>
			{/each}
		</ul>
	{/if}
</section>
