<script lang="ts">
	import CalendarDays from '@lucide/svelte/icons/calendar-days';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import Clock from '@lucide/svelte/icons/clock';

	import { messages } from '$lib/messages';
	import { ignoredEvents, isEventIgnored } from '$lib/ignoredEvents';
	import { isTaskDone, taskDoneOverrides } from '$lib/userEdits.svelte';
	import { getRevealChannel } from '$lib/reveal.svelte';
	import StatPill from '$lib/components/ui/StatPill.svelte';
	import type { RevealItem } from '$lib/reveal';
	import type { EventRowData, TaskRowData } from '$lib/homeView';

	/**
	 * The three numbers that answer "is anything on fire" before reading -- and,
	 * now, the three lists behind them.
	 *
	 * ## Why these are counted here and not in the load function
	 *
	 * Because the counts have to see the student's own edits, and those live in
	 * `localStorage`. The Next server counted from `task.done` alone, which meant
	 * ticking the overdue task left the coral pill still insisting one was overdue
	 * -- the dashboard contradicting the list directly beneath it.
	 *
	 * Ignored events are excluded for exactly the same reason: the dashboard must
	 * not say five events this week while the card below shows three.
	 *
	 * The dates are still classified on the server. `TaskRowData` arrives with its
	 * urgency already decided, `EventRowData` with its date block already split and
	 * its `thisWeek` flag already answered, and nothing here touches a timestamp --
	 * what moved to the client is the COUNTING, not the clock.
	 *
	 * ## The count and the list are the same expression
	 *
	 * Each pill's number is `items.length` of the list it opens. They are not two
	 * derivations that have to be kept in agreement -- a pill saying 3 and opening
	 * a list of 2 would be the same contradiction as the server-side count, one
	 * level down. It also means a zero count has an empty list, which is what makes
	 * the pill inert rather than a button opening an empty box.
	 *
	 * ## The event ids are raw `Event.id`s
	 *
	 * Read straight off the row and passed to the ignore store and to the reveal
	 * target unchanged. No prefix handling, for the same reason as
	 * `UpcomingEvents`: this is the key space the ignore store is deliberately
	 * keyed on, and normalising an already-raw id is how a second normaliser gets
	 * added.
	 */
	let {
		items,
		eventRows
	}: {
		items: TaskRowData[];
		/** Every upcoming event, each flagged with whether it is inside the week. */
		eventRows: EventRowData[];
	} = $props();

	const reveal = getRevealChannel();

	const open = $derived(items.filter((item) => !isTaskDone(item.task, taskDoneOverrides())));

	function taskItemsFor(urgency: 'overdue' | 'today'): RevealItem[] {
		return open
			.filter((item) => item.due.urgency === urgency)
			.map((item) => ({
				target: { kind: 'task' as const, id: item.task.id },
				title: item.task.title,
				// Both already strings from the server: the due line reads as prose,
				// the countdown is a value and goes in mono.
				detail: item.due.fullLabel,
				value: item.due.countdown
			}));
	}

	const overdue = $derived(taskItemsFor('overdue'));
	const dueToday = $derived(taskItemsFor('today'));

	const eventsThisWeek = $derived(
		eventRows
			.filter((entry) => entry.thisWeek && !isEventIgnored(entry.event.id, ignoredEvents()))
			.map((entry) => ({
				target: { kind: 'event' as const, id: entry.event.id },
				title: entry.event.title,
				/*
				 * The date block's month and day, joined. Its three parts were split
				 * for the calendar-tear shape on an event row; a single line in a list
				 * wants them back together, and joining two formatted strings is not
				 * formatting a date.
				 */
				detail: `${entry.dateBlock.month} ${entry.dateBlock.day}`,
				value: entry.dateBlock.time
			}))
	);

	function jumpTo(item: RevealItem) {
		reveal.request(item.target);
	}
</script>

<div class="flex flex-wrap gap-2">
	<StatPill
		icon={CircleAlert}
		value={overdue.length}
		label={messages.home.stats.overdue}
		tone={overdue.length === 0 ? 'calm' : 'urgent'}
		items={overdue}
		onSelect={jumpTo}
		listLabel={messages.home.stats.listLabel(overdue.length, messages.home.stats.overdue)}
	/>
	<StatPill
		icon={Clock}
		value={dueToday.length}
		label={messages.home.stats.dueToday}
		tone={dueToday.length === 0 ? 'calm' : 'watch'}
		items={dueToday}
		onSelect={jumpTo}
		listLabel={messages.home.stats.listLabel(dueToday.length, messages.home.stats.dueToday)}
	/>
	<StatPill
		icon={CalendarDays}
		value={eventsThisWeek.length}
		label={messages.home.stats.eventsThisWeek}
		tone="primary"
		items={eventsThisWeek}
		onSelect={jumpTo}
		listLabel={messages.home.stats.listLabel(
			eventsThisWeek.length,
			messages.home.stats.eventsThisWeek
		)}
	/>
</div>
