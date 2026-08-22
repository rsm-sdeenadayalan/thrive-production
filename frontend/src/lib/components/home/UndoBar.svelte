<script lang="ts">
	import Undo2 from '@lucide/svelte/icons/undo-2';

	import { messages } from '$lib/messages';
	import type { TaskUndo } from '$lib/userEdits.svelte';

	/**
	 * The way back from a tick.
	 *
	 * Ticking a row moves it out of its group and down into Done, which on a full
	 * list is a long way. This stays put at the TOP of the list rather than
	 * following the row, so the way back is always in the same place -- and the row
	 * it refers to has just moved, so a strip anchored to where it was would be
	 * anchored to a gap.
	 *
	 * ## Deliberately not a live region
	 *
	 * `TasksCard` already announces the change and the availability of undo in one
	 * breath, through its single `aria-live` sentence. A second region here would
	 * talk over it on a single action -- which is exactly what three regions did on
	 * the events card before it was cut to one.
	 *
	 * Same shape as `IgnoreUndoBar`, and not shared with it on purpose: that one
	 * names an event and this one names an action plus a task, and merging them
	 * would mean a component that takes either.
	 */
	let {
		undo,
		onUndo
	}: {
		undo: TaskUndo;
		onUndo: () => void;
	} = $props();

	const action = $derived(
		undo.markedDone ? messages.taskEditing.markedDone : messages.taskEditing.markedNotDone
	);
</script>

<div class="flex items-center gap-2 rounded-md border border-line bg-sunken px-2.5 py-1.5">
	<p class="min-w-0 flex-1 text-2xs text-muted-ink">
		<span class="font-medium text-body">{action}</span>
		<span aria-hidden="true"> · </span>
		<span class="break-words">{undo.task.title}</span>
	</p>

	<button
		type="button"
		onclick={onUndo}
		class="inline-flex min-h-11 shrink-0 items-center gap-1 rounded-md px-2 text-2xs font-medium text-primary transition-colors duration-(--motion-fast) ease-standard hover:bg-primary-soft lg:min-h-9"
	>
		<Undo2 aria-hidden="true" class="size-3.5" />
		{messages.common.undo}
		<span class="sr-only">{messages.taskEditing.undoSubject(action, undo.task.title)}</span>
	</button>
</div>
