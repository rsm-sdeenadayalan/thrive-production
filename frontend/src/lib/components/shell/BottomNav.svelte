<script lang="ts">
	import { page } from '$app/state';

	import { isActiveRoute, primaryNav, type NavItem } from '$lib/nav';

	/**
	 * Mobile navigation. Replaces SideRail below `lg`.
	 *
	 * One slot per destination, and there are four, so every destination is one
	 * tap away.
	 *
	 * ## The More sheet is gone (2026-08-22)
	 *
	 * It existed because nine destinations do not fit across a phone: four got a
	 * slot and the rest lived behind an overflow sheet. With four destinations
	 * total there is no overflow, so the sheet, its scrim, its
	 * `aria-expanded`/`aria-controls` wiring, its open state, and its
	 * focus-return-on-dismiss all went with it. Kept as an empty sheet it would
	 * have been a button that opens nothing.
	 *
	 * What went with it, listed because each was a deliberate thing and someone
	 * rebuilding an overflow later should know it existed:
	 *   - `dismissMore()`, which returned focus to the More button on BOTH Escape
	 *     and a scrim tap. The Next version only did it on Escape, which left a
	 *     scrim tap dropping focus to the top of the document.
	 *   - `use:escapeKey`, whose whole point was that the listener's lifetime is
	 *     the sheet element's. The action itself is kept at
	 *     `$lib/actions/escapeKey` -- it is general-purpose and the floating
	 *     panels behind FEATURES will want it -- but this was its only call site.
	 *   - `PRIMARY_SLOTS`, a hardcoded list of the four important hrefs. The bar
	 *     renders `primaryNav` directly now, so "which four" is stated once.
	 *
	 * PORTED AT 1px -- see the note in SideRail.
	 */

	const pathname = $derived(page.url.pathname);
</script>

{#snippet barLink(item: NavItem)}
	{@const active = isActiveRoute(item.href, pathname)}
	{@const Icon = item.icon}
	<a
		href={item.href}
		aria-current={active ? 'page' : undefined}
		class="flex min-h-11 min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-md border py-1 text-2xs font-medium transition-colors duration-(--motion-fast) ease-standard
			{active
			? // Same treatment as the rail: a filled, bordered tab. The tint the
				// active tab used to get was doing the job with colour alone, and on a
				// phone in daylight it was doing it badly.
				'border-line-strong bg-primary text-on-primary'
			: 'border-transparent text-muted-ink hover:border-line hover:text-ink'}"
	>
		<Icon aria-hidden="true" class="size-5 shrink-0" />
		<span class="max-w-full truncate">{item.label}</span>
	</a>
{/snippet}

<nav
	data-nav="bottom"
	aria-label="Primary"
	class="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface lg:hidden"
>
	<!-- Only the top pad is set here -- the bottom one belongs to the safe-area
	     inset below, and a py-* would be silently overwritten by it. -->
	<ul
		class="flex h-bottomnav items-stretch gap-1 px-1.5 pt-1"
		style="padding-bottom: env(safe-area-inset-bottom)"
	>
		{#each primaryNav as item (item.href)}
			<li class="flex min-w-0 flex-1">{@render barLink(item)}</li>
		{/each}
	</ul>
</nav>
