<script lang="ts">
	import ItemRow from '$lib/components/calendar/ItemRow.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import type { ScheduleItem } from '$lib/schedule';
	import { isTickable } from '$lib/tickItem';

	/**
	 * One titled group of items on the selected day.
	 *
	 * There will be several of these on a day -- classes, what is due, what the
	 * student set themselves, booked time -- and near-copies of a section shell is
	 * exactly how they start to disagree about padding, heading level and how a
	 * row looks.
	 */
	let {
		id,
		title,
		items,
		onTick,
		onOpen
	}: {
		id: string;
		title: string;
		items: ScheduleItem[];
		onTick?: (item: ScheduleItem, done: boolean) => void;
		/** Passed straight through to the row. See `ItemRow`. */
		onOpen?: (item: ScheduleItem) => void;
	} = $props();

	/*
	 * THE COUNT IS OVER TICKABLE ITEMS, NOT OVER THE TOTAL. This was a real bug,
	 * it was fixed, and it must not come back.
	 *
	 * It used to read `done / items.length`, so a group holding one finished task
	 * and two classes rendered "1/3" and told the student three things could be
	 * ticked. Two of them could not be ticked by anyone: a class is not a thing
	 * you complete.
	 *
	 * `isTickable` is the same question the row's checkbox asks -- is a writable
	 * source row attached -- so the fraction's denominator is exactly the number
	 * of checkboxes rendered below it. Anything else lets the heading and the list
	 * disagree.
	 *
	 * A group with nothing tickable falls back to a bare total, because "0/0" is
	 * not information.
	 */
	const tickables = $derived(items.filter((entry) => isTickable(entry)));
	const done = $derived(tickables.filter((entry) => entry.done === true).length);
	const count = $derived(
		tickables.length > 0 ? `${done}/${tickables.length}` : `${items.length}`
	);
</script>

<!-- Empty groups are dropped by `groupDayItems` before they reach here, so a
     section that renders always has something in it and needs no empty state. -->
{#if items.length > 0}
	<section aria-labelledby={id} class="thrive-panel">
		<SectionHeading as="h3" {id} {title} {count} />

		<ul class="mt-2 space-y-0.5">
			{#each items as item (item.id)}
				<li>
					<ItemRow {item} {onTick} {onOpen} />
				</li>
			{/each}
		</ul>
	</section>
{/if}
