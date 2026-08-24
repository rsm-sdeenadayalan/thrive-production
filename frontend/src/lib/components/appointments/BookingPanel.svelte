<script lang="ts">
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import CalendarPlus from '@lucide/svelte/icons/calendar-plus';
	import CircleCheckBig from '@lucide/svelte/icons/circle-check-big';
	import Clock from '@lucide/svelte/icons/clock';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import MapPin from '@lucide/svelte/icons/map-pin';
	import Video from '@lucide/svelte/icons/video';

	import {
		REASON_MAX,
		type AppointmentView,
		type ServiceView
	} from '$lib/appointmentsView';
	import { slotsForDay, type ModeFilter } from '$lib/availability';
	import Button from '$lib/components/ui/Button.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { downloadIcs, icsFromAppointment } from '$lib/ics';
	import { messages } from '$lib/messages';
	import { cn } from '$lib/utils';

	/**
	 * The booking form: pick a day, a meeting type, a time, say why, confirm.
	 *
	 * ## The chips are the picker again
	 *
	 * Phase 8 replaced this strip with a month calendar and the calendar was
	 * confusing, so the strip is back — one horizontal row of the five business
	 * days this advisor publishes, which is what the fixture emits and therefore
	 * what the strip can show without becoming a grid drawn in one line.
	 *
	 * **One thing from the grid work is kept:** each chip carries its open COUNT,
	 * so a student can see where to look before pressing anything. The original
	 * strip made them select a day to discover it was empty. A day whose slots are
	 * all taken says "Full" and is disabled rather than selectable-and-then-empty.
	 *
	 * ## The day is still not this component's state
	 *
	 * It is a prop, chosen in `BookingArea`, because "Your day" and the month
	 * reference beside it read the same selection. That is also what dissolved
	 * MIGRATION.md §8.5's adjust-during-render: with one owner there is nothing to
	 * reconcile, and the side effect it existed to perform — clearing the chosen
	 * slot when the day moves — is unnecessary because `selectedSlot` is derived by
	 * looking the chosen id up in THIS day's slots.
	 *
	 * ## Why a form rather than a click handler
	 *
	 * See `+page.server.ts`. Briefly: `load` re-runs after the action, which is
	 * what makes a fresh booking appear in "Your day" and in the list below it with
	 * nothing to keep in sync by hand.
	 *
	 * `use:enhance` keeps the result LOCAL rather than calling `applyAction`, so the
	 * confirmation and the error are this component's state and "Done" can simply
	 * clear them.
	 *
	 * ## A taken slot is a state, not an edge case
	 *
	 * Two people can want the same 2pm. The action returns 409 with the data
	 * layer's own sentence; this renders it in an alert and CLEARS the choice, so
	 * the student picks again from a list that has just been re-fetched rather than
	 * pressing the same dead slot twice.
	 */
	let {
		service,
		dayKey,
		dayLabel,
		onSelectDay,
		onClose
	}: {
		service: ServiceView;
		/** The chosen day, or null when every published day is full. */
		dayKey: string | null;
		/**
		 * That day in words, e.g. "Mon, Aug 24".
		 *
		 * A PROP, not formatted here. Every chip carries its finished labels from
		 * the server, so the panel takes one rather than re-deriving it — which is
		 * why this page appears nowhere on CONVENTIONS' list of accepted client-side
		 * date formats.
		 */
		dayLabel: string;
		onSelectDay: (dayKey: string) => void;
		onClose: () => void;
	} = $props();

	const copy = messages.appointments.panel;
	const confirmCopy = messages.appointments.confirmed;
	const dayCopy = messages.appointments.days;

	const MODE_FILTERS: { value: ModeFilter; label: string }[] = [
		{ value: 'any', label: copy.modeAny },
		{ value: 'in person', label: copy.modeInPerson },
		{ value: 'zoom', label: copy.modeZoom }
	];

	/**
	 * One stroke for every choice in this flow.
	 *
	 * Meeting types and times are the same kind of decision, so they are the same
	 * kind of control: a bordered box that darkens its edge when chosen rather than
	 * only tinting, which keeps the state legible in grayscale. The day rows in
	 * `DayPicker` use the same language, so all three steps look like one thing.
	 */
	const CHOICE_BASE = [
		'rounded-md border text-2xs',
		'transition-colors duration-(--motion-fast) ease-standard'
	].join(' ');

	const CHOICE_RESTING =
		'border-line bg-surface text-body hover:border-line-strong hover:bg-primary-soft hover:text-primary-hover';

	const CHOICE_ACTIVE = 'border-primary bg-primary-soft text-primary-hover';

	/** Names a control group -- the one eyebrow treatment, same as every other
	 *  small all-caps label in the app. Was its own ad-hoc uppercase combo. */
	const FIELD_LABEL = 'thrive-eyebrow mb-1.5 block';

	let mode = $state<ModeFilter>('any');
	let chosenId = $state<string | null>(null);
	let reason = $state('');
	let pending = $state(false);
	let error = $state<string | null>(null);
	let confirmed = $state<AppointmentView | null>(null);

	const daySlots = $derived(dayKey ? slotsForDay(service.slots, dayKey, mode) : []);

	/**
	 * The chosen slot, or null.
	 *
	 * Derived from THIS day's list rather than held as its own object, which is
	 * what makes the day change self-cleaning: the id survives, the lookup fails,
	 * and the confirm button disables itself. `available` is re-checked here too,
	 * so a slot that went stale between renders cannot be submitted.
	 */
	const selectedSlot = $derived(
		daySlots.find((slot) => slot.id === chosenId && slot.available) ?? null
	);

	function addToCalendar(appointment: AppointmentView) {
		downloadIcs(`thrive-${appointment.id}`, [
			icsFromAppointment(
				appointment,
				confirmCopy.icsTitle(appointment.advisorRole, appointment.advisorName)
			)
		]);
	}
