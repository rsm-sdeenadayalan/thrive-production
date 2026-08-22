<script lang="ts">
	import { pageTitle } from '$lib/title';
	import { createRevealChannel, setRevealChannel } from '$lib/reveal.svelte';
	import { resolveRows } from '$lib/taskBoard';
	import { addedTasks, taskDues, taskPriorities, taskTitles } from '$lib/userEdits.svelte';
	import HomeHeader from '$lib/components/home/HomeHeader.svelte';
	import MyClasses from '$lib/components/home/MyClasses.svelte';
	import TasksCard from '$lib/components/home/TasksCard.svelte';
	import TodaysClasses from '$lib/components/home/TodaysClasses.svelte';
	import UpcomingEvents from '$lib/components/home/UpcomingEvents.svelte';
	import type { PageData } from './$types';

	/**
	 * Home.
	 *
	 * The one page the whole app is arranged around. Six providers in one
	 * `Promise.all`, every date classified in `+page.server.ts`, four cards in a
	 * 2x2 grid that fits one viewport.
	 *
	 * ## The grid
	 *
	 * `lg:grid-cols-2` over four cards IS the 2x2 -- measured as
	 * `grid-template-columns: 550px 550px` with two rows. It was already 2x2
	 * before the density pass; what pushed the second row below the fold was the
	 * header above it, not the grid.
	 *
	 * The cards are ordered so the pair a student acts on -- Tasks and today's
	 * classes -- lands in the first row, and the pair they browse lands in the
	 * second. On a phone that same order becomes the scroll order, which is the
	 * right priority either way.
	 *
	 * Each card caps its own height on desktop and scrolls inside; see
	 * `.thrive-card-body` in `app.css` for why that is a fixed height rather than a
	 * maximum. The result is that expanding any card moves nothing else.
	 *
	 * `space-y-2` rather than `space-y-3`: with the header down to one panel there
	 * are only two gaps left on this page, and 4px each is worth having.
	 *
	 * ## The page owns "reveal this row"
	 *
	 * The stat pills open a popover of the actual items behind each count, and
	 * those items jump to the row on the page -- which may be collapsed behind a
	 * "show more" in a card the popover has no business reaching into.
	 *
	 * So the channel lives HERE, at the one point that can see both the pills in
	 * the header and the cards in the grid, and it carries a request rather than
	 * state: a pill asks, and each card decides for itself whether the request is
	 * about one of its rows and whether it needs to open. Every card keeps its own
	 * collapse state and its own show-more control, unchanged. This adds a second
	 * way in, it does not take the first one away.
	 *
	 * Handed down through CONTEXT rather than as a prop. Three of the four
	 * components between here and `TaskStatPills` have no interest in reveal, and
	 * more importantly context dies with this component -- so "collapse resets on
	 * navigation" stays true because of where the channel lives rather than because
	 * something remembers to reset it.
	 *
	 * ## The page also resolves the task rows, once
	 *
	 * `resolveRows` merges the tasks the student created and applies their title,
	 * priority and due-date edits, reclassifying anything whose date moved. It runs
	 * HERE, at the one point that can see both the stat pills in the header and the
	 * Tasks card in the grid, and the same array goes to both.
	 *
	 * That is not tidiness, it is the pills' honesty. Each pill's number is
	 * `items.length` of the list it opens, counted from `due.urgency` -- so if the
	 * card resolved its own rows and the header did not, moving a due date would
	 * restyle the list while the coral pill above it went on counting the server's
	 * answer. Two views of one list, contradicting each other, which is the exact
	 * bug that moved the counting to the client in 6a. One expression, two
	 * consumers, and they cannot disagree.
	 *
	 * `data.nowISO` is the server's instant, so nothing here asks the browser what
	 * day it is -- see CONVENTIONS.md on the narrowed exception.
	 */
	let { data }: { data: PageData } = $props();

	setRevealChannel(createRevealChannel());

	const taskRows = $derived(
		resolveRows(
			data.taskItems,
			addedTasks(),
			taskTitles(),
			taskPriorities(),
			taskDues(),
			data.nowISO
		)
	);
</script>

<svelte:head><title>{pageTitle()}</title></svelte:head>

<div class="mx-auto w-full max-w-page space-y-2">
	<HomeHeader
		student={data.student}
		degree={data.degree}
		timeline={data.timeline}
		dateLabel={data.dateLabel}
		greeting={data.greeting}
		taskItems={taskRows}
		eventRows={data.eventRows}
	/>

	<div class="grid grid-cols-1 gap-2 lg:grid-cols-2">
		<TasksCard rows={taskRows} nowISO={data.nowISO} />
		<TodaysClasses rows={data.todaysClasses} dateLabel={data.dateLabel} />
		<MyClasses rows={data.courseRows} />
		<UpcomingEvents rows={data.eventRows} />
	</div>
</div>
