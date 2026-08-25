<script lang="ts">
	import ChatWindow from '$lib/components/ask/ChatWindow.svelte';
	import type { PageData } from './$types';

	/**
	 * One destination.
	 *
	 * A mount point and nothing else. The header and the rail belong to the layout
	 * because they are the same on all three; what changes between them is the chat
	 * window's contents, and that is this.
	 *
	 * `{#key}` on the conversation id: opening a different saved conversation must
	 * clear the unsent exchange from this tab. Without it, a student could type a
	 * question under one conversation, click another in the rail, and find their
	 * own message sitting under someone else's title -- the state would survive
	 * because the component would not have remounted. Same construct and the same
	 * reason as the booking panel remounting per advisor.
	 */
	let { data }: { data: PageData } = $props();
</script>

{#key data.conversation?.id ?? data.destination}
	<ChatWindow
		destination={data.destination}
		conversation={data.conversation}
		live={data.live}
		starter={data.starter}
	/>
{/key}