</script>

{#if confirmed}
	<section aria-labelledby={confirmCopy.headingId} class="min-w-0">
		<div class="flex items-start gap-2.5">
			<!-- Teal is `on-track`, which already means "this is fine" everywhere else
			     in THRIVE. Reused rather than invented, and it is a confirmation rather
			     than an availability mark, so the no-green rule does not reach it. -->
			<span
				class="grid size-9 shrink-0 place-items-center rounded-pill border border-on-track bg-on-track-soft"
			>
				<CircleCheckBig aria-hidden="true" class="size-5 text-on-track" />
			</span>

			<div class="min-w-0">
				<h3 id={confirmCopy.headingId} class="text-lg font-bold text-ink">
					{confirmCopy.heading}
				</h3>

				<p class="mt-0.5 text-sm text-body">
					{confirmCopy.line(
						confirmed.dateLabel,
						confirmed.timeLabel,
						confirmed.advisorName
					)}
				</p>

				<p class="mt-1 flex items-center gap-1.5 text-3xs text-muted-ink">
					{#if confirmed.mode === 'zoom'}
						<Video aria-hidden="true" class="size-3 shrink-0" />
					{:else}
						<MapPin aria-hidden="true" class="size-3 shrink-0" />
					{/if}
					{confirmed.location}
				</p>

				{#if confirmed.reason}
					<p
						data-tone="sunken"
						data-flush="true"
						class="thrive-panel mt-2 px-2.5 py-1.5 text-xs text-body"
					>
						{confirmCopy.reasonQuote(confirmed.reason)}
					</p>
				{/if}

				<p class="mt-2 text-3xs text-muted-ink">{confirmCopy.note}</p>

				<div class="mt-3 flex flex-wrap gap-1.5">
					<Button variant="primary" onclick={onClose}>{confirmCopy.done}</Button>

					<!-- Downloads a file the student chooses to import. Still no calendar
					     API call anywhere in THRIVE. -->
					<Button onclick={() => confirmed && addToCalendar(confirmed)}>
						<CalendarPlus aria-hidden="true" class="size-3.5" />
						{confirmCopy.addToCalendar}
					</Button>
				</div>
			</div>
		</div>
	</section>
{:else}
	<form
		method="POST"
		action="?/book"
		class="flex min-w-0 flex-col gap-3"
		use:enhance={() => {
			pending = true;
			error = null;

			return async ({ result }) => {
				pending = false;

				if (result.type === 'success') {
					confirmed =
						(result.data as { booked?: AppointmentView } | undefined)?.booked ?? null;
					// Re-reads the server: the slot this took is now unavailable, the
					// day list's count drops, and the list below gains a row.
					await invalidateAll();
					return;
				}

				if (result.type === 'failure') {
					error = String((result.data as { error?: string } | undefined)?.error ?? '');
					// Drop the choice. The list is about to re-render from fresh data and
					// pressing the same dead slot again should not be possible.
					chosenId = null;
					await invalidateAll();
					return;
				}

				/*
				 * Anything else — a redirect, or a real error like the 403 a missing
				 * `ORIGIN` produced the first time this ran. It MUST say something:
				 * leaving this branch silent made the confirm button visibly do nothing,
				 * which is indistinguishable from a broken page.
				 */
				error = messages.appointments.errors.unexpected;
				chosenId = null;
			};
		}}
	>
		<!-- The submitted choice. A hidden field rather than a fetch body, so the
		     form is the whole request and the action needs no client to call it. -->
		<input type="hidden" name="slotId" value={selectedSlot?.id ?? ''} />

		<!--
			PICK A DAY. A horizontal strip of the days this advisor publishes.

			Each chip carries the weekday (or "Today"/"Tomorrow" where those apply),
			the date on the numeric face, and how much is open. A full day is disabled
			and says "Full" rather than being selectable and then empty.
		-->
		<fieldset>
			<legend class={FIELD_LABEL}>{dayCopy.legend}</legend>

			{#if service.days.length === 0}
				<p class="text-xs text-muted-ink">{dayCopy.empty}</p>
			{:else}
				<div class="flex flex-wrap gap-1.5">
					{#each service.days as day (day.dayKey)}
						{@const open = day.openCount > 0}
						{@const active = day.dayKey === dayKey}
						{@const state = open ? dayCopy.openCount(day.openCount) : dayCopy.fullyBooked}

						<button
							type="button"
							data-day={day.dayKey}
							data-open={day.openCount}
							disabled={!open}
							aria-pressed={active}
							aria-label={dayCopy.dayLabel(
								day.relativeLabel || day.weekdayLabel,
								day.dateLabel,
								state
							)}
							onclick={() => onSelectDay(day.dayKey)}
							class={cn(
								CHOICE_BASE,
								'flex min-h-11 min-w-18 flex-col items-center justify-center px-2.5 py-1.5',
								'disabled:cursor-not-allowed',
								active
									? 'border-line-strong bg-primary text-on-primary'
									: open
										? CHOICE_RESTING
										: 'border-line bg-sunken text-muted-ink'
							)}
						>
							<span class="font-medium">{day.relativeLabel || day.weekdayLabel}</span>
							<span
								class={cn(
									'thrive-numeric text-3xs',
									active ? 'text-on-primary' : 'text-muted-ink'
								)}
							>
								{day.dateLabel}
							</span>
							<!-- The count, kept from the month-grid work. It is what lets a
							     student see where to look before pressing anything. -->
							<span
								class={cn(
									'text-3xs',
									active ? 'text-on-primary' : open ? 'text-primary' : 'text-muted-ink'
								)}
							>
								{#if open}
									<span class="thrive-numeric">{day.openCount}</span>
									{dayCopy.openCountSuffix(day.openCount)}
								{:else}
									{dayCopy.fullyBooked}
								{/if}
							</span>
						</button>
					{/each}
				</div>
			{/if}
		</fieldset>

		<div class="min-w-0">
			<!-- Meeting type. Each slot is published as one mode or the other, so this
			     NARROWS the list rather than changing a chosen time. -->
			<fieldset>
				<legend class={FIELD_LABEL}>{copy.modeLegend}</legend>
				<div class="flex flex-wrap gap-1.5">
					{#each MODE_FILTERS as filter (filter.value)}
						{@const active = filter.value === mode}
						<button
							type="button"
							aria-pressed={active}
							onclick={() => {
								mode = filter.value;
								chosenId = null;
							}}
							class={cn(CHOICE_BASE, 'h-9 px-2.5', active ? CHOICE_ACTIVE : CHOICE_RESTING)}
						>
							{filter.label}
						</button>
					{/each}
				</div>
			</fieldset>

			<fieldset class="mt-3">
				<legend class={FIELD_LABEL}>
					{copy.timesLegend}
					{#if dayKey}
						<span class="text-muted-ink normal-case">{copy.timesFor(dayLabel)}</span>
					{/if}
				</legend>

				{#if !dayKey}
					<EmptyState icon={Clock} message={copy.noDaySelected} />
				{:else if daySlots.length === 0}
					<EmptyState icon={Clock} message={copy.noTimesForFilter} />
				{:else}
					<div class="flex flex-wrap gap-1.5">
						{#each daySlots as slot (slot.id)}
							{@const active = slot.id === chosenId}
							<button
								type="button"
								disabled={!slot.available}
								aria-pressed={active}
								title={slot.available ? undefined : copy.takenTitle}
								onclick={() => (chosenId = slot.id)}
								class={cn(
									CHOICE_BASE,
									'inline-flex h-9 items-center gap-1.5 px-2.5',
									'disabled:cursor-not-allowed disabled:line-through disabled:opacity-50',
									// The chosen time is a commitment, so it goes solid — the same
									// treatment the chosen day gets one column to the left.
									active ? 'border-line-strong bg-primary text-on-primary' : CHOICE_RESTING
								)}
							>
								{#if slot.mode === 'zoom'}
									<Video aria-hidden="true" class="size-3 shrink-0" />
								{:else}
									<MapPin aria-hidden="true" class="size-3 shrink-0" />
								{/if}
								<span class="thrive-numeric">{slot.timeLabel}</span>
								<!-- The mode and "taken" are carried by an icon and a
								     strikethrough on screen. Both are said in words here, so
								     neither rests on a glyph. -->
								<span class="sr-only">
									{copy.slotMode(slot.mode)}{slot.available ? '' : copy.slotTaken}
								</span>
							</button>
						{/each}
					</div>
				{/if}
			</fieldset>
		</div>

		<div class="min-w-0">
			<label for="booking-reason" class={FIELD_LABEL}>{copy.reasonLabel}</label>
			<textarea
				id="booking-reason"
				name="reason"
				bind:value={reason}
				maxlength={REASON_MAX}
				rows="3"
				placeholder={copy.reasonPlaceholder}
				class="w-full resize-y rounded-md border-[1.5px] border-line-strong bg-surface px-2.5 py-1.5 text-sm text-body placeholder:text-muted-ink"
			></textarea>
			<p class="thrive-numeric mt-1 text-right text-3xs text-muted-ink">
				{copy.reasonCount(reason.length, REASON_MAX)}
			</p>

			{#if error}
				<p
					role="alert"
					class="mt-2 rounded-sm border border-urgent bg-urgent-soft px-2.5 py-1.5 text-2xs text-urgent"
				>
					{error}
				</p>
			{/if}

			<div class="mt-3 flex flex-wrap items-center gap-2.5">
				<Button type="submit" variant="primary" disabled={!selectedSlot || pending}>
					{#if pending}
						<LoaderCircle aria-hidden="true" class="size-3.5 animate-spin" />
					{/if}
					{pending ? copy.confirming : copy.confirm}
				</Button>

				<p aria-live="polite" class="text-2xs text-muted-ink">
					{selectedSlot
						? copy.selected(dayLabel, selectedSlot.timeLabel, selectedSlot.mode)
						: copy.pickTime}
				</p>
			</div>
		</div>
	</form>
{/if}
