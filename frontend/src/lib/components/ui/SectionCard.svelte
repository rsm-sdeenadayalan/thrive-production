<script lang="ts">
	import type { Snippet } from 'svelte';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	import { cn } from '$lib/utils';
	import { messages } from '$lib/messages';
	import { isBuiltRoute, isKnownRoute } from '$lib/nav';

	/**
	 * The standard container for a Home dashboard section.
	 *
	 * Every section on Home is one of these, which is what makes the grid read as
	 * one calm surface instead of four differently-styled boxes.
	 *
	 * ## Three bands, and why the footer is outside the scroll area
	 *
	 * Header, body, footer. The body is `.thrive-card-body`, which on desktop is a
	 * fixed height that scrolls inside -- see the note on that class in `app.css`.
	 *
	 * The footer sits BELOW that region rather than inside it, and that is
	 * deliberate: the footer holds the show-more control, and a control that
	 * scrolls away with the content it controls is unreachable exactly when it is
	 * wanted. Expand a card, scroll to the bottom, and "show less" would be the
	 * one thing you could not find. Pinned, it is always one click away.
	 *
	 * It also means the card's total height is header + cap + footer, which is
	 * constant. That is what makes the grid immovable.
	 */
	let {
		title,
		description,
		href,
		linkLabel = messages.common.viewAll,
		class: className,
		children,
		meta,
		footer
	}: {
		title: string;
		/** Optional one-line framing under the title. */
		description?: string;
		/** Renders a "View all" affordance pointing at the full section. */
		href?: string;
		linkLabel?: string;
		class?: string;
		children: Snippet;
		/**
		 * Rendered inside the header band, below the title row.
		 *
		 * Exists so a card can move a fixed, always-present element OUT of its
		 * scrolling body. Tasks puts its progress bar here: in the body it cost 36
		 * of the ~190px of overhead that stood between the cap and the first task
		 * row, and it is not something a student scrolls to find.
		 */
		meta?: Snippet;
		/** Pinned below the scroll area. The show-more control lives here. */
		footer?: Snippet;
	} = $props();

	// Ties the <section> to its heading for assistive tech.
	const headingId = $derived(`section-${title.toLowerCase().replace(/\s+/g, '-')}`);

	/**
	 * The link renders only when its destination is a page that exists.
	 *
	 * Several cards point at PARKED routes, which render `PagePlaceholder` — a
	 * title and a note. A "View all" that lands there reads as broken rather than
	 * unfinished, which is worse than no link at all: the student has spent a click
	 * to learn nothing and now distrusts the next one.
	 *
	 * The test is `isBuiltRoute`, which asks `primaryNav`. **Deciding it here rather
	 * than per card is the point** — a route moving out of `parkedNav` brings every
	 * card's link back with no further edit, and no card carries its own opinion
	 * about whether its destination is ready.
	 */
	const showLink = $derived(href !== undefined && isBuiltRoute(href));

	/*
	 * An href in NEITHER nav list is a typo, not a decision, and hiding a link
	 * because of one would be exactly the silent no-op this repo treats as its
	 * worst failure mode: the card looks finished and the way out has simply gone.
	 *
	 * A warning rather than a throw. `PagePlaceholder` throws on an unknown href
	 * because it IS the page, so failing loudly costs nothing that was working;
	 * taking Home down over a "View all" would be worse than the missing link.
	 * Behind `import.meta.env.DEV`, so no gate covers it — same limitation as
	 * `arriveAtRow`'s warn, and stated for the same reason.
	 */
	$effect(() => {
		if (import.meta.env.DEV && href !== undefined && !isKnownRoute(href)) {
			console.warn(
				`SectionCard: "${title}" links to "${href}", which is in neither primaryNav ` +
					`nor parkedNav. The link is hidden. If that route exists, add it to nav.ts; ` +
					`if the href is a typo, fix it.`
			);
		}
	});
</script>

<section aria-labelledby={headingId} class={cn('thrive-panel flex flex-col p-3', className)}>
	<!-- The header sits on its own ruled band. A card with a heading, a rule and a
	     body reads as a labelled box rather than a stack of text.

	     `rounded-t-xl` matches the panel's own corner radius. The band is pulled
	     flush to the panel's edges by the negative margin above, so without this
	     its square top corners sit inside the panel's rounded ones and paint a
	     bg-sunken wedge into what should be a curve -- crisp everywhere except
	     the two corners that most read as "is this box finished". -->
	<div
		class="-mx-3 -mt-3 mb-3 shrink-0 rounded-t-xl border-b border-line bg-sunken px-3 py-2"
	>

		<!--
			`min-h-11` is a FLOOR so the band cannot shrink when the link is absent.

			The link is the only child that changes, and on mobile it is a 44px touch
			target — so on a card whose title and description are shorter than that,
			removing it would pull the header band up and move everything below.
			Measured on this fixture it is not the binding constraint (the text block
			is 53px at 375px, the link 44px), which is precisely why a floor is worth
			having: the property should hold because a rule says so, not because
			today's copy happens to be long enough.

			No floor above `lg`, deliberately. There the link is `lg:min-h-0 lg:py-1`
			at about 26px, well under any realistic title block, so a floor could only
			ever GROW a card — trading a hypothetical shrink for a real regression.
		-->
		<div class="flex min-h-11 items-start justify-between gap-3 lg:min-h-0">
		<div class="min-w-0">
			<!-- Weight at the call site: the type scale carries size only. -->
			<h2 id={headingId} class="text-lg font-bold text-ink">{title}</h2>
			{#if description}
				<p class="mt-0.5 text-xs text-muted-ink">{description}</p>
			{/if}
		</div>

		{#if showLink}
			<a
				href={href!}
				class="group inline-flex min-h-11 shrink-0 items-center gap-0.5 rounded-sm border border-line bg-surface px-2 text-3xs font-medium text-body transition-colors duration-(--motion-fast) ease-standard hover:border-primary hover:text-primary lg:min-h-0 lg:py-1"
			>
				{linkLabel}
				<ChevronRight
					aria-hidden="true"
					class="size-3 transition-transform duration-(--motion-fast) ease-standard group-hover:translate-x-0.5"
				/>
				<span class="sr-only">{messages.common.viewAllIn(title)}</span>
			</a>
		{/if}
		</div>

		{#if meta}
			<div class="mt-1.5">{@render meta()}</div>
		{/if}
	</div>

	<!-- No `flex-1` here, deliberately. This is a flex column, and `flex: 1 1 0%`
	     beats the `height` that `.thrive-card-body` sets at desktop -- the body grew
	     to its content and the cap silently did nothing. Measured, not reasoned:
	     the first run reported a 423px body against a 248px cap. -->
	<div class="thrive-card-body">
		{@render children()}
	</div>

	{#if footer}
		<div class="mt-2 shrink-0 border-t border-hairline-soft pt-2">
			{@render footer()}
		</div>
	{/if}
</section>
