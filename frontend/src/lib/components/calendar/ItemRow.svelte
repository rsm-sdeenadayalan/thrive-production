<script lang="ts">
	import AlertTriangle from '@lucide/svelte/icons/triangle-alert';
	import Info from '@lucide/svelte/icons/info';

	import Tag from '$lib/components/ui/Tag.svelte';
	import { messages } from '$lib/messages';
	import { categoryLabel, categoryTag, type ScheduleItem } from '$lib/schedule';
	import { isTickable } from '$lib/tickItem';
	import { cn } from '$lib/utils';

	/**
	 * One item, in the shape every calendar view renders it.
	 *
	 * Extracted so the day list, the week columns and the agenda cannot drift on
	 * how a class or a ticked to-do looks. The time is a value and takes
	 * `.thrive-numeric`, so a column of times aligns; the title is something a
	 * person wrote and takes DM Sans.
	 *
	 * Tickable rows carry a real checkbox that writes back to whichever store the
	 * item came from, so ticking here and ticking on Home are the same act.
	 *
	 * ## What tickable means, and what it does not
	 *
	 * `isTickable` asks whether a WRITABLE SOURCE ROW is attached -- `item.task`
	 * or `item.quickItem`, put there by `mergedSchedule` at merge time. It does
	 * not ask whether `done` happens to be set, and it does not parse the id.
	 *
	 * Those can disagree, and when they did the failure was silent: a synthetic
	 * row carrying a `done` flag with nothing behind it rendered a checkbox that
	 * appeared to tick and reverted on the next render. See `tickItem.ts` and
	 * CONVENTIONS.md.
	 *
	 * A row is also only tickable if a handler was passed. A read-only view gets
	 * the spacer, not a dead control.
	 *
	 * ## The details control
	 *
	 * `onOpen` arrived in 7c with `ItemDetail`. It is optional for the same reason
	 * `onTick` is: a view that has nowhere to put a dialog must not render a button
	 * that does nothing. The WEEK column never gets one — see `compact`.
	 */
	let {
		item,
		compact = false,
		dateLabel,
		onTick,
		onOpen
	}: {
		item: ScheduleItem;
		/**
		 * The week column's shape. Time stacked ABOVE the title, no detail line, no
		 * type tag, and the title clamped to three lines.
		 *
		 * Side-by-side was tried first in the prototype and read badly: an ~80px
		 * column minus a time gutter left "MGT 142 · Machine Learning for Business"
		 * wrapping to five lines, and adjacent columns ran together into one string.
		 *
		 * Compact rows carry NO checkbox, deliberately. A 17px control inside an
		 * 80px column with a three-line title is a mis-tap waiting to happen, and
		 * the week view's job is shape rather than action -- selecting the day drops
		 * a student into the day panel, where the same row is fully tickable.
		 */
		compact?: boolean;
		/**
		 * Pre-formatted date, shown beside the detail line.
		 *
		 * For the agenda when its groups are NOT days: grouped by type or by course,
		 * a row's time alone does not say which of thirty days it falls on. Passed in
		 * already formatted, because the caller is the only one that knows the day
		 * key and this component never interprets a date. `showsRowDate` in
		 * `$lib/calendarViews` is the decision of when to pass it.
		 */
		dateLabel?: string;
		onTick?: (item: ScheduleItem, done: boolean) => void;
		/**
		 * Open the detail dialog on this item.
		 *
		 * Absent in the week column and in any view that has no dialog to open.
		 * `CalendarView` is the only thing that can supply it, because `detail` is
		 * one of the three pieces of state that node owns.
		 */
		onOpen?: (item: ScheduleItem) => void;
	} = $props();

	const done = $derived(item.done === true);
	const tickable = $derived(!compact && isTickable(item) && Boolean(onTick));
	const time = $derived(item.allDay ? messages.calendar.row.allDay : item.timeLabel);

	// Scoped to the row, so two views showing the same item cannot collide.
	const checkboxId = $derived(`tick-${item.id}`);
</script>

