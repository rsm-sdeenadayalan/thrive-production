<script lang="ts">
	import { untrack } from 'svelte';

	import type { ServiceView } from '$lib/appointmentsView';
	import { firstBookableDay } from '$lib/availability';
	import BookingPanel from '$lib/components/appointments/BookingPanel.svelte';
	import MonthBrowser from '$lib/components/appointments/MonthBrowser.svelte';
	import MyDayPane from '$lib/components/appointments/MyDayPane.svelte';
	import ServiceCard from '$lib/components/appointments/ServiceCard.svelte';
	import type { ScheduleData } from '$lib/schedule';

	/**
	 * The booking surface's one stateful node.
	 *
	 * Service cards across the top, then two columns: the booking panel on the
	 * left, and on the right the student's month with the day it selects beneath
	 * it.
	 *
	 * ```
	 *  [ card ]        [ card ]
	 *  ───────────────────────────────────
	 *  Pick a day      │  Your month
	 *  [Today][Tue]…   │  [ month grid ]   <- the control
	 *  Meeting type    │
	 *  Available times │  Your day         <- the result
	 *  [reason]        │  9:30  MGT 100
	 *  [Confirm]       │  14:00 Advising
	 * ```
	 *
	 * ## The result goes UNDER the control, as of this commit
	 *
	 * "Your day" was on top and the grid beneath it, which put the thing being
	 * changed above the thing that changes it. At 1512 the pane ran 358-503px and
	 * the grid 629-876px, so a click landed 270px below the pane it moved; on an
	 * 800px-tall laptop the grid's last row was already past the fold, so scrolling
	 * down to click scrolled the answer off the screen. The reported symptom was
	 * "clicking does nothing", and this arrangement is most of why.
	 *
	 * This is the original arrangement. Phase 8 replaced the chip strip with a
	 * month calendar in the right column, which put the day picker across the page
	 * from the times and read backwards; a later pass moved it left as a day list.
	 * Both are reverted. The chips are the picker and they sit at the top of the
	 * panel, where the first decision belongs.
	 *
	 * The month grid survives on this page as a second, narrower question — "what
	 * does my month look like" — and it is a real control. See `MonthBrowser`.
	 *
	 * ## FOUR pieces of state, and two of them are days
	 *
	 *  - `activeId` — which advisor. The cards set it, the panel renders from it.
	 *  - `bookingDay` — the day being BOOKED. Drives the chips and the times.
	 *  - `browseDay` — the day being LOOKED AT. Drives "Your day".
	 *  - `browseMonth` — which month the grid shows. A view, not a choice.
	 *
	 * ## Why two days rather than one
	 *
	 * Booking and browsing are different questions, and the month grid made that
	 * visible. A student comparing next Thursday against their classes has not
	 * changed their mind about booking Tuesday, so the grid must not move the chips.
	 *
	 * **The coupling runs one way.** Choosing a CHIP moves both, because seeing what
	 * a slot would collide with is the entire reason "Your day" is on this page.
	 * Choosing a day in the grid moves only `browseDay`. One direction, stated here
	 * because a reader will reasonably wonder why the two are not symmetrical.
	 *
	 * They start equal, so the page opens coherent rather than pointing two panes at
	 * two different days for no reason.
	 *
	 * ## The initial day is derived, not "today"
	 *
	 * `firstBookableDay` picks the soonest published day with something free. Today
	 * is usually the first chip and is frequently empty by mid-afternoon, so opening
	 * there would show an empty times list beside chips that do have room.
	 *
	 * ## Switching advisor resets the form
	 *
	 * `BookingPanel` is keyed on the advisor id, so choosing the other service
	 * remounts it and clears the meeting type, the chosen time and the reason.
	 * Carrying a half-written reason across to a different person would be wrong.
	 */
	let {
		services,
		data,
		todayKey
	}: {
		services: ServiceView[];
		data: ScheduleData;
		todayKey: string;
	} = $props();

	let activeId = $state<string | null>(null);
	let bookingDay = $state<string | null>(null);
	let browseDay = $state<string | null>(null);
	/**
	 * Seeded from today's month, then owned by the student.
	 *
	 * `untrack` states the latch out loud, the same way `ItemDetail` latches its
	 * row: this is the STARTING month, not a mirror of `todayKey`. An
	 * `invalidateAll` after a booking re-runs `load` and hands the same `todayKey`
	 * back, and a month the student has paged to must survive that rather than
	 * snapping home.
	 */
	let browseMonth = $state(untrack(() => monthOf(todayKey)));

	const active = $derived(
		services.find((service) => service.advisor.id === activeId) ?? null
	);

	/** The booked day's finished labels, so the panel formats nothing. */
	const activeDay = $derived(
		active?.days.find((day) => day.dayKey === bookingDay) ?? null
	);

	const dayLabel = $derived(
		activeDay ? `${activeDay.weekdayLabel}, ${activeDay.dateLabel}` : ''
	);

	/**
	 * "YYYY-MM-01" for whichever month a day belongs to.
	 *
	 * String slicing rather than `Date` arithmetic: a day key is already local
	 * calendar parts, so taking its first seven characters cannot shift a month the
	 * way parsing and re-formatting an instant can.
	 */
	function monthOf(dayKey: string): string {
		return `${dayKey.slice(0, 7)}-01`;
	}

	function toggle(service: ServiceView) {
		if (activeId === service.advisor.id) {
			activeId = null;
			return;
		}

		activeId = service.advisor.id;
		bookingDay = firstBookableDay(
			service.days.map((day) => day.dayKey),
			service.openByDay
		);
		// They start equal, so the page opens with both panes on one day.
		browseDay = bookingDay;
		browseMonth = monthOf(browseDay ?? todayKey);
	}

	/**
	 * A CHIP was pressed: move both.
	 *
	 * The grid follows the booking day here, and pulls its month along, so choosing
	 * a chip for a day in the next month does not leave the grid on this one.
	 */
	function chooseBookingDay(dayKey: string) {
		bookingDay = dayKey;
		browseDay = dayKey;
		browseMonth = monthOf(dayKey);
	}

	/** A GRID CELL was pressed: move only what is being looked at. */
	function chooseBrowseDay(dayKey: string) {
		browseDay = dayKey;
	}
</script>

<div class="space-y-4 lg:space-y-3">
	<div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:gap-3">
		{#each services as service (service.advisor.id)}
			<ServiceCard
				{service}
				selected={service.advisor.id === activeId}
				onBook={() => toggle(service)}
			/>
		{/each}
	</div>

	{#if active}
		<!--
			Stacks below `lg`: the panel first, then the month, then the day it
			selects. Control before result at every width, so the vertical order is
			the same one the eye follows and there is no arrangement that only works
			on a wide screen.
		-->
		<div class="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-3">
			<section class="thrive-panel min-w-0 p-3 lg:p-2.5">
				{#key active.advisor.id}
					<BookingPanel
						service={active}
						dayKey={bookingDay}
						{dayLabel}
						onSelectDay={chooseBookingDay}
						onClose={() => (activeId = null)}
					/>
				{/key}
			</section>

			<div class="min-w-0 space-y-4 lg:space-y-3">
				<MonthBrowser
					{data}
					{todayKey}
					selectedKey={browseDay ?? ''}
					monthKey={browseMonth}
					onSelect={chooseBrowseDay}
					onMonthChange={(next) => (browseMonth = next)}
				/>

				<!-- Reads `browseDay`, which the grid ABOVE it writes and the chips also
				     write. See the note on the one-way coupling. -->
				<MyDayPane {data} dayKey={browseDay} {todayKey} />
			</div>
		</div>
	{/if}
</div>
