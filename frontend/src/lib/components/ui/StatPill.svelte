<script lang="ts">
	import type { Component } from 'svelte';

	import { cn } from '$lib/utils';
	import { statTones, type StatTone } from '$lib/tones';
	import StatPopover from './StatPopover.svelte';
	import type { RevealItem } from '$lib/reveal';

	/**
	 * A single number worth acting on. Three across the top of Home answer "is
	 * anything on fire" before the student reads a word.
	 *
	 * The value is mono, the label is not. That split is the two-face rule at its
	 * clearest: the number is scanned and compared against the pill beside it, the
	 * word is read once.
	 *
	 * ## Two shapes, one look
	 *
	 * Given `items`, the pill is a BUTTON that opens the list behind its number.
	 * Given none, it is the plain chip it has always been. The look is a snippet so
	 * there is one description of it -- a second component would have meant two
	 * copies of the tone plumbing drifting apart.
	 *
	 * The button has to be the outer element rather than something wrapped around
	 * the chip: a `<button>` may only contain phrasing content, so the old `<div>`
	 * and `<p>` could not sit inside one. They are `<span>`s now, which renders
	 * identically -- Tailwind's preflight had already zeroed the paragraph margin --
	 * and is legal in both branches.
	 *
	 * ## A count of zero is not a control
	 *
	 * No items means no button: no `aria-expanded`, no pointer cursor, nothing to
	 * press. A popover that opens an empty box is a dead end dressed as an
	 * affordance, and `aria-expanded="false"` on something that can never expand is
	 * simply untrue. `statTones.calm` already exists so "0 overdue" does not read as
	 * an alarm; this is the same idea applied to the interaction.
	 *
	 * The zero case cannot disagree with the list, either: the caller derives the
	 * count from the items, so the number IS the length.
	 */
	let {
		icon,
		value,
		label,
		tone = 'primary',
		items,
		onSelect,
		listLabel,
		class: className
	}: {
		icon: Component;
		value: number;
		label: string;
		tone?: StatTone;
		/** The rows behind the number. Absent or empty leaves the pill inert. */
		items?: RevealItem[];
		onSelect?: (item: RevealItem) => void;
		/** Names the popover's list for assistive tech, e.g. "3 overdue". */
		listLabel?: string;
		class?: string;
	} = $props();

	const Icon = $derived(icon);
	const styles = $derived(statTones[tone]);

	/**
	 * `min-h-11 lg:min-h-9` on BOTH branches, not just the button.
	 *
	 * The interactive pill owes 44px of touch target (WCAG 2.5.5) and 24px of
	 * pointer target (2.5.8), the same as every other control in the app. Giving it
	 * to the button alone would leave a zero-count pill visibly shorter than the two
	 * beside it, and a row of pills at two heights reads as a rendering fault
	 * rather than as one of them being inert.
	 */
	const shape = 'inline-flex min-h-11 items-center gap-2.5 rounded-md px-3 py-2 lg:min-h-9';
</script>

{#snippet chip()}
	<Icon aria-hidden="true" class={cn('size-3.5 shrink-0', styles.icon)} />
	<span class="flex items-baseline gap-1.5 text-sm leading-none">
		<span class="thrive-numeric text-base">{value}</span>
		<!-- No opacity dim: at 90% every tone lands just under AA for 13px text on
		     its own soft wash. At full strength all three clear it. -->
		<span class="text-2xs font-medium">{label}</span>
	</span>
{/snippet}

{#if items && items.length > 0 && onSelect && listLabel}
	<StatPopover
		{items}
		{onSelect}
		{listLabel}
		triggerClass={cn(shape, styles.wrap, className)}
	>
		{@render chip()}
	</StatPopover>
{:else}
	<div class={cn(shape, styles.wrap, className)}>
		{@render chip()}
	</div>
{/if}
