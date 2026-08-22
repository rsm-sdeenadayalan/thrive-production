<script lang="ts">
	import { tick } from 'svelte';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	import Button from '$lib/components/ui/Button.svelte';
	import { messages } from '$lib/messages';
	import {
		addDays,
		categoriesForDay,
		categoryDot,
		categoryLabel,
		fromDayKey,
		monthGrid,
		type ScheduleData
	} from '$lib/schedule';
	import { cn } from '$lib/utils';

	/**
	 * The month grid.
	 *
	 * Up to three category dots per day plus a "+n" for the rest, a roving
	 * tabindex with real grid navigation, and a selection that pulls the view onto
	 * whatever month it lands in.
	 *
	 * ## The two dates this formats on the client, and why it has to
	 *
	 * The month label and each cell's accessible date are built with
	 * `toLocaleDateString` HERE rather than on the server, which is a documented
	 * exception to "components never see a raw timestamp" and not a lapse.
	 *
	 * The grid pages to any month with no round trip -- that is the whole reason
	 * classes stay as weekday rules -- so there is no set of months the server
	 * could pre-format. What it formats is a day key already built from local
	 * parts by `fromDayKey`, so the only thing that can differ between server and
	 * client is locale wording, never which day it is. CONVENTIONS.md lists this
	 * alongside the day heading and the agenda's group headings.
	 *
	 * ## `size` and `showTodayButton`
	 *
	 * Kept from the Next component although this phase has one call site. Both
	 * exist because the same grid is meant to serve as a compact picker beside a
	 * booking panel later, and a component that has to be edited to be reused in
	 * the way it was designed for is not reusable.
	 *
	 * ## TWO CALL SITES NOW, and both are interactive
	 *
	 * `/calendar` and `/appointments`' "Your month". They differ only in what they
	 * write to: the calendar's selection drives its own day panel, the
	 * appointments one drives "Your day" and nothing else. That is the caller's
	 * business, not this component's -- it takes `selectedKey` and `onSelect` and
	 * has no opinion about who is listening.
	 *
	 * ## A `readOnly` mode existed for one commit and is gone
	 *
	 * "Your month" was briefly a non-interactive reference: cells rendered as
	 * `<div>`s through `<svelte:element>`, no roles, no tabindex, no hover, the grid
	 * `aria-hidden`. It was removed because a month grid with dots INVITES a click
	 * and a grid that refuses one reads as broken, which is a stronger signal than
	 * any caption saying otherwise.
	 *
	 * Worth recording rather than just deleting, because the reasoning still holds
	 * in the other direction: **if a cell is not a control, it must not be an
	 * element that looks like one** -- and the fix there was to change the element,
	 * not to drop the handler, since a focusable cell that does nothing is worse
	 * than no cell. If a genuinely decorative month is ever wanted, that is the
	 * shape to go back to.
	 */
	let {
		data,
		todayKey,
		selectedKey,
		onSelect,
		monthKey,
		onMonthChange,
		showTodayButton = false,
		size = 'compact'
	}: {
		data: ScheduleData;
		/** "YYYY-MM-DD" for the real today, decided by the server. */
		todayKey: string;
		selectedKey: string;
		onSelect: (dayKey: string) => void;
		/** First of the visible month, "YYYY-MM-DD". */
		monthKey: string;
		onMonthChange: (monthKey: string) => void;
		/** Adds a "Today" jump. Wanted when this is the page's main calendar. */
		showTodayButton?: boolean;
		/** `comfortable` gives taller cells for use as a primary calendar. */
		size?: 'compact' | 'comfortable';
	} = $props();

	/** Days in a week, and the width of one grid row. */
	const WEEK_LENGTH = 7;

	/**
	 * Dots shown before collapsing into "+n".
	 *
	 * A cell is under 40px wide at 320px, so the counter has to buy its own room:
	 * once there is overflow, one dot is given up for it rather than letting the
	 * row spill past the cell edge.
	 */
	const MAX_DOTS = 3;

	const { grid: copy } = messages.calendar;

	let gridEl = $state<HTMLDivElement | null>(null);

	const roomy = $derived(size === 'comfortable');
	const cursor = $derived(fromDayKey(monthKey));
	const year = $derived(cursor.getFullYear());
	const month = $derived(cursor.getMonth());

	const days = $derived(monthGrid(year, month));
	const monthLabel = $derived(
		cursor.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
	);

	/**
	 * Weeks, not a flat run of 42 cells.
	 *
	 * `role="grid"` needs its cells inside rows; a bare list of gridcells gives
	 * assistive tech no way to map a day onto a week, so table navigation walks
	 * off the end of the month instead of down a column.
	 */
	const weeks = $derived(
		Array.from({ length: days.length / WEEK_LENGTH }, (_, index) =>
			days.slice(index * WEEK_LENGTH, index * WEEK_LENGTH + WEEK_LENGTH)
		)
	);

	/**
	 * The single tab stop for the roving tabindex.
	 *
	 * Paging the month moves the grid without moving the selection, so on a month
	 * the selection is not part of, no rendered cell would hold `tabindex=0` and
	 * the entire grid would drop out of the tab order. Falling back to the first
	 * day of the visible month keeps it reachable.
	 */
	const tabStopKey = $derived(
		days.includes(selectedKey)
			? selectedKey
			: (days.find((key) => fromDayKey(key).getMonth() === month) ?? days[0])
	);

	/** "YYYY-MM-01" for whichever month a date belongs to. */
	function monthKeyOf(date: Date): string {
		return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`;
	}

	function shiftMonth(delta: number) {
		onMonthChange(monthKeyOf(new Date(year, month + delta, 1)));
	}

	/**
	 * Focus a day cell once the month it belongs to has been committed.
	 *
	 * `await tick()` rather than the Next version's `requestAnimationFrame`: the
	 * cell may not exist until Svelte has flushed the month change, and a tick is
	 * exactly that flush rather than a guess at how long it takes.
	 *
	 * NOT an arrival. `arriveAtRow` is for landing a student ON A ROW they asked
	 * about, and it marks what it lands on; this is navigation inside one widget,
	 * which CONVENTIONS.md carves out explicitly. Marking every arrow-key press
	 * would turn a wayfinding cue into a cursor.
	 */
	async function focusDay(selector: string) {
		await tick();
		gridEl?.querySelector<HTMLButtonElement>(selector)?.focus();
	}

	function goToday() {
		onMonthChange(`${todayKey.slice(0, 7)}-01`);
		onSelect(todayKey);
		focusDay(`[data-day="${todayKey}"]`);
	}

	/**
	 * Arrow keys walk the grid a day or a week at a time, the way a date picker is
	 * expected to behave. Moving past the edge of the month pulls the view along,
	 * so the focused day is always visible.
	 */
	function onKeyDown(event: KeyboardEvent) {
		/*
		 * Paging is handled first and cancels the event itself. In the Next version
		 * the shared `preventDefault()` sat after this branch, which returned
		 * early -- so paging a month also scrolled the document.
		 */
		if (event.key === 'PageUp' || event.key === 'PageDown') {
			event.preventDefault();
			shiftMonth(event.key === 'PageUp' ? -1 : 1);
			// The month swap unmounts the focused cell, which would drop focus to
			// the body and end the keyboard session after a single page. Land on
			// whichever cell the new month made its tab stop.
			focusDay('[data-day][tabindex="0"]');
			return;
		}

		const moves: Record<string, number> = {
			ArrowLeft: -1,
			ArrowRight: 1,
			ArrowUp: -WEEK_LENGTH,
			ArrowDown: WEEK_LENGTH
		};

		let target: string | null = null;

		if (event.key in moves) {
			target = addDays(selectedKey, moves[event.key]);
		} else if (event.key === 'Home') {
			target = addDays(selectedKey, -fromDayKey(selectedKey).getDay());
		} else if (event.key === 'End') {
			target = addDays(selectedKey, 6 - fromDayKey(selectedKey).getDay());
		}

		if (!target) return;
		event.preventDefault();

		const targetDate = fromDayKey(target);
		if (targetDate.getMonth() !== month || targetDate.getFullYear() !== year) {
			onMonthChange(monthKeyOf(targetDate));
		}

		onSelect(target);

		// Focus follows selection, so the roving tabindex lands where the user is.
		focusDay(`[data-day="${target}"]`);
	}

	/** A cell's whole accessible name: the date, how much is on it, and today. */
	function labelFor(dayKey: string, count: number): string {
		const date = fromDayKey(dayKey).toLocaleDateString('en-US', {
			month: 'long',
			day: 'numeric',
			year: 'numeric'
		});
		const items = count === 0 ? copy.noItems : copy.itemCount(count);
		return copy.dayLabel(date, items, dayKey === todayKey);
	}
</script>

<div class="thrive-panel p-0">
	<!-- The header sits on its own band, the same shape every other panel in
	     THRIVE uses, so the month reads as a label on a box rather than a line of
	     text above a grid. A 1px hairline, not the Next source's `border-b-2`:
	     under this direction a decorative edge is 1px. -->
	<div
		class="flex flex-wrap items-center justify-between gap-2 rounded-t-xl border-b border-line bg-sunken px-2.5 py-2"
	>
		<h2 id="mini-cal-label" class="min-w-0 text-base font-medium text-ink">{monthLabel}</h2>

		<!-- Each control is a real 44px box rather than a small button wearing an
		     invisible 44px pseudo-element. The old shape overlapped its neighbour by
		     12px and the overlap resolved to whichever button painted last -- so
		     part of the visible "previous" chevron paged FORWARD. `gap-2` keeps 8px
		     of clear air between the targets. -->
		<div class="flex shrink-0 items-center gap-2">
			{#if showTodayButton}
				<Button onclick={goToday} class="h-11">{copy.today}</Button>
			{/if}
			<Button onclick={() => shiftMonth(-1)} aria-label={copy.previousMonth} class="size-11">
				<ChevronLeft aria-hidden="true" class="size-4" />
			</Button>
			<Button onclick={() => shiftMonth(1)} aria-label={copy.nextMonth} class="size-11">
				<ChevronRight aria-hidden="true" class="size-4" />
			</Button>
		</div>
	</div>

	<!-- Padding is one step off the panel edge only: every pixel spent here is
	     taken off seven day cells, and the cells are the thing that has to stay
	     tappable. What is left is enough for the focus ring to sit in. -->
	<div
		bind:this={gridEl}
		role="grid"
		aria-labelledby="mini-cal-label"
		onkeydown={onKeyDown}
		class="p-1"
		tabindex="-1"
	>
		<div role="row" class="grid grid-cols-7 pb-1">
			{#each copy.weekdayInitials as initial, index (copy.weekdayNames[index])}
				<!-- The role goes on a div and the abbreviation sits inside it. The Next
				     version put `role="columnheader"` on the `<abbr>` itself, which is a
				     grid role on a non-interactive element -- svelte-check rejects it,
				     and it is right to: the header is a cell, and `<abbr>` is the
				     shortening of the word inside that cell. Two jobs, two elements. -->
				<div role="columnheader" class="text-center">
					<abbr
						title={copy.weekdayNames[index]}
						class="text-3xs text-muted-ink uppercase no-underline"
					>
						{initial}
					</abbr>
				</div>
			{/each}
		</div>

		<!-- The rules between days are the container showing through the gaps.
		     Drawing them as borders on the cells instead would double every
		     interior line and leave the grid's outer edge uneven. -->
		<div role="rowgroup" class="flex flex-col gap-0.5 border border-line bg-line">
			{#each weeks as week (week[0])}
				<div role="row" class="grid grid-cols-7 gap-0.5">
					{#each week as dayKey (dayKey)}
						{@const date = fromDayKey(dayKey)}
						{@const inMonth = date.getMonth() === month}
						{@const isToday = dayKey === todayKey}
						{@const isSelected = dayKey === selectedKey}
						{@const categories = categoriesForDay(data, dayKey)}
						{@const shown = categories.length > MAX_DOTS ? MAX_DOTS - 1 : MAX_DOTS}
						{@const overflow = categories.length - shown}

						<button
							type="button"
							role="gridcell"
							data-day={dayKey}
							aria-label={labelFor(dayKey, categories.length)}
							aria-selected={isSelected}
							aria-current={isToday ? 'date' : undefined}
							tabindex={dayKey === tabStopKey ? 0 : -1}
							onclick={() => onSelect(dayKey)}
							class={cn(
								'relative flex flex-col items-center justify-center gap-1',
								roomy ? 'h-11' : 'h-9',
								'transition-colors duration-(--motion-fast) ease-standard',
								// "Not this month" is said with the cell's FILL, not with a
								// faded number. These are real buttons, and dimming the digit
								// to half muted put it at 2.1:1 -- the number stays at full
								// muted ink and the recessed tone carries the meaning.
								inMonth ? 'bg-surface text-body' : 'bg-sunken text-muted-ink',
								!isSelected && 'hover:bg-primary-soft',
								isSelected && 'bg-primary text-on-primary',
								// Today is marked by weight AND a ring, not hue alone, so it
								// survives grayscale and stays visible while selected.
								isToday && !isSelected && 'font-bold text-primary',
								isToday &&
									(isSelected
										? 'ring-2 ring-on-primary ring-inset'
										: 'ring-2 ring-primary ring-inset')
							)}
						>
							<!-- A day number is a value. `.thrive-numeric` carries the face and
							     tabular figures, so 1 and 11 sit in the same column. -->
							<span class={cn('thrive-numeric leading-none', roomy ? 'text-sm' : 'text-2xs')}>
								{date.getDate()}
							</span>

							<!-- The dots repeat what the cell's accessible name already says in
							     words, so nothing here rests on colour alone. -->
							<!-- The row reserves the dot's height whether or not there are any,
						     so a day with nothing on it is the same height as a day with three
						     and the grid cannot reflow as the filter changes. Both sizes come
						     from ONE token: a `size-cal-dot` paired with a hand-picked
						     wrapper height would clip the moment either was retuned. -->
						<span class="flex h-cal-dot items-center gap-0.5" aria-hidden="true">
								{#each categories.slice(0, shown) as category (category)}
									<span
										title={categoryLabel[category]}
										class={cn(
											'size-cal-dot rounded-pill',
											isSelected ? 'bg-on-primary' : categoryDot[category]
										)}
									></span>
								{/each}
								{#if overflow > 0}
									<span
										class={cn(
											'thrive-numeric text-3xs leading-none',
											isSelected ? 'text-on-primary' : 'text-muted-ink'
										)}
									>
										{copy.overflow(overflow)}
									</span>
								{/if}
							</span>
						</button>
					{/each}
				</div>
			{/each}
		</div>
	</div>
</div>
