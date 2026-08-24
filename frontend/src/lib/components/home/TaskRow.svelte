<script lang="ts">
	import type { Snippet } from 'svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import ListPlus from '@lucide/svelte/icons/list-plus';
	import Pencil from '@lucide/svelte/icons/pencil';
	import StickyNote from '@lucide/svelte/icons/sticky-note';

	import { cn } from '$lib/utils';
	import { messages } from '$lib/messages';
	import { revealRowId } from '$lib/reveal';
	import { rowPriorityLabel, rowPriorityOf, taskLabels } from '$lib/taskView';
	import { addQuickItem } from '$lib/quickList';
	import { showToast } from '$lib/toast.svelte';
	import { FEATURES } from '$lib/features';
	import { setTaskTitle } from '$lib/userEdits.svelte';
	import { taskNote } from '$lib/taskNotes.svelte';
	import PriorityPicker from './PriorityPicker.svelte';
	import TaskNotes from './TaskNotes.svelte';
	import Tag from '$lib/components/ui/Tag.svelte';
	import type { DueDescriptor } from '$lib/format';
	import type { Task } from '$lib/data';

	/**
	 * One task row: tick it, rename it, re-prioritise it, note it, move it.
	 *
	 * ## The 375px defect this does not reproduce
	 *
	 * MIGRATION.md section 9 defect 3, "the worst thing in the app": every task
	 * title wrapped to roughly one character per line at 375px, making Home about
	 * 7,700 CSS px tall. Isolated to TaskRow, and pre-existing rather than restyle
	 * damage.
	 *
	 * There were two causes and 6b would have reintroduced the second.
	 *
	 * 1. **A flex item's `min-width: auto`** refuses to shrink below its longest
	 *    word, so a text child with no `min-w-0` pushed the row wider than its
	 *    container and the title got whatever was left. Fixed in 6a and kept here:
	 *    `min-w-0` on the growing child, `break-words` so a long word wraps rather
	 *    than overflowing, and labels allowed onto their own line.
	 *
	 * 2. **Five 44px controls in a strip beside the title.** That is 220px of
	 *    buttons against a card about 343px wide, which leaves the title around 100px
	 *    whatever the `min-w-0` says. The read-only 6a row had no controls, so this
	 *    half of the defect was dormant rather than fixed.
	 *
	 * So the controls **wrap to their own line below `sm`** and sit inline above it.
	 * The buttons stay 44px on every pointer type -- shrinking them would trade a
	 * layout bug for a WCAG 2.5.8 failure -- and the row is simply taller on a
	 * phone, which costs nothing: `.thrive-card-body` has no height cap below `lg`,
	 * so a taller row on mobile pushes content down a page that already scrolls.
	 *
	 * Titles wrap rather than truncate: a task title is the row's subject, and half
	 * of one is not a shorter version of it.
	 *
	 * ## Structure: a div, not a label
	 *
	 * The row holds several interactive controls, and a label wrapping all of them
	 * would make pressing the note button tick the task off. The TITLE is the label
	 * for the checkbox instead, which is what makes the tick target large without
	 * `.thrive-checkbox` having to grow past the size the design system sets.
	 *
	 * ## No `justChanged` ring
	 *
	 * The Next row outlined a just-ticked task for the whole six-second undo
	 * window. Dropped, by decision: this app has ONE arrival treatment
	 * (`$lib/arrive` -- indigo, one beat, exactly one row) and a student learns that
	 * cue once. A tick is answered by the row striking through, moving to Done, the
	 * UndoBar at the top of the list, and the card's live sentence; the arrival ring
	 * is spent on the undo, which is the move that needs finding again.
	 */
	let {
		task,
		due,
		done,
		onToggle,
		reorder,
		dueEditor
	}: {
		/** Already RESOLVED -- the student's title and priority edits are applied. */
		task: Task;
		/** Classified on the server, or re-derived against the server's instant. */
		due: DueDescriptor;
		done: boolean;
		onToggle: (task: Task) => void;
		/**
		 * Drag and keyboard reordering. Omitted on a surface with no groups to move
		 * between, which is what /assignments will be.
		 */
		reorder?: {
			onDragStart: () => void;
			onDragOver: (event: DragEvent) => void;
			onDrop: (event: DragEvent) => void;
			/**
			 * No `onDragEnd`, deliberately -- the CARD clears its own drag state.
			 *
			 * It was here, and it warned. A drop moves this row to another group,
			 * which tears down its `{#each}` block; the browser then fires `dragend` on
			 * the old element, whose handler read the `reorder` prop -- a derived owned
			 * by the block that had just been destroyed. Svelte says so:
			 * `derived_inert`, "reading a derived belonging to a now-destroyed effect
			 * may result in stale values".
			 *
			 * A stale read here is harmless today, but the warning is not: the gate
			 * fails on console noise, and a real stale value in a drag handler is a
			 * genuinely hard bug. So the row no longer owns that cleanup.
			 */
			/** Null when the row is already at that end of its group. */
			onMoveUp: (() => void) | null;
			onMoveDown: (() => void) | null;
			position: string;
			dropBefore: boolean;
		};
		/** The due chip as an editor. Omitted where the date is read-only. */
		dueEditor?: Snippet;
	} = $props();

	const priority = $derived(rowPriorityOf(due, task.priority, done));
	const labels = $derived(taskLabels(task, due, done));

	const note = $derived(taskNote(task.id));
	const hasNote = $derived(note.value.length > 0);

	let noteOpen = $state(false);
	let editOpen = $state(false);
	/* Seeded once, on purpose: `openEditor()` re-seeds from the CURRENT title every
	   time the panel opens, which is the only moment a fresh value is wanted.
	   Tracking `task.title` here would overwrite the student's half-typed rename
	   the instant anything else re-derived the row. */
	// svelte-ignore state_referenced_locally
	let draft = $state(task.title);

	/**
	 * The jump target for the stat pill popovers and for the undo arrival.
	 *
	 * `tabindex="-1"` makes the row focusable programmatically without putting
	 * every row in the tab order, and it deliberately keeps its focus ring -- being
	 * able to see where the jump landed is the whole point of moving focus rather
	 * than only scrolling. Built by `revealRowId` so the id and the target cannot
	 * drift apart.
	 */
	const rowId = $derived(revealRowId({ kind: 'task', id: task.id }));

	const editId = $derived(`edit-${task.id}`);
	const noteId = $derived(`note-panel-${task.id}`);
	const checkboxId = $derived(`tick-${task.id}`);

	function openEditor() {
		// Seed from the CURRENT title each time rather than trusting stale draft
		// state: the title may have changed since this row last opened its editor.
		draft = task.title;
		editOpen = true;
	}

	/**
	 * Save the draft and close.
	 *
	 * Reached four ways -- Enter, the Save button, blur, and the pencil toggle
	 * closing the panel. **Two paths abandon instead, and only two:** Escape and
	 * Cancel. Making everything else commit is what stops "I closed it" from being
	 * a coin flip about whether the rename survived.
	 *
	 * `setTaskTitle` treats an emptied field as a REVERT rather than a blank row,
	 * and a value matching the source as no override at all. Both live in the store,
	 * so this does not have to decide either.
	 */
	function commitTitle() {
		setTaskTitle(task, draft);
		editOpen = false;
	}

	function cancelEdit() {
		draft = task.title;
		editOpen = false;
		abandoning = false;
	}

	/**
	 * Set while focus is on its way to Cancel, so blur does not commit first.
	 *
	 * The race, and it is not hypothetical: `blur` fires BEFORE `click`, so a
	 * student who types and then presses Cancel would have the draft committed by
	 * the blur and then see `cancelEdit` restore a variable that no longer matters.
	 * Cancel would save. Which is the one thing it must never do.
	 *
	 * Both halves are needed. `pointerdown` catches the mouse and touch case, and
	 * catches it in Safari, where clicking a button does not focus it and so leaves
	 * `relatedTarget` null. The `relatedTarget` check catches the keyboard case,
	 * where Tab moves focus to Cancel with no pointer event at all.
	 *
	 * A plain `let`, not `$state`: nothing renders from it.
	 */
	let abandoning = false;

	function onTitleBlur(event: FocusEvent) {
		const next = event.relatedTarget;
		const toCancel =
			abandoning || (next instanceof HTMLElement && next.dataset.abandonEdit === 'true');

		abandoning = false;
		if (toCancel) return;

		commitTitle();
	}

	function copyToList() {
		addQuickItem(task.title, { copiedFrom: task.id, dueDate: task.dueDate });
		showToast(messages.taskEditing.copied(task.title));
	}

	/** One glyph button, so five of them cannot drift apart. */
	const glyph =
		'grid size-11 shrink-0 place-items-center rounded-sm border-2 transition-colors duration-(--motion-fast) ease-standard';
	const glyphQuiet = 'border-transparent text-muted-ink hover:border-line hover:bg-sunken';
	const glyphActive = 'border-line-strong bg-sunken text-ink';
