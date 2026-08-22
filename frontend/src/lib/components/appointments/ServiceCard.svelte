<script lang="ts">
	import MapPin from '@lucide/svelte/icons/map-pin';
	import Video from '@lucide/svelte/icons/video';

	import type { ServiceView } from '$lib/appointmentsView';
	import Avatar from '$lib/components/Avatar.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Tag from '$lib/components/ui/Tag.svelte';
	import { messages } from '$lib/messages';
	import { cn } from '$lib/utils';

	/**
	 * One advisor as a card.
	 *
	 * ## The open count is the whole reason this is not just a name
	 *
	 * A card that says only who somebody is gives a student nothing to decide
	 * with. The count is what makes it a choice: it is measured inside the booking
	 * window by the server, so it can never promise times the calendar then
	 * refuses to offer.
	 *
	 * Zero open times DISABLES the button rather than hiding it. A missing control
	 * reads as an unfinished page; a disabled one beside "No open times this
	 * month" reads as an answer.
	 */
	let {
		service,
		selected,
		onBook
	}: {
		service: ServiceView;
		selected: boolean;
		onBook: () => void;
	} = $props();

	const copy = messages.appointments.card;

	const advisor = $derived(service.advisor);

	/*
	 * The location string is the only signal of whether somebody works remotely --
	 * there is no field for it. One advisor is an office, the other is
	 * "CMC office / Zoom"; see the fixture. A substring test rather than a new
	 * provider field, because widening the type for an icon would be the tail
	 * wagging the dog.
	 */
	const remote = $derived(advisor.location.toLowerCase().includes('zoom'));
</script>

<article
	class={cn(
		'thrive-panel flex flex-col gap-2.5 p-3',
		'transition-colors duration-(--motion-fast) ease-standard',
		// The chosen service keeps the darkest STROKE rather than a tint, so "which
		// one am I booking" survives at a glance across the row.
		selected && 'border-primary'
	)}
>
	<div class="flex items-start gap-2.5">
		<Avatar name={advisor.name} src={advisor.avatar} class="size-10" />

		<div class="min-w-0">
			<Tag tone="primary">{service.serviceLabel}</Tag>
			<h2 class="mt-1 line-clamp-2 text-base font-medium break-words text-ink">
				{advisor.name}
			</h2>
			<p class="text-3xs text-muted-ink">{advisor.role}</p>
		</div>
	</div>

	{#if advisor.blurb}
		<p class="text-xs text-body">{advisor.blurb}</p>
	{/if}

	<p class="flex items-center gap-1.5 text-3xs text-muted-ink">
		{#if remote}
			<Video aria-hidden="true" class="size-3.5 shrink-0" />
		{:else}
			<MapPin aria-hidden="true" class="size-3.5 shrink-0" />
		{/if}
		{advisor.location}
	</p>

	<!-- `mt-auto` pins this band to the bottom, so two cards of different blurb
	     lengths still line their buttons up. -->
	<div class="mt-auto flex flex-wrap items-center justify-between gap-2.5">
		<p class="text-3xs text-muted-ink">
			{#if service.openCount > 0}
				<!-- A count is a value, so it takes the numeric face. Left in body ink
				     rather than tinted: the Next version put it in teal, which is
				     `on-track` and already means something else. -->
				<span class="thrive-numeric text-body">{service.openCount}</span>
				{copy.openTimesSuffix(service.openCount)}
			{:else}
				{copy.noOpenTimes}
			{/if}
		</p>

		<!-- `data-service` is a gate hook, the same shape as the month grid's
		     `data-day`. `check:layout` and `check:interaction` both have to open this
		     panel, and keying on the accessible name would tie two gates to a
		     fixture's copy. -->
		<Button
			variant="primary"
			size="sm"
			onclick={onBook}
			disabled={service.openCount === 0}
			aria-pressed={selected}
			data-service={advisor.id}
		>
			{selected ? copy.booking : copy.book}
			<span class="sr-only">{copy.bookWith(advisor.name)}</span>
		</Button>
	</div>
</article>
