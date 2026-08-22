<script lang="ts">
	import PagePlaceholder from '$lib/components/PagePlaceholder.svelte';
	import { pageTitle } from '$lib/title';
</script>

<svelte:head><title>{pageTitle('Settings')}</title></svelte:head>

<PagePlaceholder href="/settings" />
