<script lang="ts">
	import { setCalendarPrefs, type CalendarPrefs } from '$lib/calendarPrefs';
	import { messages } from '$lib/messages';
	import type { CalendarViewMode } from '$lib/calendarPrefs';
	import type { GroupMode } from '$lib/schedule';
	import { cn } from '$lib/utils';

	/**
	 * Month / week / agenda, plus the grouping control the agenda needs.
	 *
	 * A `radiogroup` rather than three buttons: only one view can be active and
	 * arrow keys should move between them, which is what the role means and what
	 * the platform then provides for free.
	 *
	 * The grouping select appears in agenda ONLY. Grouping a month grid is not a
	 * thing, and offering a dead control is worse than offering none.
	 *
	 * ## Words, not values
	 *
	 * The Next version set every label here in mono. Under the tightened two-face
	 * rule "month", "week", "agenda" and "group by" are words, so they take DM
	 * Sans — this switcher is named in `app.css` as one of the exact places mono
	 * had drifted to.
	 *
	 * ## A native select, deliberately
	 *
	 * Three options, one choice, no search and no multi-select. The platform's
	 * control already handles keyboard, touch and screen readers, and on a phone it
	 * opens the OS picker. A custom listbox here would be work spent to arrive
	 * somewhere slightly worse.
	 */
	let { prefs }: { prefs: CalendarPrefs } = $props();

	const copy = messages.calendar.views;

	const VIEWS: { value: CalendarViewMode; label: string }[] = [
		{ value: 'month', label: copy.month },
		{ value: 'week', label: copy.week },
		{ value: 'agenda', label: copy.agenda }
	];

	const GROUPS: { value: GroupMode; label: string }[] = [
		{ value: 'day', label: copy.groupByDay },
		{ value: 'category', label: copy.groupByCategory },
		{ value: 'course', label: copy.groupByCourse }
	];
</script>

<div class="flex flex-wrap items-center justify-between gap-2">
	<div
		role="radiogroup"
		aria-label={copy.label}
		class="inline-flex rounded-sm border border-line bg-surface p-0.5"
	>
		{#each VIEWS as view (view.value)}
			{@const active = prefs.view === view.value}
			<button
				type="button"
				role="radio"
				aria-checked={active}
				onclick={() => setCalendarPrefs({ view: view.value })}
				class={cn(
					'min-h-11 rounded-xs px-3 text-2xs font-medium transition-colors duration-(--motion-fast) ease-standard lg:min-h-9',
					active ? 'bg-primary text-on-primary' : 'text-muted-ink hover:bg-sunken'
				)}
			>
				{view.label}
			</button>
		{/each}
	</div>

	{#if prefs.view === 'agenda'}
		<label class="flex items-center gap-2 text-2xs text-muted-ink">
			{copy.groupByLabel}
			<select
				value={prefs.groupBy}
				onchange={(event) =>
					setCalendarPrefs({ groupBy: event.currentTarget.value as GroupMode })}
				class="min-h-11 rounded-xs border border-line-strong bg-surface px-2 text-2xs text-body lg:min-h-9"
			>
				{#each GROUPS as group (group.value)}
					<option value={group.value}>{group.label}</option>
				{/each}
			</select>
		</label>
	{/if}
</div>
