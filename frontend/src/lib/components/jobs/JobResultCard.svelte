<script lang="ts">
	import Tag from '$lib/components/ui/Tag.svelte';
	import type { JobResultView } from '$lib/jobs';
	import { messages } from '$lib/messages';

	/**
	 * One search result: a posting plus how it compares to the student.
	 *
	 * ## Matched skills are a chip, missing skills are muted
	 *
	 * Not two variants of the same tag. A matched skill is a fact worth stating
	 * plainly -- `neutral`'s bordered fill, the same treatment a course code
	 * gets. A missing one is not a warning, so it does not get a status tone; it
	 * gets `quiet`, which is text with no fill at all. Two skill lists that
	 * looked identical would read as "here is everything this posting wants",
	 * losing the one distinction a student is here for.
	 *
	 * ## The score is a value, so it is its own element
	 *
	 * `null` means there is no profile to score against yet -- decided once, in
	 * `toJobResultView`, so this card never has to guess whether a number it was
	 * handed can be trusted.
	 */
	let { result }: { result: JobResultView } = $props();

	const copy = messages.jobs.card;
</script>

<article class="thrive-panel flex flex-col gap-2.5 p-3">
	<div class="flex items-start justify-between gap-2.5">
		<div class="min-w-0">
			<h3 class="text-base font-medium break-words text-ink">
				<a href={`/jobs/${result.id}`} class="hover:underline">{result.title}</a>
			</h3>
			<p class="mt-0.5 text-3xs text-muted-ink">{result.company} · {result.location}</p>
			{#if result.postedAtLabel}
				<p class="mt-0.5 text-3xs text-muted-ink">{copy.posted(result.postedAtLabel)}</p>
			{/if}
		</div>

		{#if result.score !== null}
			<div class="shrink-0 text-right">
				<p class="thrive-numeric text-lg font-semibold text-primary">{result.score}</p>
				<p class="text-3xs text-muted-ink">{copy.matchScore}</p>
			</div>
		{/if}
	</div>

	{#if result.matchedSkills.length > 0}
		<div class="min-w-0">
			<p class="text-3xs font-medium text-muted-ink uppercase">{copy.skillsHave}</p>
			<ul class="mt-1 flex flex-wrap gap-1">
				{#each result.matchedSkills as skill (skill)}
					<li><Tag tone="neutral">{skill}</Tag></li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if result.missingSkills.length > 0}
		<div class="min-w-0">
			<p class="text-3xs font-medium text-muted-ink uppercase">{copy.skillsBuild}</p>
			<ul class="mt-1 flex flex-wrap gap-1">
				{#each result.missingSkills as skill (skill)}
					<li><Tag tone="quiet">{skill}</Tag></li>
				{/each}
			</ul>
		</div>
	{/if}
</article>
