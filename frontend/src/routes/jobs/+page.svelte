<script lang="ts">
	import { goto } from '$app/navigation';
	import { enhance } from '$app/forms';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import Search from '@lucide/svelte/icons/search';

	import BenchmarkPanel from '$lib/components/jobs/BenchmarkPanel.svelte';
	import JobResultCard from '$lib/components/jobs/JobResultCard.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { jobsEmptyState } from '$lib/jobs';
	import { messages } from '$lib/messages';
	import { pageTitle } from '$lib/title';
	import type { PageData } from './$types';

	/**
	 * The Jobs search page.
	 *
	 * A GET form, so the query lives in the URL and the page works with no
	 * JavaScript at all. The upload form beneath the profile banner is the one
	 * mutation here, POSTing to `?/upload`.
	 *
	 * ## The result is kept local, same reasoning as `BookingPanel`
	 *
	 * Every branch of `enhance`'s callback ends in something on screen: a
	 * redirect navigates by hand (which re-runs `load`, so the banner and the
	 * score column update themselves), a `fail()` renders its message, and
	 * anything else gets the generic sentence rather than silently doing
	 * nothing -- the specific failure mode CONVENTIONS.md warns about.
	 */
	let { data }: { data: PageData } = $props();

	const copy = messages.jobs;

	const emptyState = $derived(jobsEmptyState(data.query, data.results.length));

	let uploading = $state(false);
	let uploadError = $state<string | null>(null);
</script>

<svelte:head><title>{pageTitle(copy.documentTitle)}</title></svelte:head>

<div class="mx-auto w-full max-w-page space-y-6 lg:space-y-4">
	<header class="mx-auto w-full max-w-5xl">
		<p class="thrive-eyebrow">{copy.eyebrow}</p>
		<h1 class="mt-1 text-3xl font-bold text-ink">{copy.title}</h1>
		<p class="mt-1.5 max-w-measure text-sm text-body">{copy.intro}</p>
	</header>

	<form method="GET" role="search" class="flex flex-wrap items-end gap-2.5">
		<div class="min-w-0 flex-1">
			<label for="jobs-query" class="mb-1.5 block text-2xs text-ink uppercase">
				{copy.search.label}
			</label>
			<input
				id="jobs-query"
				type="search"
				name="q"
				value={data.query}
				placeholder={copy.search.placeholder}
				class="min-h-11 w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2.5 text-sm text-ink placeholder:text-muted-ink"
			/>
		</div>
		<Button type="submit" variant="primary">
			<Search aria-hidden="true" class="size-4" />
			{copy.search.button}
		</Button>
	</form>

	{#if !data.profileAvailable}
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
							// Back to the same search, now that a resume is on file.
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
				<div class="min-w-0">
					<label for="jobs-resume" class="mb-1.5 block text-2xs text-ink uppercase">
						{copy.profileBanner.fileLabel}
					</label>
					<input
						id="jobs-resume"
						type="file"
						name="file"
						required
						class="block text-2xs text-body"
					/>
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

	{#if emptyState === 'no-query'}
		<EmptyState icon={Search} message={copy.empty.noQuery} />
	{:else if emptyState === 'no-results'}
		<EmptyState icon={Search} message={copy.empty.noResults(data.query)} />
	{:else}
		<div class="grid gap-4 lg:grid-cols-[2fr_1fr]">
			<ul aria-label={copy.title} class="space-y-3">
				{#each data.results as result (result.id)}
					<li>
						<JobResultCard {result} />
					</li>
				{/each}
			</ul>

			<BenchmarkPanel benchmark={data.benchmark} />
		</div>
	{/if}
</div>
