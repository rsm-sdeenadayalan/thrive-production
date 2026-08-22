<script lang="ts">
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import Clock from '@lucide/svelte/icons/clock';

	import { cn } from '$lib/utils';
	import { messages } from '$lib/messages';
	import { nudgeTones, nudgeToneFallback } from '$lib/tones';
	import DueChip from '$lib/components/ui/DueChip.svelte';
	import ProgressBar from '$lib/components/ui/ProgressBar.svelte';
	import StatusBadge from '$lib/components/ui/StatusBadge.svelte';
	import Tag from '$lib/components/ui/Tag.svelte';
	import type { DueDescriptor } from '$lib/format';
	import type { Course } from '$lib/data';

	/**
	 * One course.
	 *
	 * The `nudge` is the whole point of the card: exactly one course this term gets
	 * a sentence telling the student where to put their attention. Four progress
	 * bars with no nudge leaves them to compare and guess.
	 */
	let {
		course,
		nextDue,
		scheduleLabel
	}: {
		course: Course;
		/** Computed server-side for `course.nextAssignment`. */
		nextDue: DueDescriptor;
		/** Pre-formatted meeting pattern, e.g. "Mon/Wed 9:30 AM". */
		scheduleLabel: string;
	} = $props();

	const nudgeStyle = $derived(
		course.nudge ? (nudgeTones[course.standing] ?? nudgeToneFallback) : undefined
	);
</script>

<article data-flush="true" class="thrive-panel flex flex-col gap-2.5 p-3">
	<div class="flex items-start justify-between gap-2">
		<div class="min-w-0">
			<Tag tone="primary">{course.code}</Tag>
			<!-- Two lines, not an ellipsis. At 320px this column is about 135px wide
			     and "Machine Learning for Business" needs 220px, so a single-line
			     truncate hid the one thing the card is named for. -->
			<h3 class="mt-1 line-clamp-2 text-base break-words text-ink">{course.title}</h3>
			<p class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-3xs text-muted-ink">
				<span class="truncate">{course.instructor}</span>
				<span aria-hidden="true">·</span>
				<span class="inline-flex items-center gap-1">
					<Clock aria-hidden="true" class="size-3" />
					{scheduleLabel}
				</span>
			</p>
		</div>

		<StatusBadge standing={course.standing} />
	</div>

	<ProgressBar
		value={course.progress}
		label={messages.home.myClasses.progressLabel(course.code)}
		valueText={`${course.progress}%`}
		tone={course.standing}
	/>

	<div class="flex flex-wrap items-center justify-between gap-1.5">
		<p class="min-w-0 text-3xs text-muted-ink">
			{messages.home.myClasses.nextPrefix}<span class="text-body">
				{course.nextAssignment.title}
			</span>
		</p>
		<DueChip due={nextDue} />
	</div>

	{#if course.nudge}
		<p
			class={cn(
				'flex items-start gap-1.5 rounded-sm border px-2 py-1.5 text-2xs',
				nudgeStyle
			)}
		>
			<CircleAlert aria-hidden="true" class="mt-px size-3.5 shrink-0" />
			{course.nudge}
		</p>
	{/if}
</article>
