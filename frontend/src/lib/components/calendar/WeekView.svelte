<script lang="ts">
	import ItemRow from '$lib/components/calendar/ItemRow.svelte';
	import { messages } from '$lib/messages';
	import { fromDayKey, itemsForDay, weekGrid, type ScheduleData } from '$lib/schedule';
	import { cn } from '$lib/utils';

	/**
	 * Seven days as columns.
	 *
	 * ## It is not rendered below 48rem, and the parent decides that
	 *
	 * Seven columns on a 375px screen gives each one about 50px, which is narrower
	 * than the word "Assignment". A view that technically renders and cannot be
	 * read is worse than a view that admits it does not fit, so the parent shows
	 * the agenda instead at that width.
	 *
	 * **The Next source only ever claimed this.** Its `CalendarView` rendered
	 * `WeekView` at every width, and this component papered over the narrow case
	 * with `overflow-x-auto` and `min-w-[42rem]` — a horizontal scroll, which is
	 * the thing its own doc comment called the wrong answer. The fallback exists
	 * here for the first time; see `CalendarView` for how.
	 *
	 * Which is why there is NO min-width and no horizontal scroll here. The
	 * fallback is what guarantees the room, so a scrollbar would mean the fallback
	 * was doing nothing.
	 *
	 * ## Why 48rem rather than the 40rem the Next comment named
	 *
	 * Because the columns were measured. At 40rem they came out 71px, where a
	 * three-line clamp holds "MGT 142 · Machine Learning for Business" without
	 * overflowing and it still reads as three short stacks rather than a phrase.
	 * "Fits" and "is legible" are different bars, and this view exists to be read.
	 * At 48rem the columns are ~86px. **If a title ever stops being legible in a
	 * column, the breakpoint is the thing to change — never a min-width, which
	 * would put the scroll back.**
	 *
	 * ## Compact rows, and no checkboxes
	 *
	 * `ItemRow compact` stacks the time above the title and clamps to three lines.
	 * It carries no checkbox on purpose: a 17px control in an ~85px column under a
	 * three-line title is a mis-tap waiting to happen. The week view answers "what
	 * does my week look like"; selecting a day drops the student into the day panel
	 * where the same rows are fully tickable.
	 */
	let {
		data,
		selectedKey,
		todayKey,
		onSelect
	}: {
		data: ScheduleData;
		selectedKey: string;
		todayKey: string;
		onSelect: (dayKey: string) => void;
	} = $props();

	const copy = messages.calendar.week;

	const days = $derived(weekGrid(selectedKey));
</script>

<div class="thrive-panel p-2">
	<div class="grid grid-cols-7 gap-1.5">
		{#each days as dayKey (dayKey)}
			{@const date = fromDayKey(dayKey)}
			{@const items = itemsForDay(data, dayKey)}
			{@const isToday = dayKey === todayKey}
			{@const isSelected = dayKey === selectedKey}

			<!-- A hairline between columns. Without it the stacked rows in adjacent
			     days run together and read as one wrapped sentence. -->
			<div class="min-w-0 border-l border-hairline pl-1.5 first:border-l-0">
				<button
					type="button"
					onclick={() => onSelect(dayKey)}
					aria-current={isToday ? 'date' : undefined}
					aria-pressed={isSelected}
					aria-label={copy.selectDay(
						date.toLocaleDateString('en-US', {
							weekday: 'long',
							month: 'long',
							day: 'numeric'
						})
					)}
					class={cn(
						'mb-1.5 w-full rounded-sm px-1 py-1.5 text-left transition-colors duration-(--motion-fast) ease-standard',
						isSelected ? 'bg-sunken' : 'hover:bg-sunken'
					)}
				>
					<!-- The weekday abbreviation is a word, so no numeric treatment. One
					     of the client-side `toLocaleDateString` calls CONVENTIONS accepts
					     by name: the week is chosen in the browser, and what varies is
					     locale wording rather than which day it is. -->
					<span class="block text-3xs text-muted-ink uppercase">
						{date.toLocaleDateString('en-US', { weekday: 'short' })}
					</span>
					<!-- The date IS a value, and seven of them sit in a row, so tabular
					     figures are the whole point. -->
					<span class={cn('thrive-numeric block text-sm', isToday ? 'text-indigo' : 'text-ink')}>
						{date.getDate()}
					</span>
				</button>

				{#if items.length === 0}
					<p aria-hidden="true" class="px-1 text-3xs text-faint">{copy.emptyDay}</p>
				{:else}
					<ul class="space-y-1">
						{#each items as item (item.id)}
							<li><ItemRow {item} compact /></li>
						{/each}
					</ul>
				{/if}
			</div>
		{/each}
	</div>
</div>
