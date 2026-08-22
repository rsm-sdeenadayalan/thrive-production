<script lang="ts">
	import { isActiveRoute, primaryNav } from '$lib/nav';
	import { messages } from '$lib/messages';
	import { page } from '$app/state';

	/**
	 * The three destinations, for screens with no navigation rail.
	 *
	 * ## Why this exists at all
	 *
	 * The destinations live in the NAV RAIL now, as a disclosure under Ask THRIVE.
	 * But that rail is `hidden lg:flex` — below `lg` the bottom bar takes over, and
	 * the bottom bar has four fixed slots holding the four top-level destinations.
	 * So on a phone the rail's group is not on screen, and without this there would
	 * be no way to change subject at all.
	 *
	 * `lg:hidden`, so the two never appear together and a student never sees the
	 * same three links twice.
	 *
	 * ## It reads the SAME array the rail does
	 *
	 * `primaryNav`'s Ask THRIVE children. Not a copy, not a parallel list in
	 * `messages.ts` — the children of the one nav item, found by href. So adding a
	 * fourth subject puts it in the rail, the bottom bar's lookup, and here, from
	 * one edit. That property is the whole reason `nav.ts` grew children rather
	 * than this page keeping its own list.
	 */
	const copy = messages.ask;

	const pathname = $derived(page.url.pathname);

	/**
	 * Found by href rather than by index.
	 *
	 * `primaryNav[3]` would have worked today and broken silently the first time
	 * the nav order changed — which it already has once, when eleven destinations
	 * were trimmed to four.
	 */
	const destinations = $derived(
		primaryNav.find((item) => item.href === '/ask')?.children ?? []
	);
</script>

<nav aria-label={copy.rail.destinationsHeading} class="lg:hidden">
	<p class="thrive-eyebrow mb-1.5">{copy.rail.destinationsHeading}</p>

	<!-- A row that scrolls sideways rather than wrapping to three lines. The
	     negative margin plus matching padding lets it bleed to the page gutter
	     without clipping the focus ring on the first link. -->
	<ul class="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
		{#each destinations as item (item.href)}
			{@const active = isActiveRoute(item.href, pathname)}
			{@const Icon = item.icon}

			<li class="shrink-0">
				<a
					href={item.href}
					aria-current={active ? 'page' : undefined}
					title={item.description}
					class="flex min-h-11 items-center gap-2 rounded-md border px-2.5 py-1.5 text-2xs font-medium whitespace-nowrap transition-colors duration-(--motion-fast) ease-standard
						{active
						? 'border-line-strong bg-primary text-on-primary'
						: 'border-line bg-surface text-body hover:border-line-strong hover:bg-primary-soft hover:text-primary-hover'}"
				>
					<Icon
						aria-hidden="true"
						class="size-4 shrink-0 {active ? 'text-on-primary' : 'text-muted-ink'}"
					/>
					{item.label}
				</a>
			</li>
		{/each}
	</ul>
</nav>
