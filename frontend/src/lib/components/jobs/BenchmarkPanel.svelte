<script lang="ts">
	import ProgressBar from '$lib/components/ui/ProgressBar.svelte';
	import type { RoleBenchmark } from '$lib/data';
	import { shareWidth } from '$lib/jobs';
	import { messages } from '$lib/messages';

	/**
	 * What postings for this role typically ask for, across the sample searched.
	 *
	 * Reused on both the search page (benchmarked against the top result's
	 * title) and the detail page (against the open posting's own title) -- one
	 * component, so the two cannot render the bars differently.
	 *
	 * Widths come from `shareWidth`, not from `style` math written here: a
	 * fraction becoming a percentage is arithmetic worth a name and a test, not
	 * an inline expression repeated at two call sites.
	 */
	let { benchmark }: { benchmark: RoleBenchmark } = $props();

	const copy = messages.jobs.benchmark;
</script>

<section aria-labelledby={copy.headingId} class="thrive-panel space-y-2.5 p-3">
	<div>
		<h2 id={copy.headingId} class="text-base font-medium text-ink">{copy.heading}</h2>
		<p class="text-3xs text-muted-ink">{copy.sampleSize(benchmark.sampleSize)}</p>
	</div>

	{#if benchmark.topSkills.length === 0}
		<p class="text-xs text-muted-ink">{copy.empty}</p>
	{:else}
		<ul class="space-y-2">
			{#each benchmark.topSkills as skill (skill.name)}
				<li>
					<ProgressBar
						value={skill.share * 100}
						label={skill.name}
						valueText={shareWidth(skill.share)}
						showLabel
						size="sm"
					/>
				</li>
			{/each}
		</ul>
	{/if}
</section>
