<script lang="ts">
	import { goto } from '$app/navigation';
	import { enhance } from '$app/forms';
	import Heart from '@lucide/svelte/icons/heart';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
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
	 * The Career tab: a ranked feed, not a search box.
	 *
	 * ## The empty state is only ever consulted once the tab is known empty
	 *
	 * `feedEmptyState` takes no result count -- see its doc comment in
	 * `$lib/jobs` -- so this guards on `data.results.length === 0` itself before
	 * asking which of the three dead ends applies, the same split the function's
	 * own tests draw.
	 *
	 * ## The upload result is kept local, same reasoning as `BookingPanel`
	 *
	 * Every branch of `enhance`'s callback ends in something on screen: a
	 * redirect navigates by hand (which re-runs `load`, so the resume panel, the
	 * tab counts and every card's like/dismiss state update themselves), a
	 * `fail()` renders its message, and anything else gets the generic sentence.
	 *
	 * ## The resume panel is always on screen, in one of two shapes
	 *
	 * `data.profileAvailable` used to gate the whole panel -- a student with a
	 * resume on file never saw a way to change it again. The backend now keeps
	 * only the latest upload and deletes the rest, so a replace is always cheap
	 * and safe, and the panel says so: the same `?/upload` action, a prominent
	 * banner before a resume exists and a compact row once one does.
	 */
	let { data }: { data: PageData } = $props();

	const copy = messages.jobs;
	const feedCopy = messages.jobs.feed;

	const TABS: JobFeedTab[] = ['recommended', 'liked', 'all'];

	/** A tab's link, carrying the current query and minimum score along with it. */
	function tabHref(tab: JobFeedTab): string {
		const params = new URLSearchParams();
		if (tab !== 'recommended') params.set('tab', tab);
		if (data.q.trim().length > 0) params.set('q', data.q);
		if (data.minScore !== undefined) params.set('minScore', String(data.minScore));
		const query = params.toString();
		return query ? `/jobs?${query}` : '/jobs';
	}

	const emptyState = $derived(
		data.results.length === 0 ? feedEmptyState(data.tab, data.q) : null
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

	let uploading = $state(false);
	let uploadError = $state<string | null>(null);
	/**
	 * The name of whatever's in `input.files`, since the input itself is
	 * `sr-only` behind a styled label -- see `chooseFile` below.
	 */
	let resumeFileName = $state<string | null>(null);

	function trackChosenFile(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		resumeFileName = input.files?.[0]?.name ?? null;
	}
</script>

<svelte:head><title>{pageTitle(copy.documentTitle)}</title></svelte:head>

<div class="mx-auto w-full max-w-page space-y-6 lg:space-y-4">
	<!--
		No `max-w-5xl` wrapper here: `max-w-5xl` (64rem) is narrower than the page
		container (`--container-page`, 80rem), so `mx-auto max-w-5xl` on the header
		alone re-centered it inside the page container -- pulling its left edge in
		from the search box, tab bar and job cards below, which fill the full
		width. Long-line wrapping is handled by `max-w-measure` on the intro
		paragraph alone.
	-->
	<header class="w-full">
		<p class="thrive-eyebrow">{copy.eyebrow}</p>
		<h1 class="mt-1 text-3xl font-bold text-ink">{copy.title}</h1>
		<p class="mt-1.5 max-w-measure text-sm text-body">{copy.intro}</p>
	</header>

	<form method="GET" role="search" class="flex flex-wrap items-end gap-2.5">
		<input type="hidden" name="tab" value={data.tab} />
		<div class="min-w-0 flex-1">
			<label for="jobs-query" class="thrive-eyebrow mb-1.5 block">
				{copy.search.label}
			</label>
			<input
				id="jobs-query"
				type="search"
				name="q"
				value={data.q}
				placeholder={copy.search.placeholder}
				class="min-h-11 w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2.5 text-sm text-ink placeholder:text-muted-ink"
			/>
		</div>
		<!-- `min-h-11` to match the search input beside it -- the same pairing
		     `ChatWindow`'s composer and `ItemDetail`'s export/delete row use, so a
		     button next to a full-height field is never the short one in the row. -->
		<Button type="submit" variant="primary" class="min-h-11">
			<Search aria-hidden="true" class="size-4" />
			{copy.search.button}
		</Button>
	</form>

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

	{#if data.profileAvailable}
		<!-- A resume is already on file. Compact, and upload stays reachable at
		     every visit rather than only on the first one -- the requirement this
		     panel exists for. -->
		<div data-tone="paper" class="thrive-panel flex flex-wrap items-center justify-between gap-2.5 p-2.5">
			<p class="text-2xs text-body">{copy.profileBanner.hasResume.message}</p>

			<form
				method="POST"
				action="?/upload"
				enctype="multipart/form-data"
				class="flex flex-wrap items-end gap-2.5"
				use:enhance={() => {
					uploading = true;
					uploadError = null;

					return async ({ result }) => {
						uploading = false;

						if (result.type === 'redirect') {
							// Back to the same feed, now scored against the new resume.
							await goto(result.location, { invalidateAll: true });
							return;
						}

						if (result.type === 'failure') {
							uploadError = String(
								(result.data as { error?: string } | undefined)?.error ?? ''
							);
							return;
						}

						// Neither a redirect nor a `fail()` -- must still say something.
						uploadError = copy.profileBanner.error;
					};
				}}
			>
				<input type="hidden" name="tab" value={data.tab} />
				<input type="hidden" name="q" value={data.q} />
				{#if data.minScore !== undefined}
					<input type="hidden" name="minScore" value={data.minScore} />
				{/if}
				<div class="min-w-0">
					<span class="thrive-eyebrow mb-1.5 block">
						{copy.profileBanner.hasResume.fileLabel}
					</span>
					<div class="flex flex-wrap items-center gap-2">
						<label for="jobs-resume" class={buttonClasses('secondary', 'sm', 'cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary')}>
							{copy.profileBanner.chooseFile}
						</label>
						<input
							id="jobs-resume"
							type="file"
							name="file"
							accept="application/pdf"
							required
							class="sr-only"
							onchange={trackChosenFile}
						/>
						<span class="text-2xs text-muted-ink">
							{resumeFileName ?? copy.profileBanner.noFileChosen}
						</span>
					</div>
				</div>
				<Button type="submit" variant="ghost" size="sm" disabled={uploading}>
					{#if uploading}
						<LoaderCircle aria-hidden="true" class="size-3.5 animate-spin" />
					{/if}
					{uploading ? copy.profileBanner.hasResume.uploading : copy.profileBanner.hasResume.upload}
				</Button>
			</form>

			<p class="w-full text-3xs text-muted-ink">{copy.profileBanner.hasResume.note}</p>

			{#if uploadError}
				<p
					role="alert"
					class="w-full rounded-sm border border-urgent bg-urgent-soft px-2.5 py-1.5 text-2xs text-urgent"
				>
					{uploadError}
				</p>
			{/if}
		</div>
	{:else}
		<!-- No resume yet -- the prominent banner. -->
		<div data-tone="sunken" class="thrive-panel space-y-2.5 p-3">
			<p class="text-sm text-body">{copy.profileBanner.message}</p>

			<form
				method="POST"
				action="?/upload"
				enctype="multipart/form-data"
				class="flex flex-wrap items-end gap-2.5"
				use:enhance={() => {
					uploading = true;
					uploadError = null;

					return async ({ result }) => {
						uploading = false;

						if (result.type === 'redirect') {
							// Back to the same feed, now that a resume is on file.
							await goto(result.location, { invalidateAll: true });
							return;
						}

						if (result.type === 'failure') {
							uploadError = String(
								(result.data as { error?: string } | undefined)?.error ?? ''
							);
							return;
						}

						// Neither a redirect nor a `fail()` -- must still say something.
						uploadError = copy.profileBanner.error;
					};
				}}
			>
				<input type="hidden" name="tab" value={data.tab} />
				<input type="hidden" name="q" value={data.q} />
				{#if data.minScore !== undefined}
					<input type="hidden" name="minScore" value={data.minScore} />
				{/if}
				<div class="min-w-0">
					<span class="thrive-eyebrow mb-1.5 block">
						{copy.profileBanner.fileLabel}
					</span>
					<div class="flex flex-wrap items-center gap-2">
						<label for="jobs-resume" class={buttonClasses('secondary', 'md', 'cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary')}>
							{copy.profileBanner.chooseFile}
						</label>
						<input
							id="jobs-resume"
							type="file"
							name="file"
							accept="application/pdf"
							required
							class="sr-only"
							onchange={trackChosenFile}
						/>
						<span class="text-2xs text-muted-ink">
							{resumeFileName ?? copy.profileBanner.noFileChosen}
						</span>
					</div>
				</div>
				<Button type="submit" variant="secondary" disabled={uploading}>
					{#if uploading}
						<LoaderCircle aria-hidden="true" class="size-3.5 animate-spin" />
					{/if}
					{uploading ? copy.profileBanner.uploading : copy.profileBanner.upload}
				</Button>
			</form>

			{#if uploadError}
				<p
					role="alert"
					class="rounded-sm border border-urgent bg-urgent-soft px-2.5 py-1.5 text-2xs text-urgent"
				>
					{uploadError}
				</p>
			{/if}
		</div>
	{/if}

	{#if emptyState === 'no-jobs-at-all'}
		<EmptyState icon={Search} message={feedCopy.empty.noJobsAtAll} />
	{:else if emptyState === 'no-matches-for-query'}
		<EmptyState icon={Search} message={feedCopy.empty.noMatchesForQuery(data.q)} />
	{:else if emptyState === 'liked-tab-empty'}
		<EmptyState icon={Heart} message={feedCopy.empty.likedTabEmpty} />
	{:else}
		<!--
			`items-start`, not the grid default `stretch`: with a benchmark this
			panel is almost always shorter than the results list, and stretching it
			to match left a card with a wall of blank space below its last skill bar.

			Without one, `showBenchmark` drops the second column's track entirely
			(rather than leaving it an empty `1fr`) so the list takes the full
			width instead of sitting narrower than the page for no reason.
		-->
		<div class={cn('grid items-start gap-4', showBenchmark && 'lg:grid-cols-[2fr_1fr]')}>
			<ul aria-label={copy.title} class="space-y-3">
				{#each data.results as entry (entry.id)}
					<li>
						<JobFeedCard {entry} tab={data.tab} q={data.q} minScore={data.minScore} />
					</li>
				{/each}
			</ul>

			{#if showBenchmark && data.benchmark}
				<BenchmarkPanel benchmark={data.benchmark} />
			{/if}
		</div>
	{/if}
</div>
