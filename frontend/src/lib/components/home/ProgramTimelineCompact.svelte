<script lang="ts">
	import { cn } from '$lib/utils';
	import { messages } from '$lib/messages';
	import { abbreviateTerm, phaseStatusWord } from '$lib/programStrip';
	import type { ProgramTimeline } from '$lib/data';

	/**
	 * The program as a strip. The full stepper lives on /degree.
	 *
	 * Read-only, and derived end to end: nothing here is stored. `percentComplete`
	 * and `expectedFinishTerm` are computed by `buildProgramTimeline` from the
	 * student's start date and track, so switching track moves both with no edit.
	 *
	 * ## Bare, not a panel
	 *
	 * This used to carry `.thrive-panel px-3 py-2.5` and sit as its own box above
	 * the greeting. It is now a band inside `HomeHeader`'s single panel, because
	 * two stacked boxes cost a set of panel padding and a stack gap -- 32px of
	 * measured height for a boundary that was not saying anything. It keeps its
	 * `<section>` and its `aria-labelledby`: the landmark was never the panel.
	 */
	let { timeline }: { timeline: ProgramTimeline } = $props();

	const current = $derived(timeline.phases.find((phase) => phase.id === timeline.currentPhaseId));
</script>

<section aria-labelledby="program-strip-heading">
	<div class="flex flex-wrap items-baseline justify-between gap-x-3">
		<!-- A <p>, not an <h2>. This strip renders above the page's <h1>, so a
		     heading here would put the document out of order for anyone navigating
		     by headings. `aria-labelledby` names the section from it either way --
		     the relationship never needed the element to be a heading.

		     The term alone, not label plus term: now that the opening phase is named
		     after its quarter, "Summer Quarter · Summer 2026" said the same thing
		     twice. -->
		<p id="program-strip-heading" class="text-2xs text-ink">
			{current ? current.term : messages.home.timeline.fallbackTerm}
			{#if current}
				<span class="font-normal text-muted-ink">{messages.home.timeline.youAreHere}</span>
			{/if}
		</p>
		<!-- The percentage is a value, so mono; the sentence around it is words.
		     Two message entries rather than one -- see the note in messages.ts. -->
		<p class="text-2xs text-muted-ink">
			<span class="thrive-numeric text-primary">
				{messages.home.timeline.progressPercent(timeline.percentComplete)}
			</span>{messages.home.timeline.progressRest(timeline.expectedFinishTerm)}
		</p>
	</div>

	<!-- Pips repeat the stepper's states in miniature, each named by the term
	     printed under it, so the row is not colour-only and does not rely on a
	     `title` tooltip that touch and keyboard could never reach.

	     Every pip is a solid fill inside a stroke. An earlier pass drew "current"
	     at 45% primary (1.96:1) and "upcoming" as a bare fill, both under the 3:1
	     a meaningful graphic has to clear -- the row of pips is the only place the
	     strip shows progress, so it cannot be a hint. Required and optional
	     upcoming phases are told apart by stroke colour, not by a dash. -->
	<ol class="mt-1 flex items-start gap-1">
		{#each timeline.phases as phase (phase.id)}
			<li
				aria-current={phase.status === 'current' ? 'step' : undefined}
				class="min-w-0 flex-1"
			>
				<span
					aria-hidden="true"
					class={cn(
						'block h-2 rounded-pill border',
						phase.status === 'complete' && 'border-line-strong bg-primary',
						phase.status === 'current' && 'border-primary bg-primary-fill',
						phase.status === 'upcoming' && !phase.optional && 'border-line-strong bg-surface',
						phase.status === 'upcoming' && phase.optional && 'border-line bg-sunken'
					)}
				></span>

				<!-- The term under the bar rather than inside it. Inside, the label
				     would sit on three different fills and would need a different
				     colour on each to stay legible. Under it, every label is on the
				     panel surface, so one contrast pair covers all six states.

				     Two spellings, swapped by CSS rather than by measuring: six full
				     terms cannot fit across a phone. `aria-hidden` on both because the
				     spoken label below already says the term in full. -->
				<span
					aria-hidden="true"
					class={cn(
						'block truncate text-center text-3xs',
						phase.status === 'current' ? 'text-ink' : 'text-muted-ink'
					)}
				>
					<span class="sm:hidden">{abbreviateTerm(phase.term)}</span>
					<span class="max-sm:hidden">{phase.term}</span>
				</span>
				<span class="sr-only">
					{messages.home.timeline.phaseStatus(
						phase.label,
						phase.term,
						phaseStatusWord[phase.status],
						phase.optional
					)}
				</span>
			</li>
		{/each}
	</ol>
</section>
