<script lang="ts">
	import { goto } from '$app/navigation';
	import { enhance } from '$app/forms';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import Search from '@lucide/svelte/icons/search';

	import Button, { buttonClasses } from '$lib/components/ui/Button.svelte';
	import { messages } from '$lib/messages';
	import { pageTitle } from '$lib/title';
	import type { PageData } from './$types';

	/**
	 * The Career tab, step 1: a focused setup page, not a feed.
	 *
	 * ## Why the ranked list is not here
	 *
	 * A student optimizing for interview conversions is not well served by a
	 * page that hands them fifty postings before they have said what they are
	 * looking for. This page asks exactly one question -- what role? -- and the
	 * search form below hands off to `/jobs/results`, which is the only place
	 * the ranked, capped, floor-filtered list exists. See `targetResults` in
	 * `$lib/jobs` for the arithmetic behind "capped, floor-filtered."
	 *
	 * ## Searching works with no resume on file
	 *
	 * The resume panel is not a gate in front of the search form -- a student
	 * can search before uploading anything, and `/jobs/results` will show
	 * postings with no score attached rather than refusing to show anything.
	 * The panel stays on screen regardless, in whichever of its two shapes
	 * applies, because a score-free result list is exactly the moment a resume
	 * upload matters most.
	 *
	 * ## The resume panel itself is untouched
	 *
	 * Same markup, same copy, same `?/upload` action as the single-page version
	 * this replaced -- only `tab`/`q`/`minScore` hidden inputs are gone, because
	 * this page carries none of those anymore.
	 */
	let { data }: { data: PageData } = $props();

	const copy = messages.jobs;
	const setup = messages.jobs.setup;

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

	/** A quick-pick chip's link -- straight to the results this page exists to lead to. */
	function roleHref(role: string): string {
		return `/jobs/results?q=${encodeURIComponent(role)}`;
	}
</script>

<svelte:head><title>{pageTitle(copy.documentTitle)}</title></svelte:head>

<div class="mx-auto w-full max-w-page space-y-6 lg:space-y-4">
	<!--
		No `max-w-5xl` wrapper here: `max-w-5xl` (64rem) is narrower than the page
		container (`--container-page`, 80rem), so `mx-auto max-w-5xl` on the header
		alone re-centered it inside the page container -- pulling its left edge in
		from the cards below it, which fill the full width. Long-line wrapping is
		handled by `max-w-measure` on the intro paragraph alone.
	-->
	<header class="w-full">
		<p class="thrive-eyebrow">{copy.eyebrow}</p>
		<h1 class="mt-1 text-3xl font-bold text-ink">{copy.title}</h1>
		<p class="mt-1.5 max-w-measure text-sm text-body">{copy.intro}</p>
	</header>

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
		<!-- No resume yet -- the prominent banner. Searching still works without
		     one; this stays visible so upload is never more than a scroll away. -->
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

	<!--
		The page's one real question. `thrive-panel` rather than a bare form so it
		reads as the page's focal point next to the resume panel above it, not as
		a stray control floating on the page background.
	-->
	<section class="thrive-panel space-y-3 p-4">
		<form method="GET" action="/jobs/results" class="flex flex-wrap items-end gap-2.5">
			<div class="min-w-0 flex-1">
				<label for="jobs-role" class="thrive-eyebrow mb-1.5 block">
					{setup.roleLabel}
				</label>
				<input
					id="jobs-role"
					type="search"
					name="q"
					placeholder={setup.rolePlaceholder}
					class="min-h-11 w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2.5 text-sm text-ink placeholder:text-muted-ink"
				/>
			</div>
			<!-- `min-h-11` to match the search input beside it, the same pairing
			     `ChatWindow`'s composer and `ItemDetail`'s export/delete row use. -->
			<Button type="submit" variant="primary" class="min-h-11">
				<Search aria-hidden="true" class="size-4" />
				{setup.roleButton}
			</Button>
		</form>
		<p class="text-3xs text-muted-ink">{setup.searchHint}</p>

		<div>
			<p class="thrive-eyebrow mb-1.5">{setup.quickPicksLabel}</p>
			<ul class="flex flex-wrap gap-1.5">
				{#each setup.quickPicks as role (role)}
					<li>
						<a href={roleHref(role)} class={buttonClasses('secondary', 'sm')}>{role}</a>
					</li>
				{/each}
			</ul>
		</div>

		<a href="/jobs/results?tab=liked" class="inline-block text-2xs font-medium text-primary hover:underline">
			{setup.likedLink}
		</a>
	</section>
</div>
