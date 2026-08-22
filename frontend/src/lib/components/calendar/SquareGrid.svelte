<script module lang="ts">
	/*
	 * Re-exported, not declared here.
	 *
	 * The shapes live in `$lib/calendarDay` beside `squareGroupsFor`, the function
	 * that builds them -- a type belongs with the code that decides its values,
	 * and that code has to be in a `.ts` to be testable at all. They are exported
	 * from this component as well because this is the component they describe, so
	 * a caller building a strip has one import rather than two.
	 */
	export type { SquareCell, SquareGroup } from '$lib/calendarDay';

	/**
	 * A day's items as a strip of small squares.
	 *
	 * From the owner's reference: a run of cells, gaps clustering them into
	 * groups, filled when done, and one marked cell for the item that is next. It
	 * answers "how much is left today" in a glance, which a list of rows does not.
	 *
	 * Three states, and only two of them are about completion:
	 *
	 *   empty   pale boundary, nothing inside
	 *   done    navy fill
	 *   next    indigo outline -- RESERVED, "this is where you are now"
	 *
	 * Colour never carries the meaning alone. Every cell has a `title` and an
	 * accessible name stating the item and its state in words, and the header's
	 * "n of m done" says the same thing a third way.
	 */
</script>

<script lang="ts">
	import type { SquareCell, SquareGroup } from '$lib/calendarDay';
	import { messages } from '$lib/messages';
	import { cn } from '$lib/utils';

	let {
		groups,
		nextId,
		class: className
	}: {
		groups: SquareGroup[];
		/** The item the header calls "next up", marked here so the two agree. */
		nextId?: string | null;
		class?: string;
	} = $props();

	const total = $derived(groups.reduce((sum, group) => sum + group.cells.length, 0));

	function stateOf(cell: SquareCell): string {
		if (cell.done) return messages.calendar.header.squareDone;
		if (cell.id === nextId) return messages.calendar.header.squareNext;
		return messages.calendar.header.squareNotDone;
	}
</script>

{#if total > 0}
	<!-- `flex-wrap` rather than a fixed grid: the number of items on a day is
	     unbounded, and a hardcoded column count would either clip a busy day or
	     leave a wide gap on a quiet one. -->
	<ul
		aria-label={messages.calendar.header.squaresLabel}
		class={cn('flex flex-wrap items-center gap-x-4 gap-y-1.5', className)}
	>
		{#each groups as group (group.key)}
			<li>
				<ul class="flex flex-wrap items-center gap-1.5">
					{#each group.cells as cell (cell.id)}
						<li>
							<span
								title={cell.label}
								aria-label={messages.calendar.header.squareLabel(cell.label, stateOf(cell))}
								class={cn(
									'block size-5 rounded-sm border transition-colors duration-(--motion-fast) ease-standard',
									cell.done
										? 'border-primary bg-primary'
										: 'border-line-strong bg-surface',
									/*
									 * AN OUTLINE, NOT A RING -- MIGRATION.md section 9 defect 10
									 * built correctly rather than ported.
									 *
									 * The Next version used `ring-2 ring-indigo ring-offset-1`
									 * with no `ring-offset-color`, so it inherited Tailwind's
									 * default of white. That was right only because the strip has
									 * so far only ever sat inside a white panel; on cream, or on
									 * a sunken fill, it draws a white halo round the cell.
									 *
									 * An outline's offset region is TRANSPARENT, so it shows
									 * whatever is actually behind it and there is no colour to
									 * set or to get wrong. `.thrive-arrived` reaches for outline
									 * over ring for the same reason, and this way the two
									 * indigo markers in the app are drawn the same way.
									 */
									cell.id === nextId && 'outline-2 outline-offset-1 outline-indigo'
								)}
							></span>
						</li>
					{/each}
				</ul>
			</li>
		{/each}
	</ul>
{/if}
