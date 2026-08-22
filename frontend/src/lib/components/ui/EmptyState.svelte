<script lang="ts">
	import type { Component } from 'svelte';

	import { cn } from '$lib/utils';

	/**
	 * The one empty state.
	 *
	 * Says what WOULD appear here rather than "No data", because an empty section
	 * is an invitation to act and "No data" is a shrug. Never a dashed outline --
	 * dashed borders are out repo-wide, and a 50%-alpha dash cannot hold 3:1
	 * against cream anyway.
	 */
	let {
		icon,
		message,
		class: className
	}: {
		/** A lucide icon, held as a value. Optional -- most rows do not need one. */
		icon?: Component;
		message: string;
		class?: string;
	} = $props();

	const Icon = $derived(icon);
</script>

<div
	class={cn(
		'grid place-items-center gap-1.5 rounded-lg bg-sunken px-3 py-6 text-center',
		className
	)}
>
	{#if Icon}
		<Icon aria-hidden="true" class="size-5 text-muted-ink" />
	{/if}
	<p class="max-w-xs text-xs text-muted-ink">{message}</p>
</div>
