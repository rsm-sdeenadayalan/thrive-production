<script lang="ts">
	import Tag from '$lib/components/ui/Tag.svelte';
	import type { MatchReport } from '$lib/data';
	import { competencyLabel } from '$lib/jobs';
	import { messages } from '$lib/messages';
	import { competencyTone } from '$lib/tones';

	/**
	 * A generated fit assessment against one posting.
	 *
	 * No landmark of its own: the page's `?/report` section already owns a
	 * heading and an `aria-labelledby`, and wrapping this in a second `<section>`
	 * would nest one landmark inside another naming the same content.
	 *
	 * Matched skills and gaps use the same two tones `JobResultCard` does --
	 * `neutral` for a fact, `quiet` for a gap that is not a status -- so a
	 * student reading both surfaces sees one vocabulary rather than two.
	 */
	let { report }: { report: MatchReport } = $props();

	const copy = messages.jobs.report;
</script>

<div class="space-y-3">
	<div class="flex flex-wrap items-center gap-2.5">
		<Tag tone={competencyTone[report.competency]} dot>{competencyLabel(report.competency)}</Tag>
		<span class="thrive-numeric text-lg font-semibold text-ink">{report.score}</span>
	</div>

	<p class="max-w-measure text-sm text-body">{report.verdict}</p>

	<div class="grid gap-3 sm:grid-cols-2">
		<div class="min-w-0">
			<h3 class="text-3xs font-medium text-muted-ink uppercase">{copy.matchedHeading}</h3>
			{#if report.matchedSkills.length > 0}
				<ul class="mt-1 flex flex-wrap gap-1">
					{#each report.matchedSkills as skill (skill)}
						<li><Tag tone="neutral">{skill}</Tag></li>
					{/each}
				</ul>
			{:else}
				<p class="mt-1 text-3xs text-muted-ink">—</p>
			{/if}
		</div>

		<div class="min-w-0">
			<h3 class="text-3xs font-medium text-muted-ink uppercase">{copy.gapsHeading}</h3>
			{#if report.gaps.length > 0}
				<ul class="mt-1 flex flex-wrap gap-1">
					{#each report.gaps as skill (skill)}
						<li><Tag tone="quiet">{skill}</Tag></li>
					{/each}
				</ul>
			{:else}
				<p class="mt-1 text-3xs text-muted-ink">—</p>
			{/if}
		</div>
	</div>
</div>
