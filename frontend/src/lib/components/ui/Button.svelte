<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';

	import { cn } from '$lib/utils';

	/**
	 * The one button in THRIVE.
	 *
	 * Before this existed in the Next app there were 25 hand-rolled buttons across
	 * six different padding pairs, which is most of why the product felt assembled
	 * rather than designed.
	 *
	 * PORTED AT 1px, NOT 2px. The Next source draws `border-2` on every variant,
	 * left over from the bordered direction of 2026-08-12 that the 08-15 restyle
	 * reversed. Under the current direction a decorative edge is 1px and only a
	 * control boundary is 1.5px. Same correction the SideRail carries.
	 *
	 * Labels take their weight at the call site, since the type scale carries size
	 * only -- `font-medium` is set in `base` here rather than left to each variant.
	 */
	type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
	type Size = 'sm' | 'md';

	const base = [
		'inline-flex items-center justify-center gap-1.5 rounded-md border whitespace-nowrap font-medium',
		'transition-[background-color,color,border-color,opacity] duration-(--motion-fast) ease-standard',
		'disabled:cursor-not-allowed disabled:opacity-40'
	].join(' ');

	const variants: Record<Variant, string> = {
		// Solid navy inside the control-weight stroke. Used sparingly: one per
		// view, on the action that view exists for.
		primary:
			'border-line-strong bg-primary text-on-primary hover:bg-primary-hover active:bg-primary-active',
		// The workhorse. A white surface inside a visible edge, so it reads as a
		// control rather than as a patch of tint.
		secondary:
			'border-line bg-surface text-body hover:border-line-strong hover:bg-primary-soft hover:text-primary-hover',
		// Chrome. Holds the border box so it cannot jump size on hover, but draws
		// nothing until it is reached for.
		ghost: 'border-transparent text-muted-ink hover:border-line hover:bg-sunken hover:text-ink',
		// Coral is reserved, so it appears on intent rather than at rest -- a row of
		// permanently red buttons stops meaning "this destroys something".
		danger: 'border-line bg-surface text-body hover:border-urgent hover:bg-urgent-soft hover:text-urgent'
	};

	const sizes: Record<Size, string> = {
		sm: 'h-8 px-2.5 text-2xs',
		md: 'h-9 px-3.5 text-2xs'
	};

	let {
		variant = 'secondary',
		size = 'md',
		class: className,
		type = 'button',
		children,
		...rest
	}: HTMLButtonAttributes & {
		variant?: Variant;
		size?: Size;
		children: Snippet;
	} = $props();
</script>

<button {type} class={cn(base, variants[variant], sizes[size], className)} {...rest}>
	{@render children()}
</button>
