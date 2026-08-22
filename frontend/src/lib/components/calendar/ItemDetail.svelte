<script lang="ts">
	import { untrack } from 'svelte';
	import CalendarPlus from '@lucide/svelte/icons/calendar-plus';
	import MapPin from '@lucide/svelte/icons/map-pin';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import X from '@lucide/svelte/icons/x';

	import Button from '$lib/components/ui/Button.svelte';
	import Tag from '$lib/components/ui/Tag.svelte';
	import { clickOutside } from '$lib/actions/clickOutside';
	import { escapeKey } from '$lib/actions/escapeKey';
	import { focusTrap } from '$lib/actions/focusTrap';
	import {
		deleteCustomEvent,
		itemLabels,
		itemUrgent,
		labelFor,
		setItemLabel,
		setItemUrgent,
		urgentFor
	} from '$lib/calendarItems';
	import { downloadItemIcs } from '$lib/ics';
	import { messages } from '$lib/messages';
	import { showToast } from '$lib/toast.svelte';
	import { categoryLabel, categoryTag, type ScheduleItem } from '$lib/schedule';
	import { cn } from '$lib/utils';

	/**
	 * Everything about one item, without leaving the calendar.
	 *
	 * The brief was "reach a lot of information from this page". A row carries a
	 * time, a title and two chips before it stops being scannable, so the rest --
	 * location, description, course, priority, and every edit control -- lives here.
	 *
	 * A DIALOG rather than an expanding row. Expanding pushes the whole day list
	 * down and loses the student's place, and on a phone an expanded row is
	 * indistinguishable from a new section.
	 *
	 * ## It is a real dialog, which the Next version was not
	 *
	 * The source had `role="dialog"` and `aria-modal="true"` on a div that did
	 * three of the six things those attributes promise. It moved focus in and it
	 * closed on Escape; it did not trap focus, did not restore focus on close, and
	 * fired `deleteCustomEvent` on one click of a button labelled "delete".
	 *
	 * All three are fixed here:
	 *
	 *  - **Focus in, trapped, and returned** — `use:focusTrap`, which owns all
	 *    three because they are one contract. Focus lands on CLOSE rather than the
	 *    label field: the common case is reading, and stealing focus into a text
	 *    input makes Escape feel like it cancelled an edit that never started.
	 *  - **Escape and an outside press dismiss** — `use:escapeKey` and
	 *    `use:clickOutside`, the same two actions the stat popover uses, rather
	 *    than a `window` listener and an `onClick` on the scrim with a
	 *    `stopPropagation` on the panel. `clickOutside` listens in the capture
	 *    phase, so nothing downstream can swallow a dismissal.
	 *  - **Delete asks first.** See the note on the confirm step below.
	 *
	 * ## The two live fields read the STORES, not the row
	 *
	 * `item` is a snapshot: `CalendarView` puts the row it was handed into state,
	 * and that object does not change when a store does. So reading the row's own
	 * `urgent` for the checkbox would show the value as it was when the dialog
	 * opened and never move — which is what the Next version does, and why
	 * un-marking urgent there appears to do nothing until the dialog is reopened.
	 *
	 * Label and urgent are therefore resolved live, through the same `labelFor` /
	 * `urgentFor` that `mergedSchedule` applies to every row. One rule, so the
	 * dialog and the row behind it cannot disagree. Everything else on the item --
	 * title, time, description, course -- cannot change while the dialog is open,
	 * so the snapshot is the right source for those.
	 */
	let {
		item,
		onClose
	}: {
		item: ScheduleItem;
		onClose: () => void;
	} = $props();

	const copy = messages.calendar.detail;

	/**
	 * THE ROW, LATCHED AT MOUNT. Nothing below reads the prop again.
	 *
	 * `item` is a prop, which in Svelte 5 is a GETTER over the parent's state --
	 * here, `CalendarView.detail`. Closing writes `null` into that state, and the
	 * `{#if}` around this component then tears the subtree down. Between those two
	 * things the getter returns null while this component's handlers and deriveds
	 * still exist, so the type saying `ScheduleItem` is true of the value and not
	 * of the getter.
	 *
	 * That is not theoretical. It threw: closing while focus was in the label field
	 * fired `onblur` DURING teardown, `commitLabel` read `item.id` off the prop, and the page
	 * logged `Cannot read properties of null (reading 'id')`. Caught by
	 * `check-interaction.mjs`, which fails on a console error — no test in the
	 * suite could have seen it, because none of them has a focus model.
	 *
	 * Latching fixes the whole class rather than that one handler. It is also
	 * honest about what this component already is: `detail` is a snapshot, the
	 * dialog is modal so nothing can swap the row underneath it, and the two things
	 * that CAN change while it is open are read from their stores below.
	 */
	const row = untrack(() => item);

	/** Live, through the shared rule. See the note above. */
	const label = $derived(labelFor(row.id, row.label, itemLabels()));
	const urgent = $derived(urgentFor(row.id, row.urgent, itemUrgent(), row.done));

	/*
	 * The label field's draft, seeded once.
	 *
	 * `untrack` says out loud that the resolved label is the INITIAL value and not
	 * a source this state follows. A field that re-seeded from the store would
	 * overwrite what the student is typing the moment anything else wrote.
	 */
	let draft = $state(untrack(() => label ?? ''));

	/** The two-step delete. False until the first press. */
	let confirming = $state(false);

	const isCustom = $derived(row.customEvent !== undefined);
	const canExport = $derived(Boolean(row.startISO));

	function commitLabel() {
		setItemLabel(row.id, draft);
	}

	/**
	 * Close, committing the label on the way out.
	 *
	 * The commit cannot be left to `onblur` alone. Escape and an outside press
	 * both unmount the dialog without the input ever blurring in a way Svelte will
	 * dispatch, so a student who typed a label and pressed Escape would lose it --
	 * and Escape on a dialog means "I am done", not "throw that away".
	 */
	function close() {
		commitLabel();
		onClose();
	}

	/**
	 * Escape peels one layer at a time.
	 *
	 * With the confirmation up, Escape cancels the confirmation rather than the
	 * dialog. Anything else means the key that normally means "back out of this"
	 * skips straight past the question the student was being asked, and they land
	 * on the day list with no idea whether the delete happened.
	 */
	function onEscape() {
		if (confirming) {
			confirming = false;
			return;
		}
		close();
	}

	/**
	 * Put focus on the first control in a group the moment it appears.
	 *
	 * Local, and one line, because it means one thing on one element in one
	 * component. `$lib/actions` is for behaviour with more than one caller —
	 * promoting this would be three files for a `querySelector`.
	 */
	function focusFirst(node: HTMLElement) {
		node.querySelector('button')?.focus();
	}

	function confirmDelete() {
		// The attached source row, never a prefix sliced off the id -- the item id
		// carries `custom-` twice, so parsing it is doubly wrong here.
		const event = row.customEvent;
		if (!event) return;

		deleteCustomEvent(event.id);
		showToast(copy.deleted(row.title));
		/*
		 * `onClose`, not `close`. Committing a label onto an event that no longer
		 * exists would write an orphaned override under an id `deleteCustomEvent`
		 * has just finished clearing.
		 */
		onClose();
	}