{#if compact}
	<!-- A left rule rather than a border box. Without it the stacked rows in
	     adjacent day columns run together and read as one wrapped sentence. -->
	<div
		data-done={done ? 'true' : undefined}
		class="thrive-row border-l-2 border-line px-1.5 py-1 lg:py-0.5"
	>
		<span class={cn('thrive-numeric flex items-center gap-1 text-3xs', done ? 'text-faint' : 'text-muted-ink')}>
			{#if item.urgent}
				<!-- The one place urgency is a glyph rather than a pill: there is no
				     room for the word, and the pill would take the whole column. The
				     accessible name still carries it. -->
				<AlertTriangle aria-label={messages.calendar.row.urgentLabel} class="size-3 shrink-0 text-urgent" />
			{/if}
			{time}
		</span>
		<!-- No `block` here, and that is load-bearing rather than a tidy-up.
		     `line-clamp-3` works by setting `display: -webkit-box`, so a `display`
		     utility beside it wins in the cascade and the clamp silently does
		     nothing. Measured before the fix: a 71px column rendered "MGT 142 ·
		     Machine Learning for Business" 140px tall — seven lines, not three —
		     and nothing warned, because an unclamped clamp is not an error. -->
		<span
			data-done={done ? 'true' : undefined}
			class={cn(
				'thrive-strike mt-0.5 line-clamp-3 text-xs font-medium break-words',
				done ? 'text-muted-ink' : 'text-ink'
			)}
		>
			{item.title}
		</span>
	</div>
{:else}
	<div data-done={done ? 'true' : undefined} class="thrive-row flex items-baseline gap-2 px-2 py-1.5 lg:py-1">
	<!-- The checkbox is a SIBLING of the title, never a wrapper round the row: a
	     label spanning the whole row would make every control inside it tick the
	     item off. The title still labels the box, via `for`, which is what makes
	     the tick target large without the box growing past the size the design
	     system sets. Same lesson TaskRow learned. -->
	{#if tickable}
		<input
			id={checkboxId}
			type="checkbox"
			class="thrive-checkbox mt-1 self-start"
			checked={done}
			onchange={(event) => onTick?.(item, event.currentTarget.checked)}
			aria-label={messages.calendar.row.toggle(item.title, done)}
		/>
	{:else}
		<!-- A spacer the width of the control it stands in for, so titles align
		     whether or not a row can be ticked. Without it a list of classes and
		     tasks reads as two ragged columns.

		     `size-checkbox` is the SAME token `.thrive-checkbox` sizes itself from.
		     The Next version wrote `size-[17px]` here, which is a literal that
		     agrees with the stylesheet only until somebody resizes the control. -->
		<span aria-hidden="true" class="mt-1 size-checkbox shrink-0"></span>
	{/if}

	<span class={cn('thrive-numeric w-16 shrink-0 self-start pt-0.5 text-3xs', done ? 'text-faint' : 'text-muted-ink')}>
		{time}
	</span>

	<span class="min-w-0 flex-1">
		<!-- `.thrive-strike` rather than `line-through`: the rule is drawn as a
		     growing pseudo-element so completing something reads as an action
		     rather than a re-render. The app has one strike treatment and this is
		     it. -->
		<label
			for={tickable ? checkboxId : undefined}
			data-done={done ? 'true' : undefined}
			class={cn(
				'thrive-strike block text-sm font-medium break-words',
				tickable && 'cursor-pointer',
				done ? 'text-muted-ink' : 'text-ink'
			)}
		>
			{item.title}
		</label>

		{#if dateLabel || item.detail || item.label}
			<span class="mt-0.5 flex flex-wrap items-center gap-1.5">
				{#if dateLabel}
					<!-- Which day, when the group heading is not already saying it. First
					     in the line because it is the coarser fact: a student scanning a
					     type-grouped agenda is asking "when", and the course code is
					     context for the answer rather than the answer. Already formatted
					     upstream; this component never interprets a date. -->
					<span class="text-3xs font-medium text-body">{dateLabel}</span>
				{/if}

				{#if item.detail}
					<!-- A course code or a room, and only one of those is a Tag.

					     `detail` is overloaded: for a task or an assignment it is the
					     course code -- the exact fact Home renders as a filled `primary`
					     chip on the task row and the class card -- and for everything else
					     (a class meeting, an event, an appointment) it is a location, which
					     is not a status and was never meant to shout.

					     Routing the course-code cases through `Tag` is what makes "MGT 253"
					     the same navy chip here as it is on Home, instead of plain grey
					     words that read as a lower-priority fact than the identical chip
					     one tab over. -->
					{#if item.category === 'task' || item.category === 'assignment'}
						<Tag tone="primary">{item.detail}</Tag>
					{:else}
						<span class="truncate text-3xs text-muted-ink">{item.detail}</span>
					{/if}
				{/if}

				{#if item.label}
					<span class="rounded-xs bg-sunken px-1.5 py-0.5 text-3xs text-muted-ink">
						{item.label}
					</span>
				{/if}
			</span>
		{/if}
	</span>

	<span class="flex shrink-0 items-center gap-1.5 self-start">
		<!-- Urgent is suppressed once done, upstream in the merge, so this pill and
		     a strike-through can never appear together.

		     Through `Tag` rather than hand-rolled: urgent is a STATUS, and the app
		     has one status chip. The Next version built its own span with
		     `bg-urgent text-white`, which is a second urgent chip that would drift
		     from the first the moment either was tuned. -->
		{#if item.urgent}
			<Tag tone="urgent">{messages.calendar.row.urgent}</Tag>
		{/if}

		<!-- The category tag is deliberately NOT a `Tag` tone. There are eleven
		     categories against a handful of status tones, and `categoryTag` is the
		     one place hues are used categorically rather than as status -- see the
		     note on `categoryDot` in `schedule.ts`. Every one is paired with its
		     written label, right here. -->
		<span class={cn('rounded-xs px-1.5 py-0.5 text-3xs', categoryTag[item.category])}>
			{categoryLabel[item.category].toLowerCase()}
		</span>

		<!-- The details control, LAST in the strip and right-anchored with it.
		     A conditional control appearing at the leading edge of a right-anchored
		     group is the one arrangement that does not move anything already on
		     screen — the same rule TaskRow's control strip follows.

		     Its accessible name carries the title. "Details" on every row means a
		     screen reader hears the same word twelve times with no way to tell which
		     row it is on. -->
		{#if onOpen}
			<button
				type="button"
				onclick={(event) => {
					/*
					 * Focus the trigger before opening, so the dialog has somewhere
					 * definite to put focus back.
					 *
					 * `focusTrap` restores to whatever held focus at mount, and a POINTER
					 * press does not reliably leave focus on a button — Chrome does it,
					 * Safari on macOS does not. Without this, a mouse user closing the
					 * dialog lands on `<body>` and the next Tab starts at the top of the
					 * page, which is the failure focus restoration exists to prevent.
					 * Keyboard users already have it focused; this costs them nothing.
					 */
					event.currentTarget.focus();
					onOpen(item);
				}}
				aria-label={messages.calendar.detail.open(item.title)}
				class="shrink-0 rounded-xs p-1 text-muted-ink transition-colors duration-(--motion-fast) ease-standard hover:bg-surface hover:text-ink"
			>
				<Info aria-hidden="true" class="size-3.5" />
			</button>
		{/if}
	</span>
	</div>
{/if}
