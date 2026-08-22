<script lang="ts">
	import { untrack } from 'svelte';
	import SlidersHorizontal from '@lucide/svelte/icons/sliders-horizontal';

	import AddItemForm from '$lib/components/calendar/AddItemForm.svelte';
	import AgendaView from '$lib/components/calendar/AgendaView.svelte';
	import CalendarHeader from '$lib/components/calendar/CalendarHeader.svelte';
	import DayEventsSection from '$lib/components/calendar/DayEventsSection.svelte';
	import DayGroupToggle from '$lib/components/calendar/DayGroupToggle.svelte';
	import DaySection from '$lib/components/calendar/DaySection.svelte';
	import ItemDetail from '$lib/components/calendar/ItemDetail.svelte';
	import KeyBar from '$lib/components/calendar/KeyBar.svelte';
	import MiniCalendar from '$lib/components/calendar/MiniCalendar.svelte';
	import ViewSwitcher from '$lib/components/calendar/ViewSwitcher.svelte';
	import WeekView from '$lib/components/calendar/WeekView.svelte';
	import { arrangeDay, squareGroupsFor } from '$lib/calendarDay';
	import { agendaRange, visibleUndatedTodos } from '$lib/calendarViews';
	import { calendarPrefs } from '$lib/calendarPrefs';
	import { mergedSchedule } from '$lib/calendarSources';
	import { ignoredEvents } from '$lib/ignoredEvents';
	import { messages } from '$lib/messages';
	import { cn } from '$lib/utils';
	import {
		allLabels,
		eventItemsForDay,
		filterSchedule,
		fromDayKey,
		itemsForDay,
		nextUpItem,
		personalItemsForDay,
		scheduleItemsForDay,
		type ScheduleData,
		type ScheduleItem
	} from '$lib/schedule';
	import { tickItem } from '$lib/tickItem';
	import type { Task } from '$lib/data';

	/**
	 * The Calendar page's one stateful node.
	 *
	 * Everything the student is committed to, everything they set themselves, and
	 * everything they could opt into -- on one page, filterable.
	 *
	 * Three rules hold this together:
	 *
	 *  1. **ONE filter, applied once.** `filterSchedule` runs on the whole
	 *     `ScheduleData` before anything renders, so the month dots and the day
	 *     lists are reading the same rows. The old failure -- a dot on a day with
	 *     no row beneath it -- becomes structurally impossible rather than
	 *     something to remember. If a view added later needs filtered data, give
	 *     it this result; do not filter again downstream.
	 *
	 *  2. **ONE `selectedKey`.** Every view that lands here reads and writes it,
	 *     so switching view will never lose the student's place.
	 *
	 *  3. **The clock is the server's.** `nowMinutes` arrives as a prop. Nothing
	 *     in this subtree asks the browser what time it is -- see the note in
	 *     `+page.server.ts` for why the sanctioned client read was declined.
	 *
	 * ## Complete as of 7c
	 *
	 * 7a built the spine (month grid, the selected day, its non-event items), 7b
	 * added the other two views and the filter bar, and 7c adds the three editing
	 * surfaces: `ItemDetail`, `AddItemForm` and `DayEventsSection`. `detail` was
	 * declared in 7a and written by nothing; this is what writes it.
	 *
	 * ## The day figure and the rows beneath it now agree
	 *
	 * `CalendarHeader`'s figure counts EVERYTHING on the day, events included. For
	 * two phases that meant a day could read "12" above ten rows, because nothing
	 * rendered the events. Mounting `DayEventsSection` closes that: every category
	 * the figure counts has a section under it, all fed from the same `filtered`.
	 */
	let {
		data,
		tasks,
		todayKey,
		nowMinutes
	}: {
		data: ScheduleData;
		/** The server's task rows. Merged here, on the client, never upstream. */
		tasks: Task[];
		todayKey: string;
		/** Minutes past midnight at the server's instant. */
		nowMinutes: number;
	} = $props();

	const copy = messages.calendar;

	/**
	 * The Key's disclosure.
	 *
	 * Closed by default, which is the whole point — as a permanent column it was
	 * paying full-time rent to be a legend. NOT persisted: `calendarPrefs` carries
	 * the filter itself, which must survive a navigation, but whether the panel
	 * that edits it happens to be open is a momentary thing, like the calendar's
	 * selected day.
	 */
	let keyOpen = $state(false);

	/** Named once so `aria-controls` and the panel cannot drift. */
	const KEY_PANEL_ID = 'calendar-key-panel';

	/*
	 * Both seeded from `todayKey` and then owned outright.
	 *
	 * `untrack` says out loud what the seeding means: the prop is the INITIAL
	 * value, not a source this state follows. Without it svelte-check warns that
	 * only the initial value is captured, and it is right to ask -- the answer just
	 * happens to be "yes, deliberately". A student who selects the 4th and leaves
	 * the tab open past midnight keeps the 4th selected; the grid's "today" ring
	 * reads `todayKey` directly and moves on its own.
	 */
	let selectedKey = $state(untrack(() => todayKey));
	let monthKey = $state(untrack(() => `${todayKey.slice(0, 7)}-01`));
	/**
	 * The item whose detail dialog is open. Null when there is none.
	 *
	 * A SNAPSHOT of the row, not a subscription to it, and the dialog is written
	 * to know that: the two things it can change -- the label and the urgent flag
	 * -- are read live from their stores rather than off this object. See the note
	 * in `ItemDetail`.
	 *
	 * One slot, so opening a second dialog replaces the first. There is no way to
	 * open two, and stacking modals over a page this dense would leave a student
	 * with two Escape presses to guess at.
	 */
	let detail = $state<ScheduleItem | null>(null);

	const prefs = $derived(calendarPrefs());

	/**
	 * How many filters are ON, across BOTH dimensions.
	 *
	 * This is what the closed trigger shows, and it is the reason closing the panel
	 * does not hide an active filter. Streams and labels are counted separately and
	 * added — never merged into one list, which is the rule `KeyBar` exists to
	 * enforce. `KeyBar` computes the same figure for its own heading; both read the
	 * same two prefs fields, so they cannot disagree.
	 *
	 * Declared AFTER `prefs` because a `$derived` body is still ordinary
	 * block-scoped TypeScript — reading a `const` above its declaration is an
	 * error even though the read only happens later at runtime.
	 */
	const hiddenCount = $derived(prefs.hidden.length + (prefs.hiddenLabels?.length ?? 0));

	/*
	 * The merge, then the filter, in that order and once each.
	 *
	 * `mergedSchedule` folds the student's own tasks, to-dos and custom events
	 * onto the server's rows -- it reads nine stores, all of which are empty until
	 * `hydrateStores()` has run, so the server and the first client render both
	 * see "no personal items" and the student's rows land on the render after
	 * mount. That is correct rather than broken: un-personalised, not wrong.
	 *
	 * A plain `$derived` and no memo. React needed `useMemo` over nine
	 * dependencies here; Svelte tracks the signals the expression actually reads,
	 * so there is no dependency array to keep in step with the body.
	 */
	const merged = $derived(mergedSchedule(data, tasks));

	/**
	 * Ignored ids, in the ONE key space both surfaces share.
	 *
	 * These are raw `Event.id`s -- the store keys on exactly what Home writes and
	 * normalises nothing, and `isVisible` strips the calendar's own `evt-` prefix
	 * off an item id to match against them. So ignoring an event on Home hides it
	 * here and the reverse, which is what the store's headline has always claimed
	 * and did not do until Phase 7a. See `ignoredEvents.ts` and the cross-surface
	 * test in `calendarStores.spec.ts`.
	 */
	const ignoredEventIds = $derived(Object.keys(ignoredEvents()));

	/** THE one filter application. Everything below reads this. */
	const filtered = $derived(
		filterSchedule(merged.data, {
			hidden: prefs.hidden,
			hiddenLabels: prefs.hiddenLabels,
			showDone: prefs.showDone,
			urgentOnly: prefs.urgentOnly,
			ignoredEventIds,
			showIgnored: prefs.showIgnored
		})
	);

	/**
	 * Every label in use, for the key to render — from the UNFILTERED merge.
	 *
	 * Load-bearing, and the kind of line that gets "tidied" into a bug. If the
	 * labels came from `filtered`, switching a label off would remove its own chip
	 * from the key and there would be no way to switch it back on.
	 */
	const labels = $derived(allLabels(merged.data));

	/**
	 * The agenda's thirty days, anchored on TODAY rather than on the selection.
	 *
	 * The agenda answers "what is coming up". An anchor that moved with the
	 * selection would answer a different question every time a student touched the
	 * month grid. See `agendaRange`.
	 */
	const agendaDays = $derived(agendaRange(todayKey));

	/**
	 * Undated to-dos that survive the filter.
	 *
	 * `filterSchedule` cannot reach these — they are not in `ScheduleData`, because
	 * they have no day to be in — so the two dimensions that CAN apply to them are
	 * applied here by the same rules. `urgentOnly` hides all of them, for the exact
	 * reason `filterSchedule` drops recurring classes under the same switch: none of
	 * them can carry the flag, and a filter that visibly skips one section reads as
	 * broken. Nothing in `filterSchedule` changed.
	 */
	const visibleTodos = $derived(
		visibleUndatedTodos(merged.undatedTodos, {
			showDone: prefs.showDone,
			urgentOnly: prefs.urgentOnly
		})
	);

	const dayItems = $derived(itemsForDay(filtered, selectedKey));
	const schedule = $derived(scheduleItemsForDay(filtered, selectedKey));
	const personal = $derived(personalItemsForDay(filtered, selectedKey));
	/*
	 * The third slice, and the one that closes the day-figure gap.
	 *
	 * `dayItems` has always contained these -- they count toward the header's
	 * figure and they dot the month grid -- and from 7c they have a section of
	 * their own beneath it. Same `filtered` as the other two, so an ignored event
	 * hidden from the grid is hidden from here by the same decision, made once.
	 */
	const events = $derived(eventItemsForDay(filtered, selectedKey));

	const isToday = $derived(selectedKey === todayKey);

	/*
	 * The day's heading, formatted from a day key built out of local parts.
	 *
	 * One of the client-side `toLocaleDateString` calls CONVENTIONS.md accepts by
	 * name: the day is chosen in the browser, so no server render could have
	 * pre-formatted it, and what varies is locale wording rather than which day it
	 * is.
	 */
	const heading = $derived(
		fromDayKey(selectedKey).toLocaleDateString('en-US', {
			weekday: 'long',
			month: 'long',
			day: 'numeric'
		})
	);

	/*
	 * "Next up" only means anything relative to a clock, and only on today. On any
	 * other day the first timed item is the honest answer, which is what passing 0
	 * produces -- `nextUpItem` takes `now` as a parameter precisely so this
	 * decision belongs to the caller.
	 */
	const nextUp = $derived(nextUpItem(dayItems, isToday ? nowMinutes : 0));

	/**
	 * The square strip and the day's groups, both from `$lib/calendarDay`.
	 *
	 * Extracted rather than written here because nothing in this file can be
	 * tested -- the suite runs in Node with no jsdom -- and both of these have a
	 * branch that has been got wrong before. The concatenation below is the one to
	 * watch: `schedule` and `personal` are two filtered slices of an
	 * already-sorted day, and two sorted lists joined end to end are not sorted,
	 * so `arrangeDay` sorts again.
	 */
	const squares = $derived(squareGroupsFor(schedule, personal));
	const dayGroups = $derived(
		arrangeDay([...schedule, ...personal], prefs.dayGroupBy, copy.day.chronological)
	);

	/*
	 * One live region, mounted always, only its text swapped. A region created and
	 * populated in the same tick announces unreliably, and two regions talk over
	 * each other.
	 *
	 * All three sections, as of 7c. The events count was held back for two phases
	 * because announcing "2 to register for" above a page with no register controls
	 * on it is a promise the page does not keep; the section exists now, so the
	 * sentence is true again.
	 */
	const announcement = $derived(
		copy.header.announcement(heading, schedule.length, personal.length, events.length)
	);

	function select(dayKey: string) {
		selectedKey = dayKey;
		// Selecting a day from an adjacent month pulls the view onto that month, so
		// the selection is never off-screen.
		const dayMonth = `${dayKey.slice(0, 7)}-01`;
		if (dayMonth !== monthKey) monthKey = dayMonth;
	}

	/*
	 * No third argument and no lookup. The item carries its own source row --
	 * `mergedSchedule` attached the resolved `Task` or `QuickItem` -- and
	 * `tickItem` dispatches on that. The version that sliced a prefix off the id
	 * and searched an array silently missed every self-added task and every
	 * undated to-do. See CONVENTIONS.md.
	 */
	const onTick = (item: ScheduleItem, done: boolean) => tickItem(item, done);

	/**
	 * Open the dialog on a row.
	 *
	 * The whole writer for `detail`. Handed to every row in every view except the
	 * week column, which has no room for the control and whose job is shape rather
	 * than action -- selecting the day there drops the student into the day panel,
	 * where the same row has both.
	 */
	const onOpen = (item: ScheduleItem) => (detail = item);
