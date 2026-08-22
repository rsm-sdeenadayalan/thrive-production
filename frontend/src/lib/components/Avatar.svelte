<script lang="ts">
	import { initialsOf } from '$lib/format';
	import { cn } from '$lib/utils';

	/**
	 * Identity mark: an image if there is one, initials if there is not.
	 *
	 * Hand-rolled rather than pulled from shadcn-svelte, which is a later phase.
	 * What Radix's Avatar contributed was one behaviour -- swap to the fallback
	 * when the image is absent OR fails to load -- and that is the `failed` flag
	 * below. Everything else it did was layout this does directly.
	 *
	 * When shadcn-svelte lands, this is a candidate for deletion. The reason it
	 * might survive is that the fallback here is `initialsOf`, which has its own
	 * rule: a single name yields one letter, because "Merna" as "ME" reads as the
	 * word "me" in a circle rather than as initials.
	 */
	let {
		name,
		src,
		class: className
	}: { name: string; src?: string; class?: string } = $props();

	let failed = $state(false);
</script>

<span
	class={cn(
		'relative grid shrink-0 place-items-center overflow-hidden rounded-pill border border-line bg-primary-soft text-2xs font-medium text-primary',
		className
	)}
>
	{#if src && !failed}
		<img {src} alt="" class="size-full object-cover" onerror={() => (failed = true)} />
	{:else}
		{initialsOf(name)}
	{/if}
</span>
