<script lang="ts">
	import { setCalendarPrefs } from '$lib/calendarPrefs';
	import { messages } from '$lib/messages';
	import type { DayGroupMode } from '$lib/schedule';
	import { cn } from '$lib/utils';

	/**
	 * Arrange the day by type, or as one chronological list.
	 *
	 * Both readings are legitimate and they answer different questions. Type
	 * answers "what do I owe" and is the default. Time answers "what happens
	 * next", which is a day view's older instinct and should never be more than
	 * one click away.
	 *
	 * Small and quiet on purpose: this is a preference, not a primary action, and
	 * it sits inline with the day's sections rather than up in the page chrome
	 * where it would compete with the view switcher 7b brings.
	 *
	 * Words, so DM Sans. The Next version set these in mono, which is the drift
	 * the two-face rule was tightened to stop -- "type" and "time" are not values
	 * anybody scans in a column.
	 */
	let { mode }: { mode: DayGroupMode } = $props();

	const MODES: { value: DayGroupMode; label: string }[] = [
		{ value: 'type', label: messages.calendar.day.groupByType },
		{ value: 'time', label: messages.calendar.day.groupByTime }
	];
</script>

<div role="radiogroup" aria-label={messages.calendar.day.groupByLabel} class="flex items-center gap-1">
	<span class="text-3xs text-muted-ink">{messages.calendar.day.groupByPrefix}</span>

	{#each MODES as option (option.value)}
		{@const active = mode === option.value}
		<button
			type="button"
			role="radio"
			aria-checked={active}
			onclick={() => setCalendarPrefs({ dayGroupBy: option.value })}
			class={cn(
				'rounded-xs px-1.5 py-0.5 text-3xs transition-colors duration-(--motion-fast) ease-standard',
				active ? 'bg-sunken text-ink' : 'text-muted-ink hover:text-ink'
			)}
		>
			{option.label}
		</button>
	{/each}
</div>
