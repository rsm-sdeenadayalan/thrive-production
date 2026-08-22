<script lang="ts">
	import CalendarOff from '@lucide/svelte/icons/calendar-off';

	import { showsRowDate, undatedTodoItem } from '$lib/calendarViews';
	import ItemRow from '$lib/components/calendar/ItemRow.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { messages } from '$lib/messages';
	import type { QuickItem } from '$lib/quickList';
	import {
		fromDayKey,
		groupAgenda,
		type GroupMode,
		type ScheduleData,
		type ScheduleItem
	} from '$lib/schedule';

	/**
	 * A flat, grouped list across a date range.
	 *
	 * The view that actually answers "show me everything". The month grid shows
	 * density and the week shows shape, but only a list can be grouped by type or
	 * by course — and **only a list can carry undated items**, which is the whole
	 * reason this view exists rather than being a nicer month grid.
	 *
	 * The range is decided by the caller. See `agendaRange` in
	 * `$lib/calendarViews` for why it is anchored on today rather than on the
	 * selected day.
	 *
	 * ## Rows name their own date unless the heading already does
	 *
	 * Grouped by day, the heading IS the date and repeating it on every row is
	 * noise. Grouped by type or by course, a row's time alone does not say which
	 * of thirty days it falls on — and a time without a date, in a list spanning a
	 * month, is the wrong half of the information rather than less of it.
	 *
	 * The Next version rendered all three groupings identically and had this gap.
	 * `showsRowDate` is the decision, in the pure layer where it is tested.
	 */
	let {
		data,
		dayKeys,
		mode,
		undatedTodos,
		onTick,
		onOpen
	}: {
		data: ScheduleData;
		dayKeys: string[];
		mode: GroupMode;
		/**
		 * To-dos the student never dated, already filtered by the caller.
		 *
		 * Whole `QuickItem`s rather than flattened fields, because the row that gets
		 * built from each one has to carry it — that attachment is the only reason
		 * its checkbox can write anywhere. See `undatedTodoItem`.
		 */
		undatedTodos: QuickItem[];
		onTick?: (item: ScheduleItem, done: boolean) => void;
		/**
		 * Passed straight through to every row, dated and undated alike.
		 *
		 * The agenda is the ONLY place an undated to-do is reachable, so it is also
		 * the only place one can be labelled or flagged urgent. Withholding the
		 * control from that section would make a whole class of row uneditable.
		 */
		onOpen?: (item: ScheduleItem) => void;
	} = $props();

	const copy = messages.calendar.agenda;

	const groups = $derived(groupAgenda(data, dayKeys, mode));
	const withRowDates = $derived(showsRowDate(mode));

	/**
	 * A row's date, formatted.
	 *
	 * Short on purpose — "Sat, Aug 22" beside a course code, not the group
	 * heading's full "Saturday, August 22". Another of the client-side
	 * `toLocaleDateString` calls CONVENTIONS accepts by name: the range is walked
	 * in the browser from a day key built out of local parts, so what varies is
	 * locale wording rather than which day it is.
	 */
	function rowDate(dayKey: string): string {
		return fromDayKey(dayKey).toLocaleDateString('en-US', {
			weekday: 'short',
			month: 'short',
			day: 'numeric'
		});
	}
</script>

{#if groups.length === 0 && undatedTodos.length === 0}
	<div class="thrive-panel">
		<EmptyState icon={CalendarOff} message={copy.empty} />
	</div>
{:else}
	<div class="space-y-3">
		{#each groups as group (group.key)}
			<section aria-labelledby={`agenda-${group.key}`} class="thrive-panel">
				<div class="flex items-baseline justify-between gap-2">
					<h3 id={`agenda-${group.key}`} class="text-sm font-medium text-ink">
						{group.heading}
					</h3>
					<span class="thrive-numeric text-3xs text-muted-ink">{group.items.length}</span>
				</div>

				<ul class="mt-1.5 space-y-0.5">
					{#each group.items as item (`${item.dayKey}-${item.id}`)}
						<!-- Keyed on day AND id: `groupAgenda` expands recurring classes
						     across the range, so one class meeting appears on several days
						     with the same item id. Keying on the id alone would collapse a
						     term's worth of meetings into one row. -->
						<li>
							<ItemRow
								{item}
								dateLabel={withRowDates ? rowDate(item.dayKey) : undefined}
								{onTick}
								{onOpen}
							/>
						</li>
					{/each}
				</ul>
			</section>
		{/each}

		<!--
			Undated to-dos have no place on a grid and would be invisible forever if
			the agenda did not show them. Their own section rather than mixed into a
			day, because pretending they are due today would be a lie the student did
			not tell.
		-->
		{#if undatedTodos.length > 0}
			<section aria-labelledby="agenda-undated" class="thrive-panel">
				<div class="flex items-baseline justify-between gap-2">
					<h3 id="agenda-undated" class="text-sm font-medium text-ink">
						{copy.undatedTitle}
					</h3>
					<span class="thrive-numeric text-3xs text-muted-ink">{undatedTodos.length}</span>
				</div>
				<p class="mt-0.5 text-3xs text-muted-ink">{copy.undatedHint}</p>

				<ul class="mt-1.5 space-y-0.5">
					{#each undatedTodos as todo (todo.id)}
						<li><ItemRow item={undatedTodoItem(todo)} {onTick} {onOpen} /></li>
					{/each}
				</ul>
			</section>
		{/if}
	</div>
{/if}
