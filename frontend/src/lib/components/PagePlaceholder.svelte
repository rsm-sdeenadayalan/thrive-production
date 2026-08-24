<script lang="ts">
	import { allNav } from '$lib/nav';

	/**
	 * Shared body for the routes that exist but aren't built yet.
	 *
	 * It pulls its icon and framing from the nav config, so a stub page can never
	 * disagree with the nav item that points at it. The throw is the mechanism:
	 * add a route without adding it to `nav.ts` and the page fails loudly rather
	 * than rendering a stub with no name.
	 *
	 * The lookup is a `$derived` so it tracks `href` rather than capturing its
	 * first value. The throw lands on first read, which is during render -- the
	 * same moment React threw.
	 *
	 * It resolves against `allNav`, which is visible AND parked entries. That
	 * matters as of 2026-08-22: seven routes were taken out of the visible nav
	 * and their pages still render this, so looking them up in `primaryNav`
	 * alone would have turned every one of them into a 500. Parked is "no way in
	 * from the nav", not "gone".
	 */
	let { href }: { href: string } = $props();

	const item = $derived.by(() => {
		const found = allNav.find((navItem) => navItem.href === href);
		if (!found) throw new Error(`PagePlaceholder: no nav entry for "${href}"`);
		return found;
	});

	const Icon = $derived(item.icon);
</script>

<div class="mx-auto w-full max-w-page space-y-4 lg:space-y-3">
	<div class="flex items-start gap-2.5">
		<span
			class="grid size-10 shrink-0 place-items-center rounded-md border border-line bg-primary-soft"
		>
			<Icon aria-hidden="true" class="size-5 text-primary" />
		</span>
		<div class="min-w-0">
			<!-- PAGE TITLE. `text-3xl font-bold`, matching every built route's h1 --
			     see the ladder note in app.css. MIGRATION.md section 9 defect 4:
			     twelve of thirteen page titles in the Next app render at 400, because
			     weight came out of the type scale on 08-15 and the h1s were never
			     updated. This component serves seven routes, so it was seven of the
			     twelve on its own; the 2026-08-24 sweep fixed the size that was left
			     behind alongside the weight. -->
			<h1 class="text-3xl font-bold text-ink">{item.label}</h1>
			<p class="mt-0.5 text-sm text-muted-ink">{item.description}</p>
		</div>
	</div>

	<!-- A stub is still a panel. Left as a bare tint it read as a gap in the page
	     rather than as a section that exists but is empty. -->
	<div data-tone="sunken" class="thrive-panel px-4 py-8 text-center">
		<p class="text-base text-ink">This section is coming next.</p>
		<p class="mx-auto mt-1 max-w-md text-xs text-muted-ink">
			The shell, design tokens, and data layer are in place. {item.label} is built out in a later
			step.
		</p>
	</div>
</div>