</script>

<!--
	The selected day's panel: its summary, then its items.

	A SNIPPET because two views render it — month below the grid, week below the
	columns — and only agenda replaces it. The Next source expressed that as
	`view === "agenda" ? <Agenda/> : <dayPanel/>`, which reads as "agenda is the
	odd one out" and hides that the panel is shared. Written twice it would be two
	things to keep in step; written once it cannot drift.

	Keyed on the day, so the whole panel replays its entrance when the selection
	changes. The global reduced-motion rule collapses the duration, so it simply
	appears for anyone who asked for that.
-->
{#snippet dayPanel()}
	{#key selectedKey}
		<div class="animate-rise space-y-3">
			<CalendarHeader {heading} {isToday} items={dayItems} {nextUp} {squares} />

			<!--
				The day, by type. Groups run in DAY_GROUPS order -- classes, then what
				is due, then what the student set themselves, then booked time -- which
				is the order a day gets planned in rather than the order things happen.
				`time` collapses all of it into one chronological list for the other
				reading.
			-->
			<section aria-labelledby={copy.day.headingId} class="space-y-3">
				<div class="flex items-baseline justify-between gap-2">
					<h2 id={copy.day.headingId} class="thrive-eyebrow">{copy.day.eyebrow}</h2>
					<DayGroupToggle mode={prefs.dayGroupBy} />
				</div>

				{#if dayGroups.length === 0}
					<div data-tone="sunken" class="thrive-panel">
						<p class="text-xs text-muted-ink">{copy.day.empty}</p>
					</div>
				{:else}
					{#each dayGroups as group (group.key)}
						<DaySection
							id={`day-${group.key}`}
							title={group.heading}
							items={group.items}
							{onTick}
							{onOpen}
						/>
					{/each}
				{/if}
			</section>

			<!-- Adding sits BETWEEN the day and the events, and that order is the
			     argument: everything above is the student's own day, everything below
			     is what someone else is putting on. The add form belongs to the first
			     of those. -->
			<AddItemForm dayKey={selectedKey} />

			<DayEventsSection items={events} />
		</div>
	{/key}
{/snippet}

<!-- The agenda, rendered from one place so the week fallback and the agenda view
     itself cannot drift apart. -->
{#snippet agenda()}
	<AgendaView
		data={filtered}
		dayKeys={agendaDays}
		mode={prefs.groupBy}
		undatedTodos={visibleTodos}
		{onTick}
		{onOpen}
	/>
{/snippet}

<!--
	ONE HEADER ROW, AND THE KEY BEHIND A DISCLOSURE.

	Three things used to sit above the grid: an eyebrow, a 30px title with a
	subtitle, and the view switcher on a line of its own — and then the Key held a
	third of the remaining width permanently. The month grid's top edge was at 202px
	on a 1052px laptop and it was 927px wide.

	Now the page name, the view switcher and the Key's trigger share one row, and
	the grid is full width beneath it.

	## The Key is a disclosure, and what that costs

	It is a legend AND a filter, and as a permanent 18rem column it was paying
	full-time rent to be a legend. Behind a button it costs one row.

	**This is the one change here that makes something less discoverable**, so it is
	worth being straight about it: a panel you can see is more discoverable than a
	button you have to press. Three things make the trade acceptable rather than
	merely cheaper —

	  1. The trigger says what it opens, in words, and carries a COUNT when any
	     filter is on, so a hidden stream is never invisible while the panel is shut.
	  2. Nothing about reading the month depends on the legend. Every dot carries a
	     `title`, every cell's accessible name lists what is on the day in words, and
	     every row in the day panel below carries its own labelled tag. The legend
	     explains a colour that is never the only cue.
	  3. It is a real `<button>` with `aria-expanded` and `aria-controls`, and the
	     panel is inside an `{#if}` — so collapsed means absent from the DOM and from
	     the tab order rather than merely invisible. Same shape as the nav rail's
	     group.

	No filter was removed, nothing was flattened, and the two dimensions inside
	`KeyBar` are untouched.
-->
<div class="w-full">
	<p aria-live="polite" class="sr-only">{announcement}</p>

	<div class="space-y-3">
		<!-- The one header row. `items-start` because the switcher wraps its own
		     controls at narrow widths and the title should stay on the top line. -->
		<div class="flex flex-wrap items-start justify-between gap-2">
			<h1 class="text-xl font-bold text-ink">{copy.title}</h1>

			<div class="flex flex-wrap items-center gap-2">
				<ViewSwitcher {prefs} />

				<button
					type="button"
					aria-expanded={keyOpen}
					aria-controls={KEY_PANEL_ID}
					onclick={() => (keyOpen = !keyOpen)}
					class="inline-flex min-h-11 items-center gap-1.5 rounded-sm border border-line bg-surface px-2.5 text-2xs font-medium text-body transition-colors duration-(--motion-fast) ease-standard hover:border-line-strong hover:bg-primary-soft hover:text-primary-hover lg:min-h-9"
				>
					<SlidersHorizontal aria-hidden="true" class="size-3.5 shrink-0" />
					{copy.keyToggle}
					{#if hiddenCount > 0}
						<!-- The count is what stops a closed panel hiding an active filter.
						     A value, so it takes the numeric face. -->
						<span class="thrive-numeric text-3xs text-primary">
							{copy.keyToggleCount(hiddenCount)}
						</span>
					{/if}
				</button>
			</div>
		</div>

		{#if keyOpen}
			<div id={KEY_PANEL_ID}>
				<KeyBar {prefs} {labels} ignoredEventCount={ignoredEventIds.length} />
			</div>
		{/if}

	{#if prefs.view === 'agenda'}
		{@render agenda()}
	{:else if prefs.view === 'week'}
		<!--
			THE WEEK-TO-AGENDA FALLBACK, AT 48REM, AND IT IS CSS.

			Seven columns on a 375px screen gives each one about 50px, which is
			narrower than the word "Assignment". So below `md` (48rem) the week grid
			does not render and the agenda answers instead.

			48rem, NOT the 40rem the Next comment named. Measured at 40rem the columns
			came out 71px, where "MGT 142 · Machine Learning for Business" reads as
			three short stacks rather than a phrase — technically clamped, not actually
			legible. The owner's call, and the right one: anything that narrow falls
			back to the agenda perfectly well, so the breakpoint should sit where the
			columns are readable rather than where they merely fit.

			Done with two media-gated wrappers rather than a `matchMedia` read, and
			that is a decision. CONVENTIONS is explicit that a viewport question CSS
			can answer belongs in CSS — the JS form is reserved for cases with no CSS
			equivalent, like moving FOCUS. A `matchMedia` read would also have to
			guess during SSR, so one width of student would watch the wrong view paint
			and get replaced a beat after hydration, which is the quiet hydration drift
			the same file warns about.

			What it costs, stated rather than discovered: both subtrees are built, so a
			desktop pays for one `groupAgenda` over thirty days it will not show and a
			phone pays for one week grid. Both are cheap, and `display: none` keeps the
			hidden one out of the accessibility tree, so nothing is announced twice.
		-->
		<div class="hidden space-y-3 md:block">
			<WeekView data={filtered} {selectedKey} {todayKey} onSelect={select} />
			{@render dayPanel()}
		</div>

		<div class="space-y-3 md:hidden">
			<!-- Said out loud. The switcher still shows "week" selected, because that
			     IS the student's choice and it will be honoured the moment the screen
			     is wide enough — so the page owes them a reason for showing something
			     else rather than appearing to have ignored the click. -->
			<p data-tone="sunken" class="thrive-panel text-xs text-muted-ink">
				{copy.week.fallbackNote}
			</p>
			{@render agenda()}
		</div>
	{:else}
		<MiniCalendar
			data={filtered}
			{todayKey}
			{selectedKey}
			onSelect={select}
			{monthKey}
			onMonthChange={(next) => (monthKey = next)}
			showTodayButton
			size="comfortable"
		/>
		{@render dayPanel()}
	{/if}

	</div>

	<!--
		The dialog, mounted OUTSIDE the view branches.

		Here rather than inside `dayPanel`, for two reasons. The agenda has no day
		panel and its rows can open one too. And `dayPanel` is keyed on
		`selectedKey`, so a dialog inside it would be torn down and rebuilt the
		instant the student changed day — which is a thing they can do while it is
		open, from a keyboard, since the month grid is still behind the scrim.

		No portal and no `<svelte:boundary>`. The scrim is `position: fixed`, so it
		escapes every ancestor's box without needing to escape the tree; the shell
		sets no transform or filter, which are the only things that would trap it.
	-->
	{#if detail}
		<ItemDetail item={detail} onClose={() => (detail = null)} />
	{/if}
</div>
