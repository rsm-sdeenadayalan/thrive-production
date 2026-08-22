<script lang="ts">
	import Check from '@lucide/svelte/icons/check';

	import { toast } from '$lib/toast.svelte';

	/**
	 * The app-wide confirmation line.
	 *
	 * ## Why this exists now, in a phase about task editing
	 *
	 * `toast.svelte.ts` was ported in Phase 3b with its tests and had **no
	 * consumer**: nothing rendered it, so `showToast` wrote to a store no one read.
	 * That was harmless while nothing called it. 6b's "copy to your to-do list" is
	 * the first caller, and it is the worst possible one to leave unrendered --
	 * the floating quick list is feature-flagged off, so the copy has no visible
	 * destination either. Without this component, pressing that button would
	 * succeed, persist, and show the student absolutely nothing. A silent no-op,
	 * from an action that worked.
	 *
	 * ## `role="status"`, and mounted always
	 *
	 * `status` rather than `alert`: copying a row is not urgent and must not
	 * interrupt what a screen reader is already saying.
	 *
	 * The region is mounted ALWAYS and only its text changes. A live region created
	 * and populated in the same tick announces unreliably -- assistive tech has to
	 * have been watching the node before the text arrives.
	 *
	 * Bottom-centre, clear of the right rail where the floating launchers will sit,
	 * and above the mobile nav bar rather than behind it. `pointer-events-none` so a
	 * confirmation can never swallow a press meant for the page under it.
	 */
	const message = $derived(toast());
</script>

<div
	role="status"
	aria-live="polite"
	class="pointer-events-none fixed inset-x-0 bottom-[calc(var(--thrive-bottomnav-height)+1rem)] z-50 flex justify-center px-3 lg:bottom-6"
>
	{#if message}
		<p class="thrive-panel animate-rise flex items-center gap-2 px-3 py-2 text-2xs text-ink">
			<Check aria-hidden="true" class="size-4 shrink-0 text-primary" />
			{message}
		</p>
	{/if}
</div>
