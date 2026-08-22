<script lang="ts">
	import { cn } from '$lib/utils';
	import { progressTones, type ProgressTone } from '$lib/tones';

	/**
	 * A bar, and an accessible name it cannot render without.
	 *
	 * `label` is required rather than optional: a bare progressbar announces as
	 * "progress bar, 72%" with no clue what is 72% done, and every call site that
	 * could forget it did.
	 */
	const sizes = {
		sm: 'h-1',
		md: 'h-1.5',
		lg: 'h-2'
	} as const;

	let {
		value,
		label,
		valueText,
		showLabel = false,
		tone = 'primary',
		size = 'md',
		class: className
	}: {
		/** 0-100. Outside the range it clamps rather than overflowing its track. */
		value: number;
		/** Accessible name. Shown when `showLabel`, used as the aria-label either way. */
		label: string;
		/** Right-aligned value text, e.g. "72%" or "6 of 11". */
		valueText?: string;
		showLabel?: boolean;
		tone?: ProgressTone;
		size?: keyof typeof sizes;
		class?: string;
	} = $props();

	const clamped = $derived(Math.max(0, Math.min(100, Math.round(value))));
</script>

<div class={cn('w-full', className)}>
	{#if showLabel}
		<div class="mb-1.5 flex items-baseline justify-between gap-2">
			<span class="truncate text-2xs font-medium text-body">{label}</span>
			{#if valueText}
				<!-- A value, so mono. -->
				<span class="thrive-numeric shrink-0 text-2xs font-medium text-muted-ink">
					{valueText}
				</span>
			{/if}
		</div>
	{/if}

	<div
		role="progressbar"
		aria-valuenow={clamped}
		aria-valuemin={0}
		aria-valuemax={100}
		aria-label={label}
		aria-valuetext={valueText}
		class={cn('overflow-hidden rounded-pill bg-sunken', sizes[size])}
	>
		<div
			class={cn(
				'h-full rounded-pill transition-[width] duration-(--motion-slow) ease-standard',
				progressTones[tone]
			)}
			style="width: {clamped}%"
		></div>
	</div>
</div>
