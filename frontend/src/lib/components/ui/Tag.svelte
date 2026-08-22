<script lang="ts">
	import type { Snippet } from 'svelte';

	import { cn } from '$lib/utils';
	import { tagTones, type TagTone } from '$lib/tones';

	/**
	 * The one tag in THRIVE.
	 *
	 * Status chips, due chips, course codes, event origins and task labels all
	 * render through this, so a "Career" tag looks the same wherever it lands and
	 * nothing reads one-off.
	 *
	 * Loud by construction: a solid fill in the status hue with white text. An
	 * earlier tint-on-tint version put several tones between 3.9:1 and 4.2:1 --
	 * under AA for label-sized text. Every solid pairing is measured in the
	 * contrast gate.
	 *
	 * The tone-to-class map is in `$lib/tones`, not here: it is shared with
	 * components that are not this one, and a `Record<TagTone, string>` makes a
	 * missing tone a compile error.
	 */
	let {
		tone = 'neutral',
		dot = false,
		class: className,
		children
	}: {
		tone?: TagTone;
		/**
		 * A filled dot before the label. Use on anything whose meaning is carried
		 * by hue, so the state survives grayscale and colour blindness.
		 */
		dot?: boolean;
		class?: string;
		children: Snippet;
	} = $props();
</script>

<span
	class={cn(
		'inline-flex shrink-0 items-center gap-1 rounded-sm text-2xs font-medium whitespace-nowrap',
		tone === 'quiet' ? 'px-0' : 'px-1.5 py-0.5',
		tagTones[tone],
		className
	)}
>
	{#if dot}
		<span aria-hidden="true" class="size-1 shrink-0 rounded-pill bg-current"></span>
	{/if}
	{@render children()}
</span>
