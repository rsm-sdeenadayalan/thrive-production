<script lang="ts">
	import '../app.css';

	import AppShell from '$lib/components/shell/AppShell.svelte';
	import { primeOverlay } from '$lib/overlaySync';
	import { hydrateStores } from '$lib/overrideStore.svelte';
	import { hydrateTaskNotes } from '$lib/taskNotes.svelte';
	import { SITE_DESCRIPTION, pageTitle } from '$lib/title';

	let { data, children } = $props();

	/**
	 * THE ONE PLACE THE STORES HYDRATE.
	 *
	 * `$effect` runs after mount and only in the browser, which is exactly the
	 * contract the store layer was built against: server and first client render
	 * both see no overrides, and the student's own edits land on the render after
	 * this fires. Hydration strategy A -- the same brief un-personalised flash the
	 * Next app has.
	 *
	 * Do not move this into a component, and do not add a second call. A surface
	 * that later wants to wait for personalised data should read a flag derived
	 * from here rather than hydrating again.
	 *
	 * `hydrateTaskNotes` is separate because notes are not an override store and
	 * so are not in the registry -- see the note at the top of taskNotes.
	 */
	$effect(() => {
		primeOverlay(data.overlay ?? null);
		hydrateStores();
		hydrateTaskNotes();
	});
</script>

<svelte:head>
	<!-- The default title. Each route sets its own through `pageTitle`, which
	     reproduces Next's "%s · THRIVE" template. -->
	<title>{pageTitle()}</title>
	<meta name="description" content={SITE_DESCRIPTION} />
</svelte:head>

<AppShell student={data.student}>
	{@render children()}
</AppShell>
