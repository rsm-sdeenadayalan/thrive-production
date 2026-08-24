<script lang="ts">
	import { enhance } from '$app/forms';
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	import BenchmarkPanel from '$lib/components/jobs/BenchmarkPanel.svelte';
	import ReportPanel from '$lib/components/jobs/ReportPanel.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Tag from '$lib/components/ui/Tag.svelte';
	import type { MatchReport } from '$lib/data';
	import { messages } from '$lib/messages';
	import { pageTitle } from '$lib/title';
	import type { PageData } from './$types';

	/**
	 * One posting: the full description, its skills, the benchmark for the
	 * role, and the report a student can generate against it.
	 *
	 * ## The report is kept local, same reasoning as `BookingPanel`
	 *
	 * `use:enhance` does not call `applyAction`: the generated report is this
	 * component's own state, and every branch of the callback -- success,
	 * `fail()`, and anything else -- ends in something on screen rather than
	 * leaving the button looking like it did nothing.
	 */
	let { data }: { data: PageData } = $props();

	const copy = messages.jobs;

	let generating = $state(false);
	let report = $state<MatchReport | null>(null);
	let reportError = $state<string | null>(null);
</script>

<svelte:head><title>{pageTitle(data.job.title)}</title></svelte:head>

<div class="mx-auto w-full max-w-page space-y-6 lg:space-y-4">
	<header class="mx-auto w-full max-w-5xl">
		<p class="thrive-eyebrow">{copy.eyebrow}</p>
		<!-- PAGE TITLE. `text-3xl font-bold`, matching every other route's h1 --
		     see the ladder note in app.css. -->
		<h1 class="mt-1 text-3xl font-bold text-ink">{data.job.title}</h1>
		<p class="mt-0.5 text-sm text-body">{data.job.company} · {data.job.location}</p>
		{#if data.job.postedAtLabel}
			<p class="mt-0.5 text-3xs text-muted-ink">{copy.card.posted(data.job.postedAtLabel)}</p>
		{/if}

		<a
			href={data.job.url}
			target="_blank"
			rel="noopener noreferrer"
			class="mt-2 inline-flex items-center gap-1.5 text-2xs font-medium text-primary hover:underline"
		>
			<ExternalLink aria-hidden="true" class="size-3.5" />
			{copy.detail.viewPosting}
			<span class="sr-only">{copy.detail.viewPostingTail}</span>
		</a>
	</header>

	<div class="grid gap-4 lg:grid-cols-[2fr_1fr]">
		<div class="min-w-0 space-y-4">
			<section aria-labelledby="jobs-detail-description" class="thrive-panel space-y-2 p-3">
				<h2 id="jobs-detail-description" class="text-base font-medium text-ink">
					{data.job.title}
				</h2>
				<p class="max-w-measure text-sm text-body">{data.job.description}</p>
			</section>

			{#if data.job.skills.length > 0}
				<section aria-labelledby="jobs-detail-skills" class="thrive-panel space-y-2 p-3">
					<h2 id="jobs-detail-skills" class="text-base font-medium text-ink">
						{copy.detail.skillsHeading}
					</h2>
					<ul class="flex flex-wrap gap-1">
						{#each data.job.skills as skill (skill)}
							<li><Tag tone="neutral">{skill}</Tag></li>
						{/each}
					</ul>
				</section>
			{/if}

			<section aria-labelledby={copy.report.headingId} class="thrive-panel space-y-3 p-3">
				<h2 id={copy.report.headingId} class="text-base font-medium text-ink">
					{copy.report.heading}
				</h2>

				<form
					method="POST"
					action="?/report"
					use:enhance={() => {
						generating = true;
						reportError = null;

						return async ({ result }) => {
							generating = false;

							if (result.type === 'success') {
								report =
									(result.data as { report?: MatchReport } | undefined)?.report ?? null;
								return;
							}

							if (result.type === 'failure') {
								reportError = String(
									(result.data as { error?: string } | undefined)?.error ?? ''
								);
								return;
							}

							// Neither a success nor a `fail()` -- must still say something.
							reportError = copy.report.unexpected;
						};
					}}
				>
					<Button type="submit" variant="primary" disabled={generating}>
						{#if generating}
							<LoaderCircle aria-hidden="true" class="size-3.5 animate-spin" />
						{/if}
						{generating ? copy.report.generating : copy.report.generate}
					</Button>
				</form>

				{#if reportError}
					<p
						role="alert"
						class="rounded-sm border border-urgent bg-urgent-soft px-2.5 py-1.5 text-2xs text-urgent"
					>
						{reportError}
					</p>
				{/if}

				{#if report}
					<ReportPanel {report} />
				{/if}
			</section>
		</div>

		<BenchmarkPanel benchmark={data.benchmark} />
	</div>
</div>
