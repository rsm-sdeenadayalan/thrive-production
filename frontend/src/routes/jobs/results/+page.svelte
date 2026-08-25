<script lang="ts">
	import Heart from '@lucide/svelte/icons/heart';
	import Search from '@lucide/svelte/icons/search';

	import BenchmarkPanel from '$lib/components/jobs/BenchmarkPanel.svelte';
	import JobFeedCard from '$lib/components/jobs/JobFeedCard.svelte';
	import Button, { buttonClasses } from '$lib/components/ui/Button.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import type { JobFeedTab } from '$lib/data';
	import { feedEmptyState } from '$lib/jobs';
	import { messages } from '$lib/messages';
	import { pageTitle } from '$lib/title';
	import { cn } from '$lib/utils';
	import type { PageData } from './$types';

	/**
	 * The Career tab, step 2: the ranked, heavily-limited list.
	 *
	 * ## Recommended is short on purpose
	 *
	 * `data.results` on the Recommended tab is already `targetResults`'s
	 * output -- capped to the top 10, floor-filtered below 45 -- computed once
	 * in `+page.server.ts` rather than here, so this template never has to
	 * reason about the arithmetic, only about what to say when it leaves 0, 1
	 * or 2 postings on screen. Liked and All get no such treatment: `data.results`
	 * there is exactly what `getJobFeed` returned.
	 *
	 * ## Three empty-ish states, not one
	 *
	 * `feedEmptyState` (unchanged from the single-page version) still covers
	 * "nothing matched the search at all" -- the same dead end on every tab.
	 * `showBelowBar` and `showThin` are new and Recommended-only: a search that
	 * matched postings but left none (or almost none) worth prepping an
	 * interview for is a DIFFERENT dead end from "no postings matched," and
	 * conflating them would tell a student to "try different words" when the
	 * honest advice is "broaden your search or upload a resume."
	 */
	let { data }: { data: PageData } = $props();

	const copy = messages.jobs;
	const feedCopy = messages.jobs.feed;
	const resultsCopy = messages.jobs.results;

	const TABS: JobFeedTab[] = ['recommended', 'liked', 'all'];

	/** A tab's link, carrying the current query and minimum score along with it. */
	function tabHref(tab: JobFeedTab): string {
		const params = new URLSearchParams();
		if (tab !== 'recommended') params.set('tab', tab);
		if (data.q.trim().length > 0) params.set('q', data.q);
		if (data.minScore !== undefined) params.set('minScore', String(data.minScore));
		const query = params.toString();
		return query ? `/jobs/results?${query}` : '/jobs/results';
	}

	/** Postings matched, but none cleared the interview-worthy bar. */
	const showBelowBar = $derived(
		data.tab === 'recommended' &&
			data.rawRecommendedCount !== null &&
			data.rawRecommendedCount > 0 &&
			data.targetedCount === 0
	);

	/** 1-2 postings cleared the bar -- shown, but flagged as thin rather than presented as a full list. */
	const showThin = $derived(
		data.tab === 'recommended' &&
			data.targetedCount !== null &&
			data.targetedCount > 0 &&
			data.targetedCount <= 2
	);

	const emptyState = $derived(
		!showBelowBar && data.results.length === 0 ? feedEmptyState(data.tab, data.q) : null
	);

	/**
	 * Whether the benchmark rides along beside the list.
	 *
	 * Named rather than repeated: the same condition decides whether the grid
	 * gets a second column at all, so the list can span the full width when
	 * there is nothing to share it with instead of sitting in a fixed `2fr`
	 * track with dead space where the panel would have gone.
	 */
	const showBenchmark = $derived(data.q.trim().length > 0 && Boolean(data.benchmark));
</script>

<svelte:head><title>{pageTitle(resultsCopy.documentTitle)}</title></svelte:head>

