<script lang="ts">
	import CalendarPlus from '@lucide/svelte/icons/calendar-plus';
	import Check from '@lucide/svelte/icons/check';
	import MapPin from '@lucide/svelte/icons/map-pin';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import X from '@lucide/svelte/icons/x';

	import Button from '$lib/components/ui/Button.svelte';
	import IgnoreButton from '$lib/components/ui/IgnoreButton.svelte';
	import IgnoreUndoBar from '$lib/components/ui/IgnoreUndoBar.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import UnIgnoreButton from '$lib/components/ui/UnIgnoreButton.svelte';
	import Tag from '$lib/components/ui/Tag.svelte';
	import { dayEventRows, joinedCount } from '$lib/calendarEvents';
	import { downloadItemIcs } from '$lib/ics';
	import { ignoredEvents } from '$lib/ignoredEvents';
	import { ignoreEvents } from '$lib/ignoreUndo.svelte';
	import { messages } from '$lib/messages';
	import { showToast } from '$lib/toast.svelte';
	import { categoryLabel, categoryTag, type ScheduleItem } from '$lib/schedule';
	import { eventJoins, setEventJoined } from '$lib/userEdits.svelte';
	import { cn } from '$lib/utils';

	/**
	 * "Happening, register": the optional things on this day.
	 *
	 * ITS OWN SECTION, not a group in the day list, because opting in is a
	 * different act from ticking off. A class is something you are already
	 * committed to and an assignment is something you owe; these are invitations,
	 * and they carry a blurb, a "for you" badge and three controls that none of
	 * the other rows have. Folding them into a generic `DaySection` would throw
	 * all of that away to gain a consistency nobody asked for.
	 *
	 * ## This closes the day-figure gap
	 *
	 * Until now the header counted a day's events and nothing rendered them, so a
	 * day could read "12" above ten rows. That was accepted in 7a because the
	 * alternatives were worse — filtering events out of the count would also have
	 * taken them off the month grid, breaking "one filter, applied once". With
	 * this section mounted, every item the figure counts has a row beneath it.
	 *
	 * ## Nothing is sent anywhere
	 *
	 * "Count me in" is local intent, stored in this browser. "Add to calendar"
	 * downloads an .ics the student chooses to import. THRIVE never writes to a
	 * real calendar and never tells an organiser anything, and each joined row
	 * says so rather than leaving it to be assumed.
	 *
	 * ## Joining states the fact; leaving is a separate control
	 *
	 * It used to be one toggle: the button read "You're in" and pressing it again
	 * removed you, which nobody could discover. A control whose off-switch is
	 * invisible is a control students are afraid to press. So "You're in" is a
	 * statement and "Remove from my list" is the action.
	 *
	 * ## The id it stores under
	 *
	 * Both stores this section writes key on the RAW `Event.id`, and the calendar
	 * holds a calendar item id. `dayEventRows` sheds the prefix ONCE, at that
	 * boundary, and hands back the raw id alongside each row — see
	 * `calendarEvents.ts` for why that conversion is a tested module rather than
	 * four lines in here.
	 */
	let {
		items
	}: {
		/** This day's event rows, already filtered upstream. */
		items: ScheduleItem[];
	} = $props();

	const copy = messages.calendar.events;
	/* The register vocabulary itself. Shared with Home, which renders the identical
	   words for the identical act against the same store. */
	const shared = messages.common.events;

	/*
	 * Both stores read here, once, and passed into a pure function.
	 *
	 * Reading them in the component is what makes the section reactive; doing the
	 * arithmetic outside it is what makes the arithmetic testable.
	 */
	const rows = $derived(dayEventRows(items, eventJoins(), ignoredEvents()));
	const joined = $derived(joinedCount(rows));

	/** The standing ignore offer, if any. One slot, app-wide — see `ignoreUndo`. */
	const undo = $derived(ignoreEvents.undo);
</script>

