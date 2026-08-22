<script lang="ts">
	import Undo2 from '@lucide/svelte/icons/undo-2';

	import { messages } from '$lib/messages';

	/**
	 * The way back from a dismissal.
	 *
	 * Fixed at the top of the list rather than following the row, because the row
	 * it refers to has just disappeared and a strip anchored to a gap moves as the
	 * list reflows.
	 *
	 * Deliberately NOT a live region. The undo for a task tick is announced
	 * through the card's one `aria-live` sentence; a second region here would talk
	 * over it on a single action.
	 */
	let {
		title,
		onUndo
	}: {
		title: string;
		onUndo: () => void;
	} = $props();
</script>

<div
	class="flex flex-wrap items-center justify-between gap-2 rounded-md bg-sunken px-2.5 py-1.5 text-2xs text-body"
>
	<span class="min-w-0 truncate">{messages.home.events.ignored(title)}</span>
	<button
		type="button"
		onclick={onUndo}
		class="inline-flex min-h-11 shrink-0 items-center gap-1 rounded-sm px-1.5 font-medium text-primary transition-colors duration-(--motion-fast) ease-standard hover:bg-primary-soft lg:min-h-9"
	>
		<Undo2 aria-hidden="true" class="size-3.5" />
		{messages.common.undo}
	</button>
</div>