</script>

<!--
	`role="listitem"` because that is what it is, and its container says `list`.

	It also happens to be what a `draggable` div owes the a11y linter -- a static
	element with drag handlers and no role is unreachable to anything that is not a
	mouse. The role is the honest answer rather than the one that quiets the rule:
	these rows were anonymous divs inside a labelled section before, and a list of
	tasks read as a run of text.

	**Every caller must render TaskRow inside a `role="list"`.** /assignments is the
	next one.

	## No per-priority wash or left edge

	An earlier version painted `urgent`/`soon`/`later` as a tinted background plus
	a coloured left border, on top of `.thrive-row`'s own comment that priority is
	NOT carried by colour at this layer. Four adjacent rows in four different
	tints did not read as "one list with some rows more urgent" -- it read as an
	uneven, ad-hoc surface, which is exactly the opposite of what a state colour
	is for. Worse, a tint the same hue family as its OWN chip (`bg-watch-soft`
	under a solid `watch` "Due soon" chip) lowered the chip's contrast against its
	immediate surroundings instead of making it stand out.

	The chip already says the state, in words and in the one loud colour THRIVE
	spends on status (`Tag`, solid fill, measured in the contrast gate). Every row
	is now the same transparent-at-rest, sunken-on-hover surface `.thrive-row`
	already describes, and the state lives entirely in the chip -- one visual
	carrier instead of three fighting each other.

	`data-priority` stays: it is still read by the sr-only label below, and by
	anything that groups or filters rows, even though nothing paints it any more.

	## The border is a WRAPPER, not a `.thrive-row` edit

	Home's action items all draw the same `rounded-lg border border-hairline
	bg-surface` card now -- see `EventRow` and `CourseCard`. `.thrive-row` itself
	says "No border, no wash" and fills with `sunken` on hover, which a border
	and an opaque surface added to the SAME element would fight: a plain `bg-*`
	utility sits in the utilities layer, which wins over `.thrive-row:hover`'s
	component-layer fill regardless of the pseudo-class, so the hover state would
	stop painting. Wrapping instead keeps `.thrive-row` completely unedited and
	untouched at the call site -- the border lives on an outer div with no
	padding of its own, and the existing `px-2 py-1.5` below still sets the
	visible inset, so the card's padding matches the others exactly.
-->
<div class="rounded-lg border border-hairline bg-surface">
	<div
		id={rowId}
		role="listitem"
		tabindex="-1"
		data-done={done}
		data-priority={priority}
		draggable={reorder ? true : undefined}
		ondragstart={reorder?.onDragStart}
		ondragover={reorder?.onDragOver}
		ondrop={reorder?.onDrop}
		class={cn(
			'thrive-row group relative',
			/* The drop indicator: a rule where the row would land, drawn ON the row
			   rather than as an inserted gap so nothing reflows mid-drag. A list that
			   reflows under the cursor is what makes a drag feel like it is fighting
			   back. */
			reorder?.dropBefore &&
				'before:absolute before:-top-1 before:right-0 before:left-0 before:h-1 before:rounded-pill before:bg-primary'
		)}
	>
		<!-- Wraps below `sm`, so the controls take their own line and the title keeps
		     the full width. See the note on defect 3 above. -->
		<div class="flex flex-wrap items-start gap-x-2 gap-y-1 px-2 py-1.5 sm:flex-nowrap lg:py-1">
			<!-- `mt-0.5` aligns the box with the first line of the title rather than the
			     centre of a two-line block. -->
			<input
				id={checkboxId}
				type="checkbox"
				class="thrive-checkbox mt-0.5"
				checked={done}
				onchange={() => onToggle(task)}
			/>

			<!--
				`min-w-0` is half the fix for defect 3: without it this child refuses to
				shrink below its longest word and pushes the row wider than its container.

				A COLUMN rather than a baseline row is the other half.

				6a laid the title and its chips out on one wrapping line, with the title
				`flex-1 min-w-0`. That reads as "the chips wrap when they run out of room",
				but it does the opposite: `flex-1` on a `min-w-0` item means the TITLE is
				what gives way, so the chips keep their width and the title shrinks toward
				nothing. It survived 6a because a read-only row carried two small tags.

				Adding the due chip is what exposed it. Measured at 375px before this
				change: the title box was 90px wide, wrapping "Submit peer review" over
				THREE lines at six characters a line -- defect 3, arriving by a slightly
				different route than the original.

				So the title gets a line of its own. Measured after: 303px and ONE line at
				375px, 339px and one line at 1512px.
			-->
			<div class="flex min-w-0 flex-1 basis-full flex-col gap-1 sm:basis-auto">
				<!-- The title IS the checkbox's label, which is what makes the tick target
				     large without the box itself having to grow. -->
				<label
					for={checkboxId}
					data-done={done}
					class={cn(
						'thrive-strike cursor-pointer text-sm break-words',
						done ? 'text-muted-ink' : 'text-ink'
					)}
				>
					{task.title}
				</label>

				<!--
					The chips and the date on ONE line, which is the Next source's
					arrangement and worth about 27px a row.

					Stacking them as separate lines is the obvious reading of "the title has
					its own line", and it made a desktop row 83px: title, chips, date. Four
					of those plus the Done heading is 469px inside a 300px body, so the
					collapsed card scrolled to show the four rows it is tuned to show. On one
					line the row is 56px and four of them fit the cap as they did in 6a.

					They belong together anyway: the chip says WHAT state the deadline is in
					and the text says WHEN it is. Two readings of one fact, on one line.
				-->
				<p class="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-3xs text-muted-ink">
					{#each labels as label (label.text)}
						<Tag tone={label.tone}>{label.text}</Tag>
					{/each}

					<!-- A button where the date is editable, a plain chip where it is not. -->
					{#if dueEditor}{@render dueEditor()}{/if}

					<span>{due.fullLabel}</span>
					<!-- `countdown` is a value and holds its width so the row does not
					     reflow as "in 3 days" becomes "in 10 days". -->
					{#if due.countdown}
						<span aria-hidden="true">·</span>
						<span class="thrive-numeric">{due.countdown}</span>
					{/if}
					{#if task.subtasks.length > 0}
						<span aria-hidden="true">·</span>
						<span class="thrive-numeric">
							{task.subtasks.filter((subtask) => subtask.done).length}/{task.subtasks.length}
						</span>
					{/if}
					<!-- The wash and the left border are the visual carrier; this is the one
					     that survives with colour turned off. -->
					{#if priority !== 'none'}
						<span class="sr-only">{rowPriorityLabel[priority]}</span>
					{/if}
				</p>
			</div>

			<!-- Every control here is always visible and always 44px, on every pointer
			     type. An earlier pass hid the note button until hover, which on a phone
			     meant the only way to add a note was invisible.

			     "Always visible" means: whenever it is rendered at all. Two are
			     conditional and neither is conditional on the POINTER -- reorder needs
			     the groups (see TasksCard), and copy needs somewhere to copy TO.

			     `ms-auto` anchors the strip to the RIGHT, which is what makes the two
			     always-present controls pixel-stable as the conditional ones come and go.

			     Above `sm` the strip was already right-anchored, by the `flex-1` content
			     column beside it -- measured, Edit sits at the same x with two controls or
			     three. Below `sm` the strip wraps to its own line, where it was
			     LEFT-aligned, so removing the leading Copy control slid Edit and Add-a-note
			     49px left. Expanding a card did the same thing in reverse, since that adds
			     two reorder controls ahead of them.

			     So the invariant is now: a conditional control appears and disappears at
			     the strip's leading edge, and nothing already on screen moves.

			     `self-center`, against the row's own `items-start`: the checkbox needs
			     `items-start` so it sits on the title's first line rather than the middle
			     of a two-line block, but that same rule would pin the icon strip to the
			     TOP of a tall row -- title wrapped to two lines, three chips wrapping to
			     their own line -- leaving visible empty air below the icons. Centring
			     just this child keeps both true at once. -->
			<div class="ms-auto flex shrink-0 items-center gap-0.5 self-center">
				{#if FEATURES.floatingTodo}
					<!--
						Copy, not move, and never a link: the row stays here, and the two lists
						go their own ways from this moment on.

						## Gated on the flag that owns the destination

						The quick list lives in the floating To-do panel, which is behind
						`FEATURES.floatingTodo`. With the flag off, the copy still works and
						still persists to `thrive:quicklist` -- and the student has no way to
						see the thing they just copied. An action whose result is invisible
						reads as broken, which is the same reasoning that withholds a "View
						all" pointing at a parked route.

						Nothing is deleted: the store, `addQuickItem`, the tests and the toast
						all stay, and flipping one word brings the button back. Visibility only.

						Note the consequence, so it is not a surprise later: with this hidden,
						`showToast` has NO caller, so the `Toast` mounted in `AppShell` can
						never fire. That is coherent rather than dead code -- the toast exists
						for exactly this action and returns with it on the same flag -- but it
						does mean the toast is currently unexercised by anything but its tests.
					-->
					<button
						type="button"
						onclick={copyToList}
						class={cn(glyph, glyphQuiet, 'hover:text-primary')}
					>
						<ListPlus aria-hidden="true" class="size-4" />
						<span class="sr-only">{messages.taskEditing.copyToList(task.title)}</span>
					</button>
				{/if}

				{#if reorder}
					<!-- Dragging is pointer-only, so reordering gets real buttons too.
					     Without them the whole feature would be closed to keyboard users and
					     to anyone on a touch device, where HTML5 drag does not fire. -->
					<button
						type="button"
						disabled={!reorder.onMoveUp}
						onclick={() => reorder?.onMoveUp?.()}
						class={cn(
							glyph,
							glyphQuiet,
							'hover:text-ink disabled:opacity-40 disabled:hover:border-transparent disabled:hover:bg-transparent'
						)}
					>
						<ChevronUp aria-hidden="true" class="size-4" />
						<span class="sr-only">{messages.taskEditing.moveUp(task.title, reorder.position)}</span>
					</button>
					<button
						type="button"
						disabled={!reorder.onMoveDown}
						onclick={() => reorder?.onMoveDown?.()}
						class={cn(
							glyph,
							glyphQuiet,
							'hover:text-ink disabled:opacity-40 disabled:hover:border-transparent disabled:hover:bg-transparent'
						)}
					>
						<ChevronDown aria-hidden="true" class="size-4" />
						<span class="sr-only">{messages.taskEditing.moveDown(task.title, reorder.position)}</span>
					</button>
				{/if}

				<button
					type="button"
					aria-expanded={editOpen}
					aria-controls={editId}
					onclick={() => (editOpen ? commitTitle() : openEditor())}
					class={cn(glyph, editOpen ? glyphActive : cn(glyphQuiet, 'hover:text-ink'))}
				>
					<Pencil aria-hidden="true" class="size-4" />
					<span class="sr-only">{messages.taskEditing.edit(task.title)}</span>
				</button>

				<button
					type="button"
					aria-expanded={noteOpen}
					aria-controls={noteId}
					onclick={() => (noteOpen = !noteOpen)}
					class={cn(glyph, noteOpen || hasNote ? glyphActive : cn(glyphQuiet, 'hover:text-ink'))}
				>
					<StickyNote aria-hidden="true" class="size-4" />
					<span class="sr-only">
						{hasNote
							? messages.taskEditing.editNote(task.title)
							: messages.taskEditing.addNote(task.title)}
					</span>
				</button>
			</div>
		</div>

		<!-- Edit in place: rename and re-prioritise without leaving the page. -->
		<div id={editId}>
			{#if editOpen}
				<div class="mx-2 mb-2 space-y-2 rounded-md border border-line bg-sunken p-2.5">
					<div>
						<label
							for={`${editId}-title`}
							class="mb-1 block text-3xs font-medium text-muted-ink uppercase"
						>
							{messages.taskEditing.titleField}
						</label>
						<input
							id={`${editId}-title`}
							bind:value={draft}
							name="task-title"
							autocomplete="off"
							onblur={onTitleBlur}
							onkeydown={(event) => {
								if (event.key === 'Enter') {
									event.preventDefault();
									commitTitle();
								}
								if (event.key === 'Escape') {
									// Abandon the draft, keep the stored title. The opposite of
									// TaskNotes, and deliberately: a title has an original to
									// restore to, and prose does not.
									event.stopPropagation();
									cancelEdit();
								}
							}}
							class="w-full rounded-sm border-[1.5px] border-line-strong bg-surface px-2 py-1.5 text-sm text-ink"
						/>
						<p class="mt-1 text-3xs text-muted-ink">{messages.taskEditing.titleHint}</p>
					</div>

					<div>
						<span class="mb-1 block text-3xs font-medium text-muted-ink uppercase">
							{messages.taskEditing.priorityField}
						</span>
						<PriorityPicker {task} current={task.priority} />
					</div>

					<div class="flex gap-2">
						<button
							type="button"
							onclick={commitTitle}
							class="min-h-11 rounded-sm border border-line-strong bg-primary px-2.5 text-2xs font-medium text-on-primary transition-colors duration-(--motion-fast) ease-standard hover:bg-primary-hover lg:min-h-9"
						>
							{messages.taskEditing.save}
							<span class="sr-only">{messages.taskEditing.saveSubject(task.title)}</span>
						</button>
						<button
							type="button"
							data-abandon-edit="true"
							onpointerdown={() => (abandoning = true)}
							onclick={cancelEdit}
							class="min-h-11 rounded-sm border-2 border-line bg-surface px-2.5 text-2xs font-medium text-body transition-colors duration-(--motion-fast) ease-standard hover:border-line-strong lg:min-h-9"
						>
							{messages.taskEditing.cancel}
							<span class="sr-only">{messages.taskEditing.cancelSubject(task.title)}</span>
						</button>
					</div>
				</div>
			{/if}
		</div>

		<div id={noteId}>
			{#if noteOpen}
				<TaskNotes
					taskId={task.id}
					taskTitle={task.title}
					note={note.value}
					onSave={(next) => note.save(next)}
					onClose={() => (noteOpen = false)}
				/>
			{/if}
		</div>
	</div>
</div>
