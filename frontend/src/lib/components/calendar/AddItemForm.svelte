<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import X from '@lucide/svelte/icons/x';

	import Button from '$lib/components/ui/Button.svelte';
	import { addCalendarItem, DEFAULT_ADD_TIME, type AddKind } from '$lib/calendarAdd';
	import { messages } from '$lib/messages';
	import { showToast } from '$lib/toast.svelte';
	import { cn } from '$lib/utils';

	/**
	 * Add something to a day.
	 *
	 * Three kinds, and they route to three different stores because they mean
	 * three different things:
	 *
	 *   task   work with a deadline    joins the Tasks list on Home
	 *   to-do  a scratch item          joins the quick list
	 *   event  something happening     the student's own, goes nowhere else
	 *
	 * **The routing is not in this file.** It is `addCalendarItem` in
	 * `$lib/calendarAdd`, and the reason is that the routing is the only thing
	 * here that can be wrong invisibly: a to-do filed as a task turns up on Home
	 * under a heading that says "pulled from every source", and nothing throws.
	 * Nothing in this repo renders in a test, so logic left in a `.svelte` file is
	 * logic no gate can see. `calendarAdd.spec.ts` proves each kind lands in its
	 * own store and in neither of the others.
	 *
	 * What is left here is a form: which fields to show, what to say afterwards,
	 * and when to close.
	 *
	 * ## Collapsed to one button until wanted
	 *
	 * The same shape as Home's `AddTaskForm`, and for the same reason: the day
	 * panel is a list to read, and a permanent four-field form at the bottom of it
	 * is a form the student scrolls past every time they do not want it.
	 *
	 * Title is the only required field. The cost of a thing you never wrote down
	 * is higher than the cost of one filed slightly wrong, and everything here can
	 * be changed afterwards from the row's own detail dialog.
	 */
	let {
		dayKey
	}: {
		/** The selected day. "YYYY-MM-DD". */
		dayKey: string;
	} = $props();

	const copy = messages.calendar.add;

	/** The three kinds, with what each one MEANS rather than what pressing it does. */
	const kinds: { value: AddKind; label: string; hint: string; added: (t: string) => string }[] = [
		{ value: 'task', label: copy.kindTask, hint: copy.kindTaskHint, added: copy.addedTask },
		{ value: 'todo', label: copy.kindTodo, hint: copy.kindTodoHint, added: copy.addedTodo },
		{ value: 'event', label: copy.kindEvent, hint: copy.kindEventHint, added: copy.addedEvent }
	];

	/*
	 * Static field ids, matching Home's `AddTaskForm`.
	 *
	 * Safe because only one of these is ever mounted: the day panel is built once
	 * per view, and the week view's mobile branch renders the agenda, which has no
	 * add form. `TaskRow` derives its ids from the row instead, because there are
	 * twelve of it — the rule in this repo is per-instance ids for per-instance
	 * components and plain ones for singletons.
	 *
	 * The radio group's `name` runs on the same assumption, and more sharply: two
	 * groups sharing a name are ONE group, so a second form's radios would deselect
	 * the first's rather than merely mislabelling a field.
	 */

	let open = $state(false);
	let kind = $state<AddKind>('task');
	let title = $state('');
	let time = $state(DEFAULT_ADD_TIME);
	let label = $state('');
	let urgent = $state(false);

	const chosen = $derived(kinds.find((option) => option.value === kind) ?? kinds[0]);
	const canSubmit = $derived(title.trim().length > 0);

	function reset() {
		title = '';
		label = '';
		urgent = false;
		time = DEFAULT_ADD_TIME;
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!canSubmit) return;

		const added = chosen;
		const itemId = addCalendarItem(kind, { dayKey, title, time, label, urgent });
		if (!itemId) return;

		/*
		 * Say WHERE it went, not just that it worked.
		 *
		 * The whole point of the kind picker is that three kinds go to three
		 * different lists, and a student who picked the wrong one finds out days
		 * later on a different page. "added to your to-do list" is the sentence that
		 * closes that gap, and it costs nothing.
		 *
		 * Through the app-wide toast rather than a live region of this component's
		 * own: `Toast` is already mounted with `role="status"` in the shell, and a
		 * second region would talk over it. Same call `TaskRow`'s copy-to-list makes.
		 */
		showToast(added.added(title.trim()));

		/*
		 * NO ARRIVAL, and that is a decision rather than an omission.
		 *
		 * `arriveAtRow` is the one way any surface moves a student to a row, and it
		 * needs a row with a DOM id to move to. Calendar rows carry none — the
		 * arrival mechanism exists for Home's stat popovers, which jump across a
		 * collapsed card to a row that may not be rendered. Nothing like that is
		 * happening here: the form sits directly above the list it just added to, on
		 * the day it added to, and the new row appears a few hundred pixels away.
		 *
		 * Giving every calendar row an id to support a jump nobody asked for would
		 * add a second arrival surface with its own gate, and — for a to-do, which
		 * lands in a section rather than at the cursor — would move the page under a
		 * student who is about to add a second thing.
		 */
		reset();
		open = false;
	}
