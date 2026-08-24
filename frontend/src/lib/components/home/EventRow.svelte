<script lang="ts">
	import CalendarPlus from '@lucide/svelte/icons/calendar-plus';
	import Check from '@lucide/svelte/icons/check';
	import MapPin from '@lucide/svelte/icons/map-pin';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import X from '@lucide/svelte/icons/x';

	import { messages } from '$lib/messages';
	import { revealRowId } from '$lib/reveal';
	import Button from '$lib/components/ui/Button.svelte';
	import IgnoreButton from '$lib/components/ui/IgnoreButton.svelte';
	import Tag from '$lib/components/ui/Tag.svelte';
	import { downloadEventIcs } from '$lib/ics';
	import { eventJoins, isEventJoined, setEventJoined } from '$lib/userEdits.svelte';
	import { cn } from '$lib/utils';
	import type { TagTone } from '$lib/tones';
	import type { Event, EventType } from '$lib/data';

	/**
	 * One event row.
	 *
	 * Type tags say who is putting the event on, routed through `Tag` so an event
	 * origin looks like every other chip in THRIVE. "San Diego" is `civic`, the one
	 * tone reserved for categories -- it used to borrow the amber that means
	 * "watch" everywhere else, which made a city event look like a warning.
	 */
	const typeTone: Record<EventType, TagTone> = {
		career: 'primary',
		rady: 'needs-help',
		club: 'on-track',
		ucsd: 'neutral',
		sandiego: 'civic'
	};

	const typeLabel: Record<EventType, string> = {
		career: messages.eventTypes.career,
		rady: messages.eventTypes.rady,
		club: messages.eventTypes.club,
		ucsd: messages.eventTypes.ucsd,
		sandiego: messages.eventTypes.sandiego
	};

	let {
		event,
		dateBlock,
		onIgnore
	}: {
		event: Event;
		/** Pre-formatted on the server: month, day, and time. */
		dateBlock: { month: string; day: string; time: string };
		/** Omitted where the row is not dismissible. */
		onIgnore?: () => void;
	} = $props();

	/**
	 * The jump target for the "events this week" popover.
	 *
	 * Keyed on the RAW `Event.id`, the same key space the ignore store uses and the
	 * popover asks with. `tabindex="-1"` keeps the row out of the tab order while
	 * letting a jump put focus on it -- see the note in `TaskRow`.
	 */
	const rowId = $derived(revealRowId({ kind: 'event', id: event.id }));

	const copy = messages.common.events;

	/**
	 * Has the student said yes to this one?
	 *
	 * `event.id` straight into the store, with nothing done to it. Home holds an
	 * `Event`, so its id is already the raw form the store keys on; `eventIdOf` is
	 * for CALENDAR item ids and calling it here would mangle rather than normalise,
	 * because a raw event id begins with `evt-` too. Exactly the rule the ignore
	 * reader two lines of reasoning above already follows.
	 */
	const joined = $derived(isEventJoined(event.id, eventJoins()));
</script>

<!--
	The card treatment is plain utilities, not `.thrive-panel`: the panel's
	`data-flush` variant existed for a box nested inside another panel with no
	edge of its own, but this row sits in a `divide-y` list where Tailwind's
	divide-color rule (a UTILITY, same layer-priority argument as the note on
	`.thrive-panel` above) was winning over `data-flush`'s transparent border on
	three of four sides -- an accidental, cascade-order-dependent outline rather
	than a deliberate one. Every action item on Home now draws the SAME explicit
	border/radius/surface, this row included, so the outline is no longer a side
	effect of `divide-y`. See `UpcomingEvents` for the matching switch to
	`space-y-2`.
-->
<article
	id={rowId}
	tabindex="-1"
	class="flex items-start gap-2.5 rounded-lg border border-hairline bg-surface p-2 transition-colors duration-(--motion-fast) ease-standard hover:bg-bg"
