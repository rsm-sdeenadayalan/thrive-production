<script lang="ts">
	import Eye from '@lucide/svelte/icons/eye';

	import { cn } from '$lib/utils';
	import { messages } from '$lib/messages';

	/**
	 * The way back onto a row the student dismissed.
	 *
	 * `IgnoreButton`'s inverse, and deliberately its twin down to the last
	 * utility: same height, same weight, same muted ink, no border. They occupy
	 * the same slot on the same row and swap according to one boolean, so any
	 * difference between them would read as the row jumping.
	 *
	 * ## Only the calendar has one
	 *
	 * Home is a recommendation feed, so ignoring something there is permanent by
	 * design and the only way back is "bring them back" once the feed is empty.
	 * The calendar is the record of what exists, so an ignored event can be
	 * revealed by the key's own switch — and a revealed row that could not be
	 * recovered would make that switch a one-way door.
	 */
	let {
		title,
		onUnIgnore,
		class: className
	}: {
		/** The event title, so the accessible name says which one. */
		title: string;
		onUnIgnore: () => void;
		class?: string;
	} = $props();
</script>

<button
	type="button"
	onclick={onUnIgnore}
	class={cn(
		'inline-flex min-h-11 items-center gap-1.5 rounded-md px-2 text-2xs font-medium text-muted-ink',
		'transition-colors duration-(--motion-fast) ease-standard hover:bg-sunken hover:text-body',
		className
	)}
>
	<Eye aria-hidden="true" class="size-3.5" />
	{messages.calendar.events.unIgnore}
	<span class="sr-only">{messages.common.ignoreSubject(title)}</span>
</button>
