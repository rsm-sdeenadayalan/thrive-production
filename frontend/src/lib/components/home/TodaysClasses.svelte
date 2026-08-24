<script lang="ts">
	import CalendarDays from '@lucide/svelte/icons/calendar-days';

	import { messages } from '$lib/messages';
	import { COLLAPSED_CLASS_ROWS } from '$lib/cardLayout';
	import { collapseList } from '$lib/collapse';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import SectionCard from '$lib/components/ui/SectionCard.svelte';
	import ShowMore from '$lib/components/ui/ShowMore.svelte';

	import type { ClassRow } from '$lib/homeView';

	/**
	 * Today's classes.
	 *
	 * Every row arrives pre-formatted: the clock time is already a string, so
	 * nothing here parses a date. The card used to carry a "Due today" list as
	 * well, which rendered the same tasks TasksCard was already showing one column
	 * over -- and the two disagreed, because ticking a task struck it through in
	 * TasksCard while this server-rendered copy went on saying it was due. Tasks
	 * live in exactly one place on Home.
	 */
	let {
		rows,
		dateLabel
	}: {
		rows: ClassRow[];
		/** Today, formatted on the server. */
		dateLabel: string;
	} = $props();

	let expanded = $state(false);
	const collapse = $derived(collapseList(rows, COLLAPSED_CLASS_ROWS, expanded));
</script>

<SectionCard
	title={messages.home.todaysClasses.title}
	description={dateLabel}
	href="/calendar"
>
	<div id="todays-classes-list">
		{#if rows.length === 0}
			<EmptyState icon={CalendarDays} message={messages.home.todaysClasses.empty} />
		{:else}
			<!-- `space-y-2` and `rounded-lg`: the same gap and radius every action
			     item on Home now uses -- see `TaskRow`, `CourseCard` and `EventRow`. -->
			<ul class="space-y-2">
				{#each collapse.visible as row (row.id)}
					<li
						class="flex items-baseline gap-2.5 rounded-lg border border-hairline bg-surface px-2.5 py-2"
					>
						<!-- A clock time is a value: mono, and tabular so the column of
						     times lines up down the card. -->
						<span class="thrive-numeric w-14 shrink-0 text-2xs text-primary">
							{row.time}
						</span>
						<span class="min-w-0 flex-1">
							<span class="block text-sm font-medium break-words text-ink">{row.title}</span>
							<span class="block truncate text-2xs font-medium text-muted-ink">
								{row.location}
							</span>
						</span>
					</li>
				{/each}
			</ul>
		{/if}
	</div>

	{#snippet footer()}
		{#if collapse.canExpand}
			<ShowMore
				hiddenCount={collapse.hiddenCount}
				expanded={collapse.isExpanded}
				controls="todays-classes-list"
				onToggle={() => (expanded = !expanded)}
			/>
		{/if}
	{/snippet}
</SectionCard>
