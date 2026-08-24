<script lang="ts">
	import CheckCheck from '@lucide/svelte/icons/check-check';

	import { messages } from '$lib/messages';
	import { COLLAPSED_TASK_ROWS } from '$lib/cardLayout';
	import { collapseList } from '$lib/collapse';
	import { buildHomeGroups, nonEmptyGroups } from '$lib/homeGroups';
	import { planReveal } from '$lib/reveal';
	import { arriveAtRow } from '$lib/arrive';
	import { getRevealChannel } from '$lib/reveal.svelte';
	import {
		addTask,
		reorderWithin,
		setTaskDue,
		taskDoneOverrides,
		taskOrder,
		taskToggle
	} from '$lib/userEdits.svelte';
	import {
		dateForGroup,
		dropIndexWithin,
		isDatedGroup,
		mintTaskId,
		newTaskFrom,
		reorderedIds
	} from '$lib/taskBoard';
	import AddTaskForm from './AddTaskForm.svelte';
	import DueDateEditor from './DueDateEditor.svelte';
	import TaskRow from './TaskRow.svelte';
	import UndoBar from './UndoBar.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import ProgressBar from '$lib/components/ui/ProgressBar.svelte';
	import SectionCard from '$lib/components/ui/SectionCard.svelte';
	import ShowMore from '$lib/components/ui/ShowMore.svelte';
	import type { GroupKey, HomeRow } from '$lib/homeGroups';
	import type { DatedGroupKey } from '$lib/taskBoard';
	import type { NewTaskInput } from '$lib/taskBoard';

	/**
	 * Home's Tasks card: the list, and everything a student can do to it.
	 *
	 * ## The rows arrive RESOLVED
	 *
	 * `rows` already has the student's title, priority and due-date edits applied
	 * and reclassified -- `+page.svelte` calls `resolveRows` once and hands the same
	 * array to this card and to the stat pills. That is deliberate and it is the
	 * only arrangement that keeps them honest: if this card resolved its own rows,
	 * moving a due date would restyle the list while the pill above it went on
	 * counting the server's answer, which is the exact contradiction the pills were
	 * made client-side to fix in 6a.
	 *
	 * Grouping, counting and ordering are in `$lib/homeGroups`; the date and id
	 * arithmetic is in `$lib/taskBoard`. Both pure and tested. This component
	 * decides only what is on screen and what a gesture means.
	 *
	 * ## Collapsed is FLAT. Expanded is grouped. Reordering needs the groups.
	 *
	 * The flat/grouped split is 6a's, and it came from measuring: three group
	 * headings plus the Done heading plus the gaps cost ~190px before the first row,
	 * so at any cap that fit a laptop the card showed one task.
	 *
	 * **Reordering is therefore only offered when the card is EXPANDED**, and that
	 * follows from the split rather than being a separate decision. Collapsed, the
	 * rows are a flat slice spanning several groups, so "move this up" has no
	 * meaning to write down: sort keys are read per group, so moving a row past a
	 * group boundary in the flat list would persist a key and change nothing on
	 * screen -- a control that appears to work and does not. The Next app never had
	 * to answer this because its card was always grouped.
	 *
	 * Ticking, editing, notes, the due chip and copy-to-list are available in both
	 * states. Only position is grouped-only.
	 *
	 * ## The collapse does not persist
	 *
	 * Local `$state`. An expanded card is a momentary intent, not a preference, and
	 * a card that remembers being open makes the one-screen guarantee conditional on
	 * history.
	 *
	 * Expanding cannot move the grid: `.thrive-card-body` is a FIXED height above
	 * `lg`, not a maximum, so growing the content can only ever scroll it.
	 */
	let {
		rows,
		nowISO
	}: {
		/** Already resolved. See the note above. */
		rows: HomeRow[];
		/** The server's instant. Every date written here measures against it. */
		nowISO: string;
	} = $props();

	const reveal = getRevealChannel();

	let openExpanded = $state(false);
	let doneExpanded = $state(false);

	const board = $derived(buildHomeGroups(rows, taskDoneOverrides(), taskOrder()));
	const groups = $derived(nonEmptyGroups(board.groups));

	/**
	 * The open rows in group order, flattened.
	 *
	 * Flattened so the collapse counts ROWS rather than groups. Collapsing per group
	 * would show four overdue, four today and four this week -- twelve rows, and no
	 * cap held.
	 */
	const flatOpen = $derived(groups.flatMap((group) => group.rows));

	const openCollapse = $derived(collapseList(flatOpen, COLLAPSED_TASK_ROWS, openExpanded));
	const doneCollapse = $derived(collapseList(board.done, 0, doneExpanded));

	const undo = $derived(taskToggle.undo);

	/* --- The live region -------------------------------------------------- */

	/**
	 * What to announce after an action, cleared once it has had time to be read.
	 *
	 * Cleared rather than left in place so the SAME move made twice is announced
	 * the second time too -- an unchanged live region says nothing at all, which
	 * makes a repeated keyboard reorder silent exactly when it is being used most.
	 */
	let announcement = $state('');
	let liveTimer: ReturnType<typeof setTimeout> | null = null;
	const ANNOUNCE_MS = 4000;

	function announce(message: string) {
		if (liveTimer) clearTimeout(liveTimer);
		announcement = message;
		liveTimer = setTimeout(() => (announcement = ''), ANNOUNCE_MS);
	}

	/**
	 * ONE sentence, and the card's only live region.
	 *
	 * Counts, undo and moves all come through here. Three regions would talk over
	 * each other on a single action, which is what the events card had before it was
	 * cut to one -- and it is why `UndoBar` is deliberately not a live region of its
	 * own.
	 */
	const liveSentence = $derived.by(() => {
		if (announcement) return announcement;

		if (undo) {
			const action = undo.markedDone
				? messages.taskEditing.markedDone
				: messages.taskEditing.markedNotDone;
			return messages.taskEditing.liveWithUndo(
				action,
				undo.task.title,
				board.doneCount,
				board.total
			);
		}

		return messages.home.tasks.liveCount(board.doneCount, board.total);
	});

	/* --- Ticking, and the way back ---------------------------------------- */

	function toggle(task: HomeRow['task']) {
		taskToggle.toggle(task);
	}

	/**
	 * Undo a tick, and take the student back to the row.
	 *
	 * ## Why every write happens BEFORE the single `tick()`
	 *
	 * `arriveAtRow` awaits exactly one `tick()`. That was flagged in 6a as the first
	 * thing 6b might break: unticking pulls a task out of Done and back into its
	 * group, so the arrival lands on a row that has just moved, and if the row needs
	 * two flushes to exist the arrival does nothing -- silently, and identically to
	 * a successful arrival at a row that was already visible.
	 *
	 * So this does not rely on a flush count. Every state write is made here, in one
	 * synchronous handler, before `arriveAtRow` is called at all:
	 *
	 *   1. `applyUndo()` writes the done override.
	 *   2. `flatOpen` is READ, which recomputes it -- Svelte's deriveds are pull-based,
	 *      so the post-undo list is available immediately, with no flush.
	 *   3. `planReveal` says whether the restored row is past the collapsed slice,
	 *      and `openExpanded` is written if it is.
	 *   4. Only then `arriveAtRow`, whose one `tick()` now has every change to flush.
	 *
	 * One tick is sufficient by construction rather than by luck. It was still
	 * measured in a real browser -- see `check-interaction.mjs`.
	 *
	 * ## The row that comes back to nowhere
	 *
	 * A task due three weeks out can be ticked (Done is not week-filtered) and
	 * unticked, and the week filter then removes it from the open groups again. The
	 * row genuinely does not exist, so there is nothing to arrive at. That case is
	 * ANNOUNCED rather than silently skipped -- and skipping `arriveAtRow` also keeps
	 * its dev warning meaningful, since a warning that fires on a legitimate path
	 * teaches everyone to ignore it.
	 */
	async function undoTick() {
		const pending = taskToggle.undo;
		if (!pending) return;

		const target = { kind: 'task' as const, id: pending.task.id };

		taskToggle.applyUndo();

		const plan = planReveal(
			flatOpen.map((row) => row.task.id),
			COLLAPSED_TASK_ROWS,
			target.id
		);

		if (!plan.found) {
			// Back on the list, but not on THIS list. Say so.
			if (!board.done.some((row) => row.task.id === target.id)) {
				announce(messages.taskEditing.restoredOutOfWeek(pending.task.title));
			}
			return;
		}

		if (plan.expand) openExpanded = true;
		await arriveAtRow(target);
	}

	/* --- Moving a row ----------------------------------------------------- */

	/** What is being dragged, and where it came from. */
	interface DragState {
		id: string;
		from: GroupKey;
		index: number;
	}

	let drag = $state<DragState | null>(null);
	let dropTarget = $state<{ group: GroupKey; index: number } | null>(null);

	function endDrag() {
		drag = null;
		dropTarget = null;
	}

	/*
	 * Clear the drag state when a drag ends without a drop.
	 *
	 * ## Why this is not on the row
	 *
	 * It was, as part of the `reorder` object, and it warned. A drop moves the row
	 * to another group, which tears down its `{#each}` block; the browser then fires
	 * `dragend` on the old element and that handler read the `reorder` prop -- a
	 * derived owned by the block that had just been destroyed. Svelte named it
	 * exactly: `derived_inert`, "reading a derived belonging to a now-destroyed
	 * effect may result in stale values".
	 *
	 * Found by dragging in a real browser, not by any of the six gates. `npm run
	 * check` is clean, the tests are clean, and the production build logs the same
	 * warning -- which `check:interaction` fails on, but only for gestures it
	 * actually performs. It now performs this one.
	 *
	 * ## Why a document listener works, and is not a fudge
	 *
	 * The listener exists only while a drag is in progress -- the same "lifetime is
	 * the state's" shape as `clickOutside` and `escapeKey`, one level up.
	 *
	 * A cancelled drag (dropped on nothing) leaves the source row in place, so its
	 * `dragend` bubbles to `document` and this clears. A completed drop has already
	 * cleared, synchronously, at the top of `onDrop` -- so if the source row has been
	 * destroyed and its `dragend` reaches nothing, there is nothing left to do.
	 * Both paths are covered without a handler on a node that may not survive.
	 */
	$effect(() => {
		if (!drag) return;

		document.addEventListener('dragend', endDrag);
		return () => document.removeEventListener('dragend', endDrag);
	});

	function rowsIn(key: GroupKey): HomeRow[] {
		return groups.find((group) => group.key === key)?.rows ?? [];
	}

	function headingOf(key: GroupKey): string {
		return groups.find((group) => group.key === key)?.heading ?? key;
	}

	function move(key: GroupKey, from: number, to: number) {
		const current = rowsIn(key);
		const moved = current[from]?.task;
		if (!moved) return;

		reorderWithin(reorderedIds(current.map((row) => row.task.id), from, to));
		announce(
			messages.taskEditing.moved(moved.title, to + 1, current.length, headingOf(key))
		);
	}

	function moveToGroup(task: HomeRow['task'], target: DatedGroupKey) {
		setTaskDue(task, dateForGroup(target, task.dueDate, nowISO));
		announce(messages.taskEditing.movedToGroup(task.title, headingOf(target)));
	}

	function onDrop(target: GroupKey, index: number) {
		const active = drag;
		// Cleared FIRST, synchronously, so nothing downstream sees a half-finished
		// drag -- and so the row is free to be torn down and rebuilt in its new group.
		endDrag();
		if (!active) return;

		if (active.from === target) {
			move(target, active.index, dropIndexWithin(active.index, index));
			return;
		}

		/*
		 * "Needs a date" is a SOURCE, never a destination -- you cannot move a task
		 * into having no date, because `Task.dueDate` is required and `setTaskDue`
		 * only ever writes an instant. The guard is a type narrowing rather than a
		 * runtime check, so a future drop target has to say out loud that it is doing
		 * something `taskBoard` says is impossible.
		 */
		if (!isDatedGroup(target)) return;

		const row = rowsIn(active.from)[active.index];
		if (row) moveToGroup(row.task, target);
	}

	/* --- Adding ----------------------------------------------------------- */

	function add(input: NewTaskInput) {
		const task = newTaskFrom(input, nowISO, mintTaskId());
		if (!task) return;

		addTask(task);
		announce(messages.taskEditing.added(task.title));
	}

	/* --- Answering a reveal request --------------------------------------- */

	/**
	 * The last reveal request this card acted on.
	 *
	 * A plain `let`, deliberately not `$state`: writing it must not re-trigger the
	 * effect that writes it.
	 */
	let handledNonce = -1;

	/*
	 * `flatOpen` and `board.done` are read here and NOT `openCollapse` /
	 * `doneCollapse`. The collapse states depend on `openExpanded`, so reading one
	 * would make this effect depend on the variable it writes. `planReveal` takes
	 * the full list and the limit and answers the same question without the cycle.
	 *
	 * The done branch is no longer theoretical: 6a noted it was unreachable because
	 * no pill counts a done task, and it is still true that no PILL does -- but the
	 * path is now exercised by anything asking for a row that has been ticked.
	 */
	$effect(() => {
		const request = reveal.current();
		if (!request || request.nonce === handledNonce) return;
		if (request.target.kind !== 'task') return;

		const openPlan = planReveal(
			flatOpen.map((row) => row.task.id),
			COLLAPSED_TASK_ROWS,
			request.target.id
		);

		if (openPlan.found) {
			handledNonce = request.nonce;
			if (openPlan.expand) openExpanded = true;
			void arriveAtRow(request.target);
			return;
		}

		const donePlan = planReveal(
			board.done.map((row) => row.task.id),
			0,
			request.target.id
		);

		if (donePlan.found) {
			handledNonce = request.nonce;
			if (donePlan.expand) doneExpanded = true;
			void arriveAtRow(request.target);
		}
	});
