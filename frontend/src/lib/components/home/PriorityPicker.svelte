<script lang="ts">
	import { cn } from '$lib/utils';
	import { messages } from '$lib/messages';
	import { setTaskPriority } from '$lib/userEdits.svelte';
	import type { Priority, Task } from '$lib/data';

	/**
	 * Set a task's priority without leaving the row.
	 *
	 * Three radio buttons, not a select: there are exactly three values, so a
	 * dropdown would hide two of them behind a click and cost a keystroke to reach.
	 * Radios also give arrow-key movement and a single tab stop for free.
	 *
	 * ## Deliberately not coloured by its own value
	 *
	 * The row's left edge and wash already carry priority. A second colour source
	 * in the same row would compete with the first, and `high` is not the same
	 * signal as overdue -- which owns the urgent coral. So the checked state is
	 * drawn in ink, which says "chosen" without claiming to mean anything else.
	 *
	 * The focus ring has to come from the input, which is visually hidden, so it is
	 * forwarded onto the label the input labels.
	 */
	let {
		task,
		current
	}: {
		task: Task;
		/** The RESOLVED value, which may be the student's own override. */
		current: Priority;
	} = $props();

	const options: { value: Priority; short: string; full: string }[] = [
		{
			value: 'high',
			short: messages.taskEditing.priorityHigh,
			full: messages.taskEditing.priorityHighFull
		},
		{
			value: 'medium',
			short: messages.taskEditing.priorityMedium,
			full: messages.taskEditing.priorityMediumFull
		},
		{
			value: 'low',
			short: messages.taskEditing.priorityLow,
			full: messages.taskEditing.priorityLowFull
		}
	];

	// Scoped to the task, so two open editors cannot share a radio group and
	// unset each other.
	const name = $derived(`priority-${task.id}`);
</script>

<fieldset class="flex items-center gap-1">
	<legend class="sr-only">{messages.taskEditing.priorityLegend(task.title)}</legend>

	{#each options as option (option.value)}
		{@const checked = option.value === current}
		<label
			class={cn(
				'cursor-pointer rounded-sm border-[1.5px] px-1.5 py-0.5 text-3xs font-medium',
				'transition-colors duration-(--motion-fast) ease-standard',
				'has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary',
				checked
					? 'border-line-strong bg-ink text-surface'
					: 'border-line bg-surface text-muted-ink hover:border-line-strong hover:text-body'
			)}
		>
			<input
				type="radio"
				{name}
				value={option.value}
				{checked}
				onchange={() => setTaskPriority(task, option.value)}
				class="sr-only"
			/>
			{option.short}
			<span class="sr-only"> — {option.full}</span>
		</label>
	{/each}
</fieldset>
