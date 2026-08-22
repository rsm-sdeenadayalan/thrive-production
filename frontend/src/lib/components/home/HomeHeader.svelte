<script lang="ts">
	import ProgramTimelineCompact from './ProgramTimelineCompact.svelte';
	import GreetingPanel from './GreetingPanel.svelte';
	import type { DegreeProgress, ProgramTimeline, Student } from '$lib/data';
	import type { EventRowData, TaskRowData } from '$lib/homeView';

	/**
	 * Everything above the grid, in ONE panel.
	 *
	 * ## Why this component exists
	 *
	 * The program strip and the greeting were two `.thrive-panel` boxes stacked
	 * with a gap. Measured, that arrangement cost a full set of panel padding
	 * (20px) plus a stack gap (12px) to draw a boundary between two things that
	 * are the same thing: the header. Neither box was earning its edge.
	 *
	 * They are one panel now, split by a hairline. The hairline is decorative --
	 * which is exactly what the design system says a hairline is for, and the test
	 * it has to pass: remove it and the layout is still unambiguous, because the
	 * strip and the greeting do not look alike.
	 *
	 * Both children keep their own `<section>` and `aria-labelledby`. The landmark
	 * was never the panel, and collapsing the boxes must not collapse the document
	 * outline with them.
	 *
	 * `data-emphasis="strong"` moves here from the greeting: the header is one
	 * region now, so it takes one border treatment.
	 */
	let {
		student,
		degree,
		timeline,
		dateLabel,
		greeting,
		taskItems,
		eventRows
	}: {
		student: Student;
		degree: DegreeProgress;
		timeline: ProgramTimeline;
		dateLabel: string;
		greeting: string;
		taskItems: TaskRowData[];
		/** Passed through to the stat pills, which count and list this week's. */
		eventRows: EventRowData[];
	} = $props();
</script>

<div data-emphasis="strong" class="thrive-panel space-y-2 p-2.5">
	<ProgramTimelineCompact {timeline} />

	<!-- Decorative, and it passes the hairline test: take it away and the strip
	     still does not read as part of the greeting. -->
	<div class="border-t border-hairline-soft"></div>

	<GreetingPanel {student} {degree} {dateLabel} {greeting} {taskItems} {eventRows} />
</div>
