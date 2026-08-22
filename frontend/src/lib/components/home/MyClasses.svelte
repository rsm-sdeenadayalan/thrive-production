<script lang="ts">
	import { messages } from '$lib/messages';
	import { COLLAPSED_COURSE_CARDS } from '$lib/cardLayout';
	import { collapseList } from '$lib/collapse';
	import SectionCard from '$lib/components/ui/SectionCard.svelte';
	import ShowMore from '$lib/components/ui/ShowMore.svelte';
	import CourseCard from './CourseCard.svelte';
	import type { CourseRow } from '$lib/homeView';

	/**
	 * My Classes.
	 *
	 * The collapsed count is three rather than four, and that is not an oversight:
	 * a course card is roughly three task rows tall, so the same height cap holds
	 * fewer of them. One number for every card would either scroll this one at rest
	 * or leave half of Tasks' cap empty. See `$lib/cardLayout`.
	 */
	let { rows }: { rows: CourseRow[] } = $props();

	let expanded = $state(false);
	const collapse = $derived(collapseList(rows, COLLAPSED_COURSE_CARDS, expanded));
</script>

<SectionCard
	title={messages.home.myClasses.title}
	description={messages.home.myClasses.description(rows.length)}
	href="/classes"
>
	<div id="my-classes-list" class="space-y-3">
		{#each collapse.visible as row (row.course.id)}
			<CourseCard course={row.course} nextDue={row.nextDue} scheduleLabel={row.scheduleLabel} />
		{/each}
	</div>

	{#snippet footer()}
		{#if collapse.canExpand}
			<ShowMore
				hiddenCount={collapse.hiddenCount}
				expanded={collapse.isExpanded}
				controls="my-classes-list"
				onToggle={() => (expanded = !expanded)}
			/>
		{/if}
	{/snippet}
</SectionCard>
