<script lang="ts">
	import PagePlaceholder from '$lib/components/PagePlaceholder.svelte';
	import { pageTitle } from '$lib/title';

	/**
	 * Placeholder body only.
	 *
	 * Same shape as `/degree`: PARTIAL in the Next app, where the placeholder sits
	 * above a link card into `/career/resume` showing version and skill counts.
	 * That card needs `getResumeVersions`, so it waits for Phase 5.
	 */
</script>

<svelte:head><title>{pageTitle('Career')}</title></svelte:head>

<PagePlaceholder href="/career" />
