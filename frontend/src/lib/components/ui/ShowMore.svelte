<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';

	import { messages } from '$lib/messages';

	/**
	 * The control that expands a capped card.
	 *
	 * One component so all four cards offer the same affordance with the same
	 * words. The label carries the REAL remaining count -- "show 9 more", not
	 * "show more" -- because the number is the thing that tells a student whether
	 * it is worth the click.
	 *
	 * `aria-expanded` and `aria-controls` do the non-visual half: the control says
	 * what state it is in and what it governs, so this is a disclosure rather than
	 * a button that mysteriously changes the page.
	 *
	 * State is owned by the card, not here. It deliberately does not persist -- see
	 * the note in `TasksCard`.
	 */
	let {
		hiddenCount,
		expanded,
		controls,
		onToggle
	}: {
		/** How many rows are held back. Ignored when `expanded`. */
		hiddenCount: number;
		expanded: boolean;
		/** id of the region this governs. */
		controls: string;
		onToggle: () => void;
	} = $props();
</script>

<button
	type="button"
	aria-expanded={expanded}
	aria-controls={controls}
	onclick={onToggle}
	class="inline-flex min-h-11 w-full items-center justify-center gap-1 rounded-md text-2xs font-medium text-primary transition-colors duration-(--motion-fast) ease-standard hover:bg-primary-soft lg:min-h-9"
>
	{#if expanded}
		{messages.common.showLess}
		<ChevronUp aria-hidden="true" class="size-3.5" />
	{:else}
		{messages.common.showMore(hiddenCount)}
		<ChevronDown aria-hidden="true" class="size-3.5" />
	{/if}
</button>
