<script lang="ts">
	import type { Snippet } from 'svelte';

	import BottomNav from '$lib/components/shell/BottomNav.svelte';
	import SideRail from '$lib/components/shell/SideRail.svelte';
	import TopBar from '$lib/components/shell/TopBar.svelte';
	import Toast from '$lib/components/ui/Toast.svelte';
	import { FEATURES } from '$lib/features';
	import type { Student } from '$lib/data/types';

	/**
	 * The persistent frame around every page: rail (desktop) or bottom bar
	 * (mobile), header, and the content region.
	 *
	 * In the Next app this was an `async` server component that awaited
	 * `getStudent()` mid-tree. SvelteKit has nowhere to await inside a component,
	 * and does not need one: the root `+layout.server.ts` loads the student and
	 * passes it in. Same data, fetched at the edge of the tree instead of inside
	 * it, which is where MIGRATION.md section 8 item 2 says it belongs.
	 *
	 * Kept as its own component rather than inlined into `+layout.svelte` so the
	 * layout stays about data and lifecycle while this stays about structure.
	 */
	let { student, children }: { student: Student; children: Snippet } = $props();
</script>

<div class="min-h-dvh bg-bg">
	<!-- First tab stop: lets keyboard users jump the whole nav. -->
	<a href="#main-content" class="skip-link">Skip to main content</a>

	<SideRail />

	<div class="lg:pl-rail">
		<TopBar {student} notificationCount={2} />

		<!-- The bottom padding clears the mobile nav bar, which is fixed OVER the
		     page, so on mobile it is the bar's height plus the page's gutter. Above
		     `lg` there is no bar and the gutter is the whole padding.
		     Both halves now come from `--thrive-page-gutter-bottom` rather than one
		     being a bare `pb-8`: 32px of desktop padding was buying nothing under a
		     page whose last element is already a bordered panel, and it cost every
		     route. -->
		<!--
			NO MAX-WIDTH HERE ANY MORE.

			`max-w-6xl` used to live on this element, which made one number the measure
			of every route in the app — so a page that wanted more room could not have
			it without widening Home by accident. The shell now provides the gutters
			and each page names its own measure with `max-w-page`. Every route lands on
			that one today, `/calendar` included — but the point of naming it per page
			stands: how wide a page should be is a property of what is on it, not of
			the frame around it — and prose inside it is capped
			separately with `max-w-measure`, because a paragraph does not want the
			width a month grid does.

			THE SIDE GUTTER IS THE SHELL'S JOB, and it widens at `lg`.

			`px-3 sm:px-5` below that, unchanged, because a phone has no width to give
			away. `lg:px-page-x` (40px) above it, which is what keeps content off the
			edges at 1512 where the caps do not bite. The caps and the gutter are two
			separate knobs: a gutter alone does not solve a 2560px monitor and a cap
			alone does not solve a 1512px one.
		-->
		<main
			id="main-content"
			tabindex="-1"
			class="w-full px-3 pt-4 lg:pt-3 pb-[calc(var(--thrive-bottomnav-height)+var(--thrive-page-gutter-bottom))] sm:px-5 lg:px-page-x lg:pb-page-bottom"
		>
			{@render children()}
		</main>
	</div>

	<BottomNav />

	<!-- Mounted always, on every route, and its text is the only thing that
	     changes. A live region populated in the same tick it is created announces
	     unreliably -- see the note in the component. -->
	<Toast />

	<!--
		Floating widgets mount here, last in the DOM so they land above the page
		without a z-index race, and so they are the final tab stops rather than
		something the keyboard has to pass through to reach the content.

		Hidden for now to simplify the UI. Flip FEATURES to true to bring back.
		The internals are a later phase; these are the mount points.
	-->
	{#if FEATURES.floatingTodo}
		<!-- QuickListWidget -->
	{/if}

	{#if FEATURES.floatingAssistant}
		<!-- AssistantWidget -->
	{/if}
</div>