</script>

<SectionCard
	title={messages.home.tasks.title}
	description={messages.home.tasks.description}
	href="/assignments"
>
	{#snippet meta()}
		<!-- In the header band, not the body: it is always present and never scrolled
		     to, so inside the cap it was pure overhead. -->
		<ProgressBar
			value={board.percent}
			label={messages.home.tasks.progressLabel}
			valueText={messages.home.tasks.progressValue(board.doneCount, board.total)}
			showLabel
			tone={board.doneCount === board.total ? 'onTrack' : 'primary'}
		/>
	{/snippet}

	<!-- The card's ONE live region. Counts, undo and moves all come through it. -->
	<p aria-live="polite" class="sr-only">{liveSentence}</p>

	<div id="tasks-card-list" class="space-y-3">
		{#if undo}
			<!-- Fixed at the top of the list rather than following the row, because the
			     row it refers to has just moved. -->
			<UndoBar {undo} onUndo={undoTick} />
		{/if}

		<!--
			The open rows are their OWN region, and the id is the point.

			Both show-more controls used to declare `aria-controls="tasks-card-list"` --
			this whole list, including the done group that neither of them governs. Two
			controls claiming one region is wrong for a screen-reader user (each
			announces that it expands something it does not) and it trapped the
			interaction gate twice, because "the control for this list" was ambiguous and
			had to be disambiguated by document order.

			So the open rows and the done rows each get an id and each control names the
			region it actually expands. `#tasks-card-list` stays as the card's list
			container, and nothing claims to control it now.

			Rendered only when there ARE open rows, so this is never an empty box taking
			a `space-y-3` gap. Safe for the footer control, which exists only when
			`openCollapse.canExpand` -- and that requires rows.

			`space-y-3` moves here from the parent so the gaps BETWEEN group sections are
			unchanged now they sit one level deeper.
		-->
		{#if flatOpen.length > 0}
			<div id="tasks-open-list" class="space-y-3">
				{#if openCollapse.isExpanded}
					<!-- Expanded: grouped, and the only state where position can be changed. -->
					{#each groups as group (group.key)}
						{@const droppable = isDatedGroup(group.key)}
						<section aria-label={group.heading}>
							<h3 class="thrive-eyebrow mb-1">{group.heading}</h3>

							<!-- The group is its own drop zone, so a row can be dropped in the empty
							     area below the last one and still land in this group. "Needs a date"
							     gets none: there is nothing to write. -->
							<div
								role="list"
								class="min-h-4 space-y-2"
								ondragover={(event) => {
									if (!drag || !droppable) return;
									event.preventDefault();
									dropTarget = { group: group.key, index: group.rows.length };
								}}
								ondrop={(event) => {
									event.preventDefault();
									onDrop(group.key, group.rows.length);
								}}
							>
								{#each group.rows as row, index (row.task.id)}
									<TaskRow
										task={row.task}
										due={row.due}
										done={false}
										onToggle={toggle}
										reorder={{
											onDragStart: () => (drag = { id: row.task.id, from: group.key, index }),
											onDragOver: (event) => {
												if (!drag) return;
												event.preventDefault();
												event.stopPropagation();
												dropTarget = { group: group.key, index };
											},
											onDrop: (event) => {
												event.preventDefault();
												event.stopPropagation();
												onDrop(group.key, index);
											},
											onMoveUp: index > 0 ? () => move(group.key, index, index - 1) : null,
											onMoveDown:
												index < group.rows.length - 1
													? () => move(group.key, index, index + 1)
													: null,
											position: messages.taskEditing.position(
												index + 1,
												group.rows.length,
												group.heading
											),
											dropBefore: dropTarget?.group === group.key && dropTarget.index === index
										}}
									>
										{#snippet dueEditor()}
											<DueDateEditor
												task={row.task}
												due={row.due}
												{nowISO}
												onPick={(iso) => {
													setTaskDue(row.task, iso);
													announce(messages.taskEditing.dueUpdated(row.task.title));
												}}
											/>
										{/snippet}
									</TaskRow>
								{/each}
							</div>
						</section>
					{/each}
					{:else}
					<!-- Collapsed: flat, and no reorder. Every row still states its own urgency
					     in its labels, so no information is lost with the headings. -->
					<div role="list" class="space-y-2">
						{#each openCollapse.visible as row (row.task.id)}
							<TaskRow task={row.task} due={row.due} done={false} onToggle={toggle}>
								{#snippet dueEditor()}
									<DueDateEditor
										task={row.task}
										due={row.due}
										{nowISO}
										onPick={(iso) => {
											setTaskDue(row.task, iso);
											announce(messages.taskEditing.dueUpdated(row.task.title));
										}}
									/>
								{/snippet}
							</TaskRow>
						{/each}
					</div>
				{/if}
			</div>
		{/if}

		{#if board.done.length > 0}
			<section aria-label={messages.taskGroups.done}>
				<h3 class="thrive-eyebrow mb-1">
					{messages.taskGroups.done}<span class="thrive-numeric">
						{messages.common.countSuffix(board.done.length)}
					</span>
				</h3>
				<!-- Always rendered, so the id its control names is never absent. Empty
				     while collapsed, which is exactly what "expands nothing yet" means. -->
				<div id="tasks-done-list">
					{#if doneCollapse.visible.length > 0}
						<div role="list" class="space-y-2">
							{#each doneCollapse.visible as row (row.task.id)}
								<!-- No due editor and no reorder on a done row: the date has stopped
								     being a deadline and position in a record does not mean anything. -->
								<TaskRow task={row.task} due={row.due} done={true} onToggle={toggle} />
							{/each}
						</div>
					{/if}
				</div>
				{#if doneCollapse.canExpand}
					<ShowMore
						hiddenCount={doneCollapse.hiddenCount}
						expanded={doneCollapse.isExpanded}
						controls="tasks-done-list"
						onToggle={() => (doneExpanded = !doneExpanded)}
					/>
				{/if}
			</section>
		{/if}

		{#if flatOpen.length === 0 && board.done.length === 0}
			<EmptyState icon={CheckCheck} message={messages.home.tasks.emptyAll} />
		{:else if flatOpen.length === 0}
			<EmptyState icon={CheckCheck} message={messages.home.tasks.emptyOpen} />
		{/if}

		<!-- In the body, where the source has it: it belongs after the list it adds
		     to, and the footer is reserved for the control that reveals the list. -->
		<AddTaskForm {nowISO} onAdd={add} />
	</div>

	{#snippet footer()}
		{#if openCollapse.canExpand}
			<ShowMore
				hiddenCount={openCollapse.hiddenCount}
				expanded={openCollapse.isExpanded}
				controls="tasks-open-list"
				onToggle={() => (openExpanded = !openExpanded)}
			/>
		{/if}
	{/snippet}
</SectionCard>