<section aria-labelledby={copy.headingId} class="thrive-panel">
	<SectionHeading
		as="h3"
		id={copy.headingId}
		title={copy.title}
		prefix={copy.prefix}
		count={items.length === 0 ? undefined : copy.joinedCount(joined, items.length)}
	/>

	<!-- Same place and shape as the task list's undo: at the TOP of the section
	     rather than following the row, because the row it refers to has gone and a
	     strip anchored to a gap moves as the list reflows. -->
	{#if undo}
		<div class="mt-3">
			<IgnoreUndoBar title={undo.title} onUndo={() => ignoreEvents.applyUndo()} />
		</div>
	{/if}

	{#if items.length === 0}
		<p class="mt-3 text-xs text-muted-ink">{copy.empty}</p>
	{:else}
		<ul class="mt-3 space-y-2">
			{#each rows as row (row.item.id)}
				<li
					data-ignored={row.ignored ? 'true' : undefined}
					class={cn(
						'rounded-lg border border-hairline p-2.5',
						/*
						 * A revealed-but-ignored row reads de-emphasised through means that
						 * already exist: the sunken fill, and the same 0.62 `.thrive-row`
						 * uses for a done task. No new token, and no new idea about what
						 * "receded" looks like.
						 */
						row.ignored && 'bg-sunken opacity-60'
					)}
				>
					<div class="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
						<!-- Clamped, not truncated. At 320px this title has about 170px and
						     "Employer Coffee Chat: Fintech Analytics" needs roughly 290.
						     There is vertical room; an ellipsis buys nothing and leaves no
						     way to recover the full string. -->
						<h4 class="line-clamp-2 min-w-40 flex-1 text-sm font-medium break-words text-ink">
							{row.item.title}
						</h4>

						<span class="flex shrink-0 flex-wrap items-center gap-1.5">
							<span
								class={cn('rounded-xs px-1.5 py-0.5 text-3xs', categoryTag[row.item.category])}
							>
								{categoryLabel[row.item.category].toLowerCase()}
							</span>
							{#if row.item.relevantToGoal}
								<Tag tone="primary">
									<Sparkles aria-hidden="true" class="size-3" />
									{shared.relevanceBadge}
								</Tag>
							{/if}
						</span>
					</div>

					<p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-3xs text-muted-ink">
						<!-- A time is a value. -->
						<span class="thrive-numeric">{row.item.timeLabel}</span>
						{#if row.item.detail}
							<span aria-hidden="true">·</span>
							<span class="inline-flex min-w-0 items-center gap-1">
								<MapPin aria-hidden="true" class="size-3 shrink-0" />
								<span class="truncate">{row.item.detail}</span>
							</span>
						{/if}
					</p>

					{#if row.item.description}
						<p class="mt-1.5 max-w-measure text-xs text-body">{row.item.description}</p>
					{/if}

					<div class="mt-2.5 flex flex-wrap items-center gap-2">
						{#if row.joined}
							<!-- A statement of fact, so it is not a button. Rendering it as one
							     is what made the old toggle undiscoverable. -->
							<span
								class="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-on-track px-2.5 text-2xs font-medium text-on-primary"
							>
								<Check aria-hidden="true" class="size-3" />
								{shared.joined}
							</span>

							<Button
								class="min-h-11"
								variant="danger"
								onclick={() => setEventJoined(row.eventId, false)}
							>
								<X aria-hidden="true" class="size-3" />
								{shared.leave}
								<span class="sr-only">{shared.subject(row.item.title)}</span>
							</Button>
						{:else}
							<!-- `min-h-11` rather than the button's own height: these were about
							     26px tall in the source, well under a comfortable touch target on
							     the one surface whose whole job is signing up for things. -->
							<Button class="min-h-11" onclick={() => setEventJoined(row.eventId, true)}>
								{shared.countMeIn}
								<span class="sr-only">{shared.subject(row.item.title)}</span>
							</Button>
						{/if}

						<Button
							class="min-h-11"
							disabled={!row.item.startISO}
							onclick={() => downloadItemIcs(row.item)}
						>
							<CalendarPlus aria-hidden="true" class="size-3" />
							{shared.addToCalendar}
							<span class="sr-only">{shared.subject(row.item.title)}</span>
						</Button>

						<!-- Separated by an auto margin rather than sitting flush as a third
						     equal button. Ignore is not a peer of these two. -->
						{#if row.ignored}
							<UnIgnoreButton
								title={row.item.title}
								onUnIgnore={() => ignoreEvents.unIgnore(row.eventId)}
								class="ms-auto"
							/>
						{:else}
							<IgnoreButton
								title={row.item.title}
								onIgnore={() => {
									ignoreEvents.ignore(row.eventId, row.item.title);
									showToast(messages.home.events.ignored(row.item.title));
								}}
								class="ms-auto"
							/>
						{/if}
					</div>

					<!-- Mounted always, filled conditionally. A live region created and
					     populated in the same tick is announced unreliably. -->
					<p aria-live="polite" class={cn('text-3xs text-muted-ink', row.joined && 'mt-2')}>
						{row.joined ? shared.joinedNote : ''}
					</p>
				</li>
			{/each}
		</ul>
	{/if}
</section>