</script>

<!--
	The scrim. Fixed, so it covers the page rather than the panel it was opened
	from, and `bg-ink/20` rather than a token of its own: it is the ink colour at
	low alpha, which is a use of the palette rather than a new entry in it.

	Bottom-anchored on a phone and centred from `sm` up. A dialog that appears in
	the middle of a small screen has its controls under the fold of a thumb's
	reach; one anchored to the bottom edge does not, and the square top corners
	say it is attached to that edge rather than floating over it.
-->
<div class="fixed inset-0 z-50 flex items-end justify-center bg-ink/20 p-0 sm:items-center sm:p-4">
	<div
		role="dialog"
		aria-modal="true"
		aria-labelledby={copy.headingId}
		use:focusTrap={{ initial: '[data-dialog-close]' }}
		use:escapeKey={onEscape}
		use:clickOutside={{ onOutside: close }}
		class="thrive-panel max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-b-none sm:rounded-xl"
	>
		<div class="flex items-start justify-between gap-3">
			<div class="min-w-0 flex-1">
				<p class="flex flex-wrap items-center gap-1.5">
					<!-- The category tag is deliberately NOT a `Tag` tone: eleven
					     categories against a handful of status tones, and `categoryTag` is
					     the one place hues are used categorically. Same call `ItemRow`
					     makes, and its written label goes with it. -->
					<span class={cn('rounded-xs px-1.5 py-0.5 text-3xs', categoryTag[row.category])}>
						{categoryLabel[row.category].toLowerCase()}
					</span>
					{#if urgent}
						<Tag tone="urgent">{copy.urgent}</Tag>
					{/if}
				</p>

				<h2 id={copy.headingId} class="mt-1.5 text-lg font-bold break-words text-ink">
					{row.title}
				</h2>

				<!-- A time is a value. -->
				<p class="thrive-numeric mt-1 text-xs text-muted-ink">
					{row.allDay ? copy.allDay : row.timeLabel}
				</p>
			</div>

			<button
				type="button"
				data-dialog-close
				onclick={close}
				aria-label={copy.close}
				class="shrink-0 rounded-xs p-1.5 text-muted-ink transition-colors duration-(--motion-fast) ease-standard hover:bg-sunken hover:text-ink"
			>
				<X aria-hidden="true" class="size-4" />
			</button>
		</div>

		{#if row.detail}
			<p class="mt-3 flex items-center gap-1.5 text-xs text-muted-ink">
				<MapPin aria-hidden="true" class="size-3.5 shrink-0" />
				{row.detail}
			</p>
		{/if}

		{#if row.description}
			<p class="mt-2 text-sm text-body">{row.description}</p>
		{/if}

		{#if row.courseCode}
			<p class="mt-2 text-xs text-muted-ink">
				{copy.course}
				<span class="text-ink">{row.courseCode}</span>
			</p>
		{/if}

		{#if row.priority}
			<p class="mt-1 text-xs text-muted-ink">
				{copy.priority}
				<span class="text-ink">{row.priority}</span>
			</p>
		{/if}

		<!-- --- Edits ------------------------------------------------------- -->
		<div class="mt-4 border-t border-hairline pt-3 lg:mt-3">
			<p class="thrive-eyebrow">{copy.editEyebrow}</p>

			<label class="mt-2 flex items-center gap-2 text-3xs text-muted-ink">
				{copy.labelField}
				<!-- Committed on blur, not per keystroke, and again on close. Same rule
				     `TaskNotes` follows: a store write per character makes undo useless
				     and puts a hundred entries in localStorage for one label. -->
				<input
					bind:value={draft}
					onblur={commitLabel}
					placeholder={copy.labelPlaceholder}
					autocomplete="off"
					class="min-h-11 min-w-0 flex-1 rounded-sm border border-line bg-surface px-2 text-3xs text-ink placeholder:text-faint"
				/>
			</label>

			<label class="mt-2 flex cursor-pointer items-center gap-1.5 text-3xs text-muted-ink">
				<input
					type="checkbox"
					class="thrive-checkbox"
					checked={urgent}
					onchange={(event) => setItemUrgent(row.id, event.currentTarget.checked)}
					disabled={row.done === true}
				/>
				{copy.markUrgent}
				{#if row.done === true}
					<!-- Why it is disabled, in words. A greyed control with no reason
					     beside it reads as a bug. -->
					<span class="text-faint">{copy.urgentDisabled}</span>
				{/if}
			</label>
		</div>

		<!-- --- Actions ----------------------------------------------------- -->
		<div class="mt-4 flex flex-wrap items-center gap-2 lg:mt-3">
			<Button class="min-h-11" disabled={!canExport} onclick={() => downloadItemIcs(item)}>
				<CalendarPlus aria-hidden="true" class="size-3.5" />
				{copy.addToCalendar}
			</Button>

			{#if isCustom && !confirming}
				<!-- Destructive, so coral appears on intent rather than at rest. That is
				     what `danger` is: a neutral control that turns urgent when reached
				     for. A row of permanently red buttons stops meaning anything. -->
				<Button variant="danger" class="min-h-11" onclick={() => (confirming = true)}>
					<Trash2 aria-hidden="true" class="size-3.5" />
					{copy.delete}
				</Button>
			{/if}
		</div>

		{#if isCustom && confirming}
			<!--
				THE CONFIRMATION STEP.

				Deleting a custom event is irreversible: there is no undo slot for it,
				the way there is for a tick or an ignore, because the event is the
				student's own and nothing else holds a copy. So it asks.

				Two decisions in the button order, and both are about the second press:

				 1. "Keep it" comes FIRST, in the position the "Delete" button occupied.
				    A student who double-taps, or whose finger is already moving, hits
				    the safe control rather than the one that destroys the thing —
				    which is the failure a confirmation step exists to prevent and the
				    one that a same-position confirm button reintroduces.
				 2. Focus lands on "Keep it" too, so Enter and Space agree with the
				    pointer. The keyboard path must not be the dangerous one.

				Focused by `focusFirst` on the group rather than by an `autofocus`
				attribute: the trap's `initial` ran at mount and this branch did not
				exist then, and `autofocus` on a dynamically inserted element is honoured
				inconsistently across browsers. A one-line action runs exactly when the
				group appears, which is the moment that matters.
			-->
			<div class="mt-3 rounded-lg bg-sunken p-2.5">
				<p class="text-xs text-body">{copy.deleteConfirm(row.title)}</p>
				<div use:focusFirst class="mt-2 flex flex-wrap gap-2">
					<Button class="min-h-11" onclick={() => (confirming = false)}>
						{copy.deleteKeep}
					</Button>
					<Button variant="danger" class="min-h-11" onclick={confirmDelete}>
						<Trash2 aria-hidden="true" class="size-3.5" />
						{copy.deleteGoAhead}
					</Button>
				</div>
			</div>
		{/if}

		{#if !canExport}
			<!-- Why the export is disabled. A class is a weekday RULE with no single
			     instant behind it, which is not something a greyed button conveys. -->
			<p class="mt-2 text-3xs text-muted-ink">{copy.noInstant}</p>
		{/if}

		<!-- The standing promise. This is the surface where a student types things
		     into a browser and could reasonably assume they went somewhere. -->
		<p data-tone="sunken" class="thrive-panel mt-4 p-2.5 text-xs text-muted-ink lg:mt-3">
			<span class="font-medium text-ink">{copy.localOnlyLabel}</span>
			{copy.localOnly}
		</p>
	</div>
</div>
