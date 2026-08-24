<script lang="ts">
	import { page } from '$app/state';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';

	import { messages } from '$lib/messages';
	import { isActiveRoute, primaryNav, type NavItem } from '$lib/nav';

	/**
	 * Desktop navigation rail. Hidden below `lg`, where BottomNav takes over.
	 * Rendered as its own <nav> landmark so screen reader users can jump to it.
	 *
	 * Structural chrome, drawn as a bounded region: a recessed fill and a
	 * hairline edge. The fill is what separates it -- `sunken` against the page's
	 * `bg` -- and the line only tidies the boundary.
	 *
	 * PORTED AT 1px, NOT 2px. The Next source draws `border-r-2` here and its
	 * comment calls that "the standard 2px edge". Both are left over from the
	 * bordered direction of 2026-08-12, which the 08-15 restyle reversed without
	 * sweeping the call sites: under the current direction a decorative hairline
	 * is 1px and only a control boundary is 1.5px. MIGRATION.md section 5 lists
	 * the leftover 2px strokes as an unfinished sweep, and section 9 puts them on
	 * the build-correctly list.
	 *
	 * `RailLink` was its own component in the Next tree, for one reason: the rail
	 * renders two lists and they must not drift. A snippet is the Svelte
	 * equivalent and keeps it in the file that uses it.
	 *
	 * IT RENDERS ONE LIST NOW (2026-08-22). The second was a pinned strip at the
	 * bottom holding `secondaryNav`, which held Settings and nothing else.
	 * Settings is parked with the other trimmed destinations, so that list is
	 * empty and the strip with it -- an empty bordered container is not a
	 * treatment worth keeping. The snippet stays: it is still the thing that
	 * stops the rail and the bottom bar drifting, which is the more important of
	 * the two jobs it had.
	 *
	 * ## An item with children is a DISCLOSURE, and owes the whole contract
	 *
	 * Ask THRIVE's subjects live here now rather than in a second rail on
	 * the page. That makes the parent two things at once -- a link to a real route
	 * and the trigger for a group -- and those cannot be the same element:
	 *
	 *  - The **link** navigates. `/ask` redirects to the first child, so tapping
	 *    the label always goes somewhere useful.
	 *  - A separate **button** beside it toggles the group, carries
	 *    `aria-expanded` and `aria-controls`, and is the only thing a keyboard
	 *    needs to open it.
	 *
	 * Folding both into one control would mean either a link that does not
	 * navigate or a disclosure that cannot be collapsed once opened.
	 *
	 * **Collapsed means REMOVED, not hidden.** The children are inside an `{#if}`,
	 * so they are absent from the DOM and therefore from the tab order — rather
	 * than `hidden` or `display:none`, which browsers treat inconsistently for
	 * focus. There is nothing to `tabindex="-1"` because there is nothing there.
	 *
	 * **It opens itself when a child is current**, so landing on `/ask/courses`
	 * from a link shows the group already open with Course Recommender marked. That is
	 * `$derived` from the URL rather than an effect writing state: the URL is the
	 * source of truth and an effect would let the two disagree for a tick.
	 *
	 * No `escapeKey` and no `focusTrap` here, and that is deliberate. Those belong
	 * to things that cover the page — a modal dialog, a floating panel. An inline
	 * disclosure inside a persistent rail traps nothing and dismisses nothing; a
	 * student tabs past it. Adding either would make the rail modal, which it is
	 * not.
	 */

	const pathname = $derived(page.url.pathname);
	const copy = messages.nav;

	/**
	 * Groups the student has toggled by hand, by href.
	 *
	 * Only the DIVERGENCE from "open when a child is current" is stored, which is
	 * the same shape as the override stores: `undefined` means "no opinion, use the
	 * derived answer". Without that, opening a group and then navigating inside it
	 * would fight the derived state.
	 *
	 * Not persisted. A rail's open group is a momentary place, like the calendar's
	 * selected day.
	 */
	let toggled = $state<Record<string, boolean>>({});

	function hasCurrentChild(item: NavItem): boolean {
		return (item.children ?? []).some((child) => isActiveRoute(child.href, pathname));
	}

	function isOpen(item: NavItem): boolean {
		return toggled[item.href] ?? hasCurrentChild(item);
	}
</script>

