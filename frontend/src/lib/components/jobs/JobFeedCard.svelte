<script lang="ts">
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import Heart from '@lucide/svelte/icons/heart';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import Undo2 from '@lucide/svelte/icons/undo-2';
	import X from '@lucide/svelte/icons/x';

	import Button from '$lib/components/ui/Button.svelte';
	import Tag from '$lib/components/ui/Tag.svelte';
	import type { JobFeedTab } from '$lib/data';
	import { competencyLabel, ringPercent, type JobFeedEntryView } from '$lib/jobs';
	import { messages } from '$lib/messages';
	import { competencyTone } from '$lib/tones';

	import MatchRing from './MatchRing.svelte';

	/**
	 * One posting in the ranked feed.
	 *
	 * ## The ring's tone follows `scoreKind`, not a colour scale
	 *
	 * A cached report is the stronger signal, so it gets `text-primary`; the
	 * hybrid search estimate every posting starts with gets the quieter
	 * `text-muted-ink`, plus a caption saying so. Neither is a verdict on the
	 * NUMBER -- that is what the competency `Tag` (strong/good/stretch/reach) is
	 * for, and it only exists once a report has actually run.
	 *
	 * ## `tab`/`q`/`minScore` travel with the card, not read from `$page.url`
	 *
	 * Like and Dismiss are plain `POST` forms -- no `use:enhance` needed, since
	 * a full-page redirect back to `+page.server.ts`'s `load` is exactly what
	 * turns a like into a filled heart. That redirect target is built server-side
	 * by `redirectTarget`, which reads these same three values back out of each
	 * form's hidden inputs -- so the card carries them once here rather than
	 * every form re-deriving the current URL.
	 */
	let {
		entry,
		tab,
		q,
		minScore
	}: {
		entry: JobFeedEntryView;
		tab: JobFeedTab;
		q: string;
		minScore: number | undefined;
	} = $props();

	const copy = messages.jobs.feed.card;

	/** A handful of chips per side, not the whole posting's skill list. */
	const MAX_MATCHED_SKILLS = 6;
	const MAX_MISSING_SKILLS = 4;
</script>

<article class="thrive-panel flex flex-col gap-2.5 p-3">
	<div class="flex items-start justify-between gap-2.5">
		<div class="min-w-0">
			<h3 class="text-base font-medium break-words text-ink">
				<a href={`/jobs/${entry.id}`} class="hover:underline">{entry.title}</a>
			</h3>
			<p class="mt-0.5 text-3xs text-muted-ink">{entry.company} · {entry.location}</p>
			{#if entry.postedLabel}
				<p class="mt-0.5 text-3xs text-muted-ink">{copy.posted(entry.postedLabel)}</p>
			{/if}
		</div>

		{#if entry.score !== null}
			<div class="flex shrink-0 flex-col items-center gap-1 text-center">
				<MatchRing
					value={ringPercent(entry.score)}
					label={copy.ringLabel(entry.score)}
					tone={entry.scoreKind === 'report' ? 'primary' : 'muted'}
				/>
				{#if entry.scoreKind === 'report' && entry.competency}
					<Tag tone={competencyTone[entry.competency]} dot>{competencyLabel(entry.competency)}</Tag>
				{:else}
					<p class="text-3xs text-muted-ink">{copy.estimatedMatch}</p>
				{/if}
			</div>
		{/if}
	</div>

	{#if entry.matchedSkills.length > 0}
		<div class="min-w-0">
			<p class="thrive-eyebrow">{copy.skillsHave}</p>
			<ul class="mt-1 flex flex-wrap gap-1">
				{#each entry.matchedSkills.slice(0, MAX_MATCHED_SKILLS) as skill (skill)}
					<li><Tag tone="neutral">{skill}</Tag></li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if entry.missingSkills.length > 0}
		<div class="min-w-0">
			<p class="thrive-eyebrow">{copy.skillsBuild}</p>
			<ul class="mt-1 flex flex-wrap gap-1">
				{#each entry.missingSkills.slice(0, MAX_MISSING_SKILLS) as skill (skill)}
					<li><Tag tone="quiet">{skill}</Tag></li>
				{/each}
			</ul>
		</div>
	{/if}

	<div class="mt-1 flex flex-wrap items-center gap-2">
		<form method="POST" action="?/like">
			<input type="hidden" name="jobId" value={entry.id} />
			<input type="hidden" name="tab" value={tab} />
			<input type="hidden" name="q" value={q} />
			{#if minScore !== undefined}
				<input type="hidden" name="minScore" value={minScore} />
			{/if}
			<Button type="submit" variant={entry.liked ? 'primary' : 'secondary'} size="sm">
				<Heart aria-hidden="true" class="size-3.5" />
				{entry.liked ? copy.liked : copy.like}
			</Button>
		</form>

		<form method="POST" action="?/dismiss">
			<input type="hidden" name="jobId" value={entry.id} />
			<input type="hidden" name="tab" value={tab} />
			<input type="hidden" name="q" value={q} />
			{#if minScore !== undefined}
				<input type="hidden" name="minScore" value={minScore} />
			{/if}
			<Button type="submit" variant="ghost" size="sm">
				{#if entry.dismissed}
					<Undo2 aria-hidden="true" class="size-3.5" />
					{copy.restore}
				{:else}
					<X aria-hidden="true" class="size-3.5" />
					{copy.dismiss}
				{/if}
			</Button>
		</form>

		<a
			href={entry.url}
			target="_blank"
			rel="noopener noreferrer"
			class="inline-flex items-center gap-1.5 text-2xs font-medium text-primary hover:underline"
		>
			<ExternalLink aria-hidden="true" class="size-3.5" />
			{copy.apply}
			<span class="sr-only">{copy.applyTail}</span>
		</a>

		{#if entry.scoreKind === 'estimate'}
			<a
				href={`/jobs/${entry.id}`}
				class="inline-flex items-center gap-1.5 text-2xs font-medium text-muted-ink hover:text-primary hover:underline"
			>
				<Sparkles aria-hidden="true" class="size-3.5" />
				{copy.getReport}
			</a>
		{/if}
	</div>
</article>