>
	<!-- Date block. A calendar-tear shape reads faster than a date string. The day
	     number is a value, the month abbreviation is a word. -->
	<div
		class="grid size-11 shrink-0 place-items-center rounded-sm border border-line bg-sunken leading-none"
	>
		<span class="text-3xs text-muted-ink uppercase">{dateBlock.month}</span>
		<span class="thrive-numeric text-base text-ink">{dateBlock.day}</span>
	</div>

	<div class="min-w-0 flex-1">
		<div class="flex flex-wrap items-start justify-between gap-x-2.5 gap-y-1">
			<!-- Wraps rather than truncates: an event title is the row's subject, and
			     half of one is not a shorter version of it. `min-w-32` lets the tags
			     wrap below on a narrow row instead of crushing the title. -->
			<h3 class="line-clamp-2 min-w-32 flex-1 text-base break-words text-ink">
				{event.title}
			</h3>

			<span class="flex shrink-0 flex-wrap items-center gap-1">
				<Tag tone={typeTone[event.type]}>{typeLabel[event.type]}</Tag>

				{#if event.relevantToGoal}
					<Tag tone="primary">
						<Sparkles aria-hidden="true" class="size-3" />
						{copy.relevanceBadge}
					</Tag>
				{/if}
			</span>
		</div>

		<p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-3xs text-muted-ink">
			<!-- A time is a value. -->
			<span class="thrive-numeric">{dateBlock.time}</span>
			<span aria-hidden="true">·</span>
			<span class="inline-flex min-w-0 items-center gap-1">
				<MapPin aria-hidden="true" class="size-3 shrink-0" />
				<span class="truncate">{event.location}</span>
			</span>
		</p>

		<!--
			"Count me in" is LIVE as of the 7c follow-on. It was inert for four phases
			because the join store was keyed on the calendar item id (MIGRATION.md
			section 9 defect 13), so a write here would have landed under a key the
			calendar never reads. 7c settled that key space on the raw `Event.id`,
			which is exactly what `event.id` holds — no prefix to shed, no `eventIdOf`.
			Join here and the calendar's day shows you joined, and the reverse.

			Nothing is sent anywhere. This is local intent, stored in this browser,
			and the row says so once it is set.

			State and exit are two controls, matching `DayEventsSection` exactly. It
			used to be one toggle reading "You're in", which removed you when pressed
			again — an off-switch nobody could discover.

			"Add to calendar" is live too, and it was the last inert control in the app.
			It downloads an `.ics` the student chooses to import — THRIVE still never
			writes to a real calendar and there is no API call anywhere in this path.
			`icsFromEvent` is Home's mapper; the calendar has its own, because a
			`ScheduleItem` and an `Event` are genuinely different shapes and need
			different fallbacks. See `$lib/ics`.
		-->
		<div class="mt-1.5 flex flex-wrap items-center gap-1.5">
			{#if joined}
				<!-- A statement of fact, so it is not a button. Rendering it as one is
				     what made the old toggle undiscoverable. -->
				<span
					class="inline-flex h-8 items-center gap-1.5 rounded-md bg-on-track px-2.5 text-2xs font-medium text-on-primary"
				>
					<Check aria-hidden="true" class="size-3" />
					{copy.joined}
				</span>

				<Button size="sm" variant="danger" onclick={() => setEventJoined(event.id, false)}>
					<X aria-hidden="true" class="size-3" />
					{copy.leave}
					<span class="sr-only">{copy.subject(event.title)}</span>
				</Button>
			{:else}
				<Button size="sm" onclick={() => setEventJoined(event.id, true)}>
					{copy.countMeIn}
					<span class="sr-only">{copy.subject(event.title)}</span>
				</Button>
			{/if}

			<Button size="sm" onclick={() => downloadEventIcs(event)}>
				<CalendarPlus aria-hidden="true" class="size-3" />
				{copy.addToCalendar}
				<span class="sr-only">{copy.subject(event.title)}</span>
			</Button>

			<!-- Pushed to the far end rather than sitting flush as a third equal
			     button. At 375px the group wraps and Ignore lands on its own line,
			     which is the right outcome: it is the least important thing here. -->
			{#if onIgnore}
				<IgnoreButton title={event.title} {onIgnore} class="ms-auto" />
			{/if}
		</div>

		<!-- Mounted always, filled conditionally. A live region created and populated
		     in the same tick is announced unreliably. -->
		<p aria-live="polite" class={cn('text-3xs text-muted-ink', joined && 'mt-1.5')}>
			{joined ? copy.joinedNote : ''}
		</p>
	</div>
</article>