{#snippet railLink(item: NavItem, nested = false)}
	{@const active = isActiveRoute(item.href, pathname)}
	{@const Icon = item.icon}
	{@const group = (item.children ?? []).length > 0}
	{@const open = group && isOpen(item)}
	{@const childCurrent = group && hasCurrentChild(item)}
	<!-- A parent whose CHILD is current is not itself current. `isActiveRoute`
	     matches by prefix, so `/ask` is "active" on `/ask/courses` -- but painting
	     both rows solid navy would say the student is in two places, and putting
	     `aria-current="page"` on both would tell a screen reader the same lie. The
	     parent takes full ink instead: the containing section, not the position. -->
	{@const selfCurrent = active && !childCurrent}
	{@const groupId = `rail-group-${item.href.replace(/\W+/g, '-')}`}

	<!-- The link and the toggle are siblings in one row, so the row still reads as
	     one item while being two controls. -->
	<div class="flex items-stretch gap-0.5">
		<a
			href={item.href}
			aria-current={selfCurrent ? 'page' : undefined}
			title={item.description}
			class="group relative flex min-h-10 flex-1 items-center gap-2.5 rounded-md border px-2.5 py-1.5 text-2xs font-medium transition-colors duration-(--motion-fast) ease-standard
				{nested ? 'pl-8' : ''}
				{selfCurrent
				? // Solid fill plus the control-weight stroke. The stroke is the part
					// that matters: appearing and disappearing is a shape change, so the
					// selected item still reads as selected to someone who cannot separate
					// the forest green from the rail behind it. aria-current carries it
					// non-visually.
					'border-line-strong bg-primary text-on-primary'
				: childCurrent
					? 'border-transparent text-ink hover:border-line hover:bg-surface'
					: 'border-transparent text-body hover:border-line hover:bg-surface hover:text-ink'}"
		>
			<!-- Resting icons sit on muted rather than faint. Faint clears the
			     non-text contrast bar but disappears next to 13px/500 labels. -->
			<Icon
				aria-hidden="true"
				class="{nested ? 'size-4' : 'size-5'} shrink-0 {selfCurrent
					? 'text-on-primary'
					: 'text-muted-ink'}"
			/>
			<span class="truncate">{item.label}</span>
		</a>

		{#if group}
			<!-- A real 44px control, its own element, carrying the disclosure state.
			     `aria-controls` points at the list it opens; `aria-expanded` is the
			     state; the label names what it does rather than which way it points. -->
			<button
				type="button"
				aria-expanded={open}
				aria-controls={groupId}
				aria-label={open ? copy.collapseGroup(item.label) : copy.expandGroup(item.label)}
				onclick={() => (toggled[item.href] = !open)}
				class="grid size-11 shrink-0 place-items-center rounded-md border border-transparent text-muted-ink transition-colors duration-(--motion-fast) ease-standard hover:border-line hover:bg-surface hover:text-ink"
			>
				<ChevronDown
					aria-hidden="true"
					class="size-4 transition-transform duration-(--motion-fast) ease-standard {open
						? 'rotate-180'
						: ''}"
				/>
			</button>
		{/if}
	</div>

	{#if group && open}
		<!-- Inside an `{#if}`, so collapsed means absent from the DOM and from the
		     tab order. Indented by the link's own padding rather than by a margin on
		     the list, so the whole 44px row stays clickable to the rail's edge. -->
		<ul id={groupId} class="mt-0.5 flex flex-col gap-0.5">
			{#each item.children ?? [] as child (child.href)}
				<li>{@render railLink(child, true)}</li>
			{/each}
		</ul>
	{/if}
{/snippet}

<!--
	`data-nav="rail"` is a gate hook, the same shape as `data-day` and
	`data-service`. BottomNav carries `aria-label="Primary"` too -- correctly, since
	whichever of the two is DISPLAYED is the primary navigation, and they are never
	displayed together. But both are in the DOM at every width, so a gate scoping by
	the label alone matches both and counts an `aria-current` twice. That is exactly
	what it did.
-->
<nav
	data-nav="rail"
	aria-label="Primary"
	class="fixed inset-y-0 left-0 z-30 hidden w-rail flex-col border-r border-line bg-sunken lg:flex"
>
	<!-- Ruled off at the same height as the header, so the rail's edge and the
	     top bar's edge continue one line across the shell. -->
	<div class="flex h-topbar shrink-0 items-center border-b border-line px-4">
		<!-- A small tracked cap rather than a headline. One piece of branding at
		     13px / 0.14em, letting the content be the loudest thing on screen.
		     Weight is set here, at the call site: the type scale carries size,
		     leading and tracking only. -->
		<a href="/" class="rounded-sm text-2xs font-medium tracking-[0.14em] text-ink uppercase">
			THRIVE
			<span class="sr-only"> home</span>
		</a>
	</div>

	<ul class="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-2">
		{#each primaryNav as item (item.href)}
			<li>{@render railLink(item)}</li>
		{/each}
	</ul>
</nav>
