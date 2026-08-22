<script lang="ts">
	import { messages } from '$lib/messages';
	import { clickOutside } from '$lib/actions/clickOutside';
	import { escapeKey } from '$lib/actions/escapeKey';
	import { fromDateInputValue, shiftFromNow, toDateInputValue } from '$lib/taskBoard';
	import DueChip from '$lib/components/ui/DueChip.svelte';
	import type { DueDescriptor } from '$lib/format';
	import type { Task } from '$lib/data';

	/**
	 * The due chip, as a button that opens a small date editor.
	 *
	 * A native `<input type="date">` rather than a hand-rolled calendar: it is
	 * keyboard-operable and screen-reader-labelled for free, and on a phone it
	 * raises the platform's own picker, which is better than anything worth
	 * building here. The three shortcuts cover the cases a student actually wants
	 * without making them read a calendar to find tomorrow.
	 *
	 * ## Dismissal is two actions, not two `useEffect`s
	 *
	 * The Next version added and removed `pointerdown` and `keydown` listeners in
	 * an effect keyed on `open`, which meant an effect re-checking the state it was
	 * already keyed on. `clickOutside` and `escapeKey` sit on the panel inside the
	 * `{#if open}`, so each listener's lifetime IS the panel's and there is no open
	 * state to keep them in step with.
	 *
	 * `alsoInside` carries the trigger. Without it, pressing the chip to close
	 * fires the outside handler first, the panel unmounts, and the chip's own click
	 * reopens what the student just dismissed.
	 *
	 * ## Nothing here reads a clock
	 *
	 * `nowISO` is the server's instant, and every shortcut is `shiftFromNow`
	 * measured against it. The chip renders the descriptor the server (or
	 * `resolveRows`, against the same instant) already classified.
	 */
	let {
		task,
		due,
		nowISO,
		onPick
	}: {
		task: Task;
		due: DueDescriptor;
		/** The server's instant. Never `new Date()`. */
		nowISO: string;
		onPick: (iso: string) => void;
	} = $props();

	let open = $state(false);
	let trigger: HTMLButtonElement | undefined = $state();

	function close() {
		open = false;
		trigger?.focus();
	}

	function pick(iso: string) {
		onPick(iso);
		close();
	}

	const shortcuts = $derived([
		{ days: 0, label: messages.taskEditing.dueToday },
		{ days: 1, label: messages.taskEditing.dueTomorrow },
		{ days: 7, label: messages.taskEditing.dueNextWeek }
	]);

	const inputId = $derived(`due-${task.id}`);
</script>

<span class="relative inline-flex">
	<button
		bind:this={trigger}
		type="button"
		aria-expanded={open}
		aria-haspopup="dialog"
		onclick={() => (open = !open)}
		class="rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
	>
		<DueChip {due} />
		<span class="sr-only">{messages.taskEditing.changeDue(task.title)}</span>
	</button>

	{#if open}
		<div
			role="dialog"
			aria-label={messages.taskEditing.dueDialogLabel(task.title)}
			use:clickOutside={{ onOutside: () => (open = false), alsoInside: [trigger] }}
			use:escapeKey={close}
			class="thrive-panel absolute top-full left-0 z-30 mt-1 w-56 p-2.5"
		>
			<div class="flex flex-col gap-1.5">
				{#each shortcuts as shortcut (shortcut.days)}
					<button
						type="button"
						onclick={() => pick(shiftFromNow(shortcut.days, task.dueDate, nowISO))}
						class="min-h-11 rounded-sm border-2 border-line bg-surface px-2 text-left text-2xs text-body transition-colors duration-(--motion-fast) ease-standard hover:border-primary hover:text-primary-hover lg:min-h-9"
					>
						{shortcut.label}
					</button>
				{/each}
			</div>

			<label for={inputId} class="mt-2.5 block text-3xs text-muted-ink uppercase">
				{messages.taskEditing.duePick}
			</label>
			<input
				id={inputId}
				type="date"
				value={toDateInputValue(task.dueDate)}
				onchange={(event) => {
					// An empty value means the field was cleared, not a date of zero.
					const next = event.currentTarget.value;
					// `nowISO` is the fallback clock, which is what makes this the fix
					// path for a "Needs a date" row: that task's own date does not parse,
					// so there is no time of day on it to carry over.
					if (next) pick(fromDateInputValue(next, task.dueDate, nowISO));
				}}
				class="mt-1 min-h-11 w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2 text-2xs text-ink lg:min-h-9"
			/>
		</div>
	{/if}
</span>
