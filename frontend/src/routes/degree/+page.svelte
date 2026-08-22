<script lang="ts">
	import PagePlaceholder from '$lib/components/PagePlaceholder.svelte';
	import { pageTitle } from '$lib/title';

	/**
	 * Placeholder body only.
	 *
	 * In the Next app this route is PARTIAL, not a stub: it renders a real
	 * `ProgramTimeline` above the placeholder, plus a link card into
	 * `/degree/requests` carrying live counts. Both need providers
	 * (`getProgramTimeline`, `getMyRequests`), so both wait for Phase 5. The body
	 * that was always a placeholder is what is here.
	 */
</script>

<svelte:head><title>{pageTitle('Degree')}</title></svelte:head>

<PagePlaceholder href="/degree" />