<div class="mx-auto w-full max-w-page space-y-6 lg:space-y-4">
	<!-- No `max-w-5xl` wrapper -- see the note on the same header in `/jobs`. -->
	<header class="flex w-full flex-wrap items-start justify-between gap-3">
		<div class="min-w-0">
			<p class="thrive-eyebrow">{resultsCopy.eyebrow}</p>
			<h1 class="mt-1 text-3xl font-bold text-ink">{resultsCopy.headings[data.tab](data.q)}</h1>
			{#if data.tab === 'recommended' && data.targetedCount !== null && data.targetedCount > 0}
				<p class="mt-1.5 text-sm text-body">{resultsCopy.count(data.targetedCount)}</p>
			{/if}
		</div>
		<a href="/jobs" class="shrink-0 text-2xs font-medium text-primary hover:underline">
			{resultsCopy.backToSetup}
		</a>
	</header>

	<!-- Refine, inline -- a student adjusting a query stays on this page rather
	     than bouncing back through step 1 to search again. -->
	<form method="GET" role="search" class="flex flex-wrap items-end gap-2.5">
		<input type="hidden" name="tab" value={data.tab} />
		{#if data.minScore !== undefined}
			<input type="hidden" name="minScore" value={data.minScore} />
		{/if}
		<div class="min-w-0 max-w-sm flex-1">
			<label for="jobs-results-q" class="thrive-eyebrow mb-1.5 block">
				{resultsCopy.refineLabel}
			</label>
			<input
				id="jobs-results-q"
				type="search"
				name="q"
				value={data.q}
				placeholder={resultsCopy.refinePlaceholder}
				class="min-h-11 w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2.5 text-sm text-ink placeholder:text-muted-ink"
			/>
		</div>
		<Button type="submit" variant="secondary" class="min-h-11">
			<Search aria-hidden="true" class="size-4" />
			{resultsCopy.refineButton}
		</Button>
	</form>

	<div>
		<nav aria-label={feedCopy.tabsLabel} class="flex flex-wrap gap-1.5">
			{#each TABS as tab (tab)}
				<a
					href={tabHref(tab)}
					aria-current={data.tab === tab ? 'page' : undefined}
					class={cn(
						'rounded-sm px-2.5 py-1.5 text-2xs font-medium',
						data.tab === tab
							? 'bg-primary text-on-primary'
							: 'text-body hover:bg-sunken hover:text-ink'
					)}
				>
					{feedCopy.tabs[tab](data.counts[tab])}
				</a>
			{/each}
		</nav>
		<p class="mt-1.5 text-3xs text-muted-ink">{resultsCopy.tabHints[data.tab]}</p>
	</div>

	{#if !data.profileAvailable}
		<!-- Upload lives on `/jobs`, not here -- this is a pointer back, not a
		     second copy of the form. -->
		<div data-tone="sunken" class="thrive-panel flex flex-wrap items-center justify-between gap-2.5 p-2.5">
			<p class="text-2xs text-body">{copy.profileBanner.message}</p>
			<a href="/jobs" class={buttonClasses('secondary', 'sm')}>{resultsCopy.backToSetup}</a>
		</div>
	{/if}

	{#if emptyState === 'no-jobs-at-all'}
		<EmptyState icon={Search} message={feedCopy.empty.noJobsAtAll} />
	{:else if emptyState === 'no-matches-for-query'}
		<EmptyState icon={Search} message={feedCopy.empty.noMatchesForQuery(data.q)} />
	{:else if emptyState === 'liked-tab-empty'}
		<EmptyState icon={Heart} message={feedCopy.empty.likedTabEmpty} />
	{:else if showBelowBar}
		<EmptyState icon={Search} message={feedCopy.empty.belowBar(data.q)} />
	{:else}
		<div class={cn('grid items-start gap-4', showBenchmark && 'lg:grid-cols-[2fr_1fr]')}>
			<div class="min-w-0 space-y-3">
				{#if showThin}
					<p
						class="rounded-sm border border-line-strong bg-sunken px-2.5 py-1.5 text-2xs text-body"
					>
						{feedCopy.thin(data.q)}
					</p>
				{/if}

				<ul aria-label={resultsCopy.headings[data.tab](data.q)} class="space-y-3">
					{#each data.results as entry (entry.id)}
						<li>
							<JobFeedCard {entry} tab={data.tab} q={data.q} minScore={data.minScore} />
						</li>
					{/each}
				</ul>
			</div>

			{#if showBenchmark && data.benchmark}
				<BenchmarkPanel benchmark={data.benchmark} />
			{/if}
		</div>
	{/if}
</div>
