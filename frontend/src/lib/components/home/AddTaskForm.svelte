<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';

	import { messages } from '$lib/messages';
	import { toDateInputValue } from '$lib/taskBoard';
	import type { NewTaskInput } from '$lib/taskBoard';
	import type { Priority } from '$lib/data';

	/**
	 * Quick add, collapsed to one button until wanted.
	 *
	 * Title is the only required field. Everything else has a working default --
	 * due today, medium priority, no label -- because the cost of a task you never
	 * write down is higher than the cost of one filed slightly wrong, and every
	 * field here can be edited on the row afterwards.
	 *
	 * ## Why the priority control here is a select and the row's is radios
	 *
	 * They are answering different questions. On a row, priority is one of three
	 * values a student is CHANGING, in a strip where all three should be visible
	 * and one arrow key apart. In this form it is one of four fields being filled
	 * in sequence, and a three-wide radio group in a two-column grid would be
	 * wider than the field beside it. Kept as the Next source has it.
	 *
	 * A native select inherits the platform's colours, which on a dark-set OS
	 * renders white-on-white against our light fill, so the colours are explicit.
	 *
	 * ## Submitting keeps the form open
	 *
	 * Adding one task usually means adding two, and collapsing would make the
	 * second one a fresh decision. The fields reset; the form stays.
	 */
	let {
		nowISO,
		onAdd
	}: {
		/** The server's instant, so the default due day is not a client clock read. */
		nowISO: string;
		onAdd: (input: NewTaskInput) => void;
	} = $props();

	let open = $state(false);
	let title = $state('');
	/* Seeded once, on purpose: this is a form field the student then edits, and
	   `nowISO` is fixed for the life of the page. `reset()` re-reads it after each
	   submit, which is the only moment the default should come back. */
	// svelte-ignore state_referenced_locally
	let dueDay = $state(toDateInputValue(nowISO));
	let label = $state('');
	let priority = $state<Priority>('medium');

	function reset() {
		title = '';
		label = '';
		priority = 'medium';
		dueDay = toDateInputValue(nowISO);
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!title.trim()) return;

		onAdd({ title, dueDay, label, priority });
		reset();
	}
</script>

{#if !open}
	<!-- Solid, not dashed: dashed outlines are out repo-wide, and at 2px a dash
	     reads as a broken border rather than an invitation. -->
	<button
		type="button"
		onclick={() => (open = true)}
		class="mt-3 flex min-h-11 w-full items-center justify-center gap-1.5 rounded-md border border-line bg-sunken text-2xs text-body transition-colors duration-(--motion-fast) ease-standard hover:border-primary hover:bg-primary-soft hover:text-primary-hover"
	>
		<Plus aria-hidden="true" class="size-4" />
		{messages.taskEditing.addOpen}
	</button>
{:else}
	<form onsubmit={submit} class="mt-3 rounded-md border border-line bg-sunken p-2.5">
		<label for="add-task-title" class="block text-3xs text-muted-ink uppercase">
			{messages.taskEditing.addTitleField}
		</label>
		<!-- The one field worth focusing: the form only exists once the student has
		     already said they want to add something. -->
		<!-- svelte-ignore a11y_autofocus -->
		<input
			id="add-task-title"
			bind:value={title}
			autocomplete="off"
			autofocus
			placeholder={messages.taskEditing.addTitlePlaceholder}
			class="mt-1 min-h-11 w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2 text-sm text-ink placeholder:text-muted-ink"
		/>

		<div class="mt-2 grid grid-cols-2 gap-2">
			<div>
				<label for="add-task-due" class="block text-3xs text-muted-ink uppercase">
					{messages.taskEditing.addDueField}
				</label>
				<input
					id="add-task-due"
					type="date"
					bind:value={dueDay}
					class="mt-1 min-h-11 w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2 text-2xs text-ink"
				/>
			</div>

			<div>
				<label for="add-task-priority" class="block text-3xs text-muted-ink uppercase">
					{messages.taskEditing.addPriorityField}
				</label>
				<select
					id="add-task-priority"
					bind:value={priority}
					class="mt-1 min-h-11 w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2 text-2xs text-ink"
				>
					<option value="high">{messages.taskEditing.priorityHighFull}</option>
					<option value="medium">{messages.taskEditing.priorityMediumFull}</option>
					<option value="low">{messages.taskEditing.priorityLowFull}</option>
				</select>
			</div>
		</div>

		<label for="add-task-label" class="mt-2 block text-3xs text-muted-ink uppercase">
			{messages.taskEditing.addLabelField}
			<span class="normal-case">{messages.taskEditing.addLabelOptional}</span>
		</label>
		<input
			id="add-task-label"
			bind:value={label}
			autocomplete="off"
			placeholder={messages.taskEditing.addLabelPlaceholder}
			class="mt-1 min-h-11 w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2 text-2xs text-ink placeholder:text-muted-ink"
		/>

		<div class="mt-2.5 flex gap-2">
			<button
				type="submit"
				disabled={!title.trim()}
				class="inline-flex min-h-11 items-center gap-1.5 rounded-sm border border-line-strong bg-primary px-3 text-2xs font-medium text-on-primary transition-colors duration-(--motion-fast) ease-standard hover:bg-primary-hover disabled:border-line disabled:bg-surface disabled:text-muted-ink"
			>
				<Plus aria-hidden="true" class="size-3.5" />
				{messages.taskEditing.addSubmit}
			</button>
			<button
				type="button"
				onclick={() => (open = false)}
				class="min-h-11 rounded-sm border-2 border-line bg-surface px-3 text-2xs font-medium text-body transition-colors duration-(--motion-fast) ease-standard hover:border-line-strong"
			>
				{messages.taskEditing.addClose}
			</button>
		</div>
	</form>
{/if}