</script>

{#if !open}
	<!-- A dashed edge, because this is a placeholder for something that is not
	     there yet rather than a control acting on what is. -->
	<button
		type="button"
		onclick={() => (open = true)}
		class="inline-flex min-h-11 w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-line-strong px-3 text-2xs font-medium text-muted-ink transition-colors duration-(--motion-fast) ease-standard hover:bg-sunken hover:text-ink"
	>
		<Plus aria-hidden="true" class="size-3.5" />
		{copy.open}
	</button>
{:else}
	<form onsubmit={submit} data-tone="sunken" class="thrive-panel p-3">
		<div class="flex items-center justify-between gap-2">
			<p class="thrive-eyebrow">{copy.eyebrow}</p>
			<button
				type="button"
				onclick={() => {
					reset();
					open = false;
				}}
				aria-label={copy.cancel}
				class="rounded-xs p-1 text-muted-ink transition-colors duration-(--motion-fast) ease-standard hover:bg-surface hover:text-ink"
			>
				<X aria-hidden="true" class="size-3.5" />
			</button>
		</div>

		<!--
			KIND FIRST, because it changes what the rest of the form means.

			A real `radiogroup`, not three buttons that look like one: arrow keys move
			between radios, the group is one tab stop, and the selected value is
			announced. The visible control is the label, with the input `sr-only`
			behind it — the same construction `KeyBar` uses for its stream chips, and
			the reason both carry a `has-[:focus-visible]` outline.
		-->
		<fieldset class="mt-2">
			<legend class="sr-only">{copy.kindLegend}</legend>
			<div class="flex gap-1">
				{#each kinds as option (option.value)}
					<label
						title={option.hint}
						class={cn(
							'flex-1 cursor-pointer rounded-xs border px-2 py-1 text-center text-3xs font-medium',
							'transition-colors duration-(--motion-fast) ease-standard',
							'has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary',
							kind === option.value
								? 'border-line-strong bg-primary text-on-primary'
								: 'border-line bg-surface text-muted-ink hover:text-ink'
						)}
					>
						<input
							type="radio"
							class="sr-only"
							name="add-kind"
							value={option.value}
							checked={kind === option.value}
							onchange={() => (kind = option.value)}
						/>
						{option.label}
					</label>
				{/each}
			</div>
		</fieldset>

		<label class="sr-only" for="add-item-title">{copy.titleField}</label>
		<input
			id="add-item-title"
			bind:value={title}
			placeholder={copy.titlePlaceholder}
			autocomplete="off"
			class="mt-2 min-h-11 w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2.5 text-sm text-ink placeholder:text-muted-ink"
		/>

		<div class="mt-2 flex flex-wrap gap-2">
			<!-- A to-do has NO TIME. The quick list does not offer one and
			     `todoToItem` renders every to-do "All day", so a picker here would
			     store a number nothing reads and contradict the row it produces. -->
			{#if kind !== 'todo'}
				<span class="flex items-center gap-1.5">
					<label for="add-item-time" class="text-3xs text-muted-ink">{copy.timeField}</label>
					<!-- A clock value, so the field's own digits take the numeric face. -->
					<input
						id="add-item-time"
						type="time"
						bind:value={time}
						class="thrive-numeric min-h-11 rounded-sm border-[1.5px] border-line-strong bg-surface px-2 text-3xs text-ink"
					/>
				</span>
			{/if}

			<span class="flex min-w-0 flex-1 items-center gap-1.5">
				<label for="add-item-label" class="text-3xs text-muted-ink">{copy.labelField}</label>
				<input
					id="add-item-label"
					bind:value={label}
					placeholder={copy.labelPlaceholder}
					autocomplete="off"
					class="min-h-11 min-w-0 flex-1 rounded-sm border border-line bg-surface px-2 text-3xs text-ink placeholder:text-faint"
				/>
			</span>
		</div>

		<label class="mt-2 flex cursor-pointer items-center gap-1.5 text-3xs text-muted-ink">
			<input type="checkbox" class="thrive-checkbox" bind:checked={urgent} />
			{copy.markUrgent}
		</label>

		<!-- The button names the kind, because the kind IS the decision this form
		     makes. "Add" would leave the routing unstated at the moment it happens. -->
		<Button
			type="submit"
			variant="primary"
			disabled={!canSubmit}
			class="mt-3 min-h-11 w-full"
		>
			{copy.submit(chosen.label)}
		</Button>
	</form>
{/if}
