<script lang="ts">
	import { onDestroy } from 'svelte';

	import { messages } from '$lib/messages';

	/**
	 * The self-notes panel for one task.
	 *
	 * ## The draft is local, and committed on blur and on close
	 *
	 * Never per keystroke. `setNote` writes to `localStorage` and to a `$state`
	 * map that every mounted row reads, so writing through on each character
	 * would re-derive the whole list to show a letter the student can already see
	 * in the field in front of them.
	 *
	 * Three things commit, and the third is the one that matters:
	 *
	 *  1. `onblur` -- the ordinary case, focus leaving the field.
	 *  2. Closing the panel -- Escape or the note button. The CLOSE path commits;
	 *     Escape here does not discard, which is a deliberate difference from the
	 *     title editor. A note is prose someone wrote and losing it to a stray key
	 *     is not a recoverable mistake; a title has an original to restore to.
	 *  3. `onDestroy` -- the panel going away without a blur. Ticking a task
	 *     elsewhere regroups this row and can unmount the panel mid-sentence, and
	 *     without this the note would be gone with no action the student took.
	 *
	 * `onDestroy` rather than an `$effect` teardown, on purpose: an effect that
	 * reads the draft would re-run on every keystroke and commit on each one,
	 * which is the behaviour this component exists to avoid. `onDestroy` is not
	 * reactive at all, which is exactly the React unmount effect this replaces.
	 *
	 * ## The autofocus, and the media query behind it
	 *
	 * Opening the panel is an explicit request to write, so focus lands in the
	 * field -- but only where a keyboard will not cover the screen. On a phone
	 * autofocus throws the keyboard over half the card, and the note button sits
	 * right in a thumb's resting arc, so the mis-tap cost is real.
	 *
	 * **This is the THIRD sanctioned client-side media read** (CONVENTIONS.md), and
	 * it is not the `hoverIntent` that was deleted. That one gated hover-to-reveal,
	 * which is CSS and needs no JavaScript opinion. This decides whether to move
	 * FOCUS, and no media query can do that -- there is no CSS form of it to prefer.
	 */
	let {
		taskId,
		taskTitle,
		note,
		onSave,
		onClose
	}: {
		taskId: string;
		taskTitle: string;
		note: string;
		onSave: (note: string) => void;
		onClose: () => void;
	} = $props();

	/* Seeded once, on purpose. The panel lives inside its row's `{#if noteOpen}`, so
	   it is mounted fresh every time it opens and re-seeds from the stored note
	   then. Tracking `note` here would instead overwrite what the student is
	   currently typing the moment any other row wrote to the store. */
	// svelte-ignore state_referenced_locally
	let draft = $state(note);
	let field: HTMLTextAreaElement | undefined = $state();

	$effect(() => {
		if (!field) return;
		if (window.matchMedia('(hover: hover)').matches) field.focus();
	});

	onDestroy(() => onSave(draft));
</script>

<!-- `pl-9` indents the panel to the title's left edge, past the checkbox, so the
     note reads as belonging to the row rather than to the list. -->
<div class="px-2.5 pb-2.5 pl-9">
	<label for={`note-${taskId}`} class="sr-only">
		{messages.taskEditing.noteLabel(taskTitle)}
	</label>
	<textarea
		bind:this={field}
		bind:value={draft}
		id={`note-${taskId}`}
		onblur={() => onSave(draft)}
		onkeydown={(event) => {
			if (event.key === 'Escape') {
				// Stop the row's own dismissal handling from also seeing it, and let
				// the close path commit rather than discarding.
				event.stopPropagation();
				onClose();
			}
		}}
		rows={2}
		placeholder={messages.taskEditing.notePlaceholder}
		class="w-full resize-y rounded-md border-[1.5px] border-line-strong bg-surface px-2.5 py-2 text-sm text-ink placeholder:text-muted-ink"
	></textarea>
</div>
