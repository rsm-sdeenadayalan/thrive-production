<script lang="ts">
	import AppointmentList from '$lib/components/appointments/AppointmentList.svelte';
	import BookingArea from '$lib/components/appointments/BookingArea.svelte';
	import { messages } from '$lib/messages';
	import { pageTitle } from '$lib/title';
	import type { PageData } from './$types';

	/**
	 * The Appointments page.
	 *
	 * A header, the booking area, and the student's own bookings. Everything
	 * stateful is inside `BookingArea` -- which advisor, which day, which month --
	 * for the same reason the calendar page is thin: the state that matters has one
	 * owner and every consumer of it is inside that owner's subtree.
	 *
	 * No reveal channel here. Nothing on this page has a collapsed row for
	 * something else to ask about.
	 */
	let { data }: { data: PageData } = $props();

	const copy = messages.appointments;
</script>

<svelte:head><title>{pageTitle(copy.documentTitle)}</title></svelte:head>

<!--
	`lg:space-y-4` is the density pass, 2026-08-21. Every compression in that pass
	is scoped to `lg` and above, because the complaint was about a wide screen at
	100% zoom and because below `lg` this app's vertical rhythm is load-bearing for
	touch: the phone numbers are deliberately, verifiably unchanged.
-->
<div class="mx-auto w-full max-w-page space-y-6 lg:space-y-4">
	<!--
		No `max-w-5xl` wrapper here: `max-w-5xl` (64rem) is narrower than the page
		container (`--container-page`, 80rem), so `mx-auto max-w-5xl` on the header
		alone re-centered it inside the page container -- pulling its left edge in
		from the service cards and appointment list below, which fill the full
		width. Long-line wrapping is handled by `max-w-measure` on the intro
		paragraph alone.
	-->
	<header class="w-full">
		<p class="thrive-eyebrow">{copy.eyebrow}</p>
		<h1 class="mt-1 text-3xl font-bold text-ink">{copy.title}</h1>
		<p class="mt-1.5 max-w-measure text-sm text-body">{copy.intro}</p>
	</header>

	<BookingArea services={data.services} data={data.data} todayKey={data.todayKey} />

	<section aria-labelledby={copy.list.headingId} class="space-y-3">
		<div class="flex flex-wrap items-baseline justify-between gap-3">
			<h2 id={copy.list.headingId} class="text-base font-medium text-ink">
				{copy.list.title}
			</h2>

			{#if data.appointments.length > 0}
				<p class="thrive-numeric text-2xs text-muted-ink">
					{copy.list.upcoming(data.appointments.length)}
				</p>
			{/if}
		</div>

		<AppointmentList items={data.appointments} />

		<!-- The standing promise, on the surface where a student is most likely to
		     assume otherwise. Capped: it is prose, and the page is now wide enough
		     that an uncapped sentence would run past a readable line. -->
		<p class="max-w-measure text-3xs text-muted-ink">{copy.disclaimer}</p>
	</section>
</div>
