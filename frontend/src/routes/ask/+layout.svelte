<script lang="ts">
	import type { Snippet } from 'svelte';

	import { page } from '$app/state';
	import { DEFAULT_DESTINATION, isAskDestination } from '$lib/ask';
	import AskHistory from '$lib/components/ask/AskHistory.svelte';
	import DestinationTabs from '$lib/components/ask/DestinationTabs.svelte';
	import { messages } from '$lib/messages';
	import { pageTitle } from '$lib/title';
	import type { LayoutData } from './$types';

	/**
	 * The section frame: a header, the history strip, and whichever destination is
	 * open.
	 *
	 * ## The width
	 *
	 * `max-w-page` (90rem) rather than the `max-w-page` (72rem) every other
	 * route uses. This is the one surface that genuinely wants the room: at 72rem on
	 * a 1512px screen the chat sat in a column with 120px of dead margin either
	 * side, and a second rail was eating another 224px of it.
	 *
	 * **The line length is capped separately, and that is the point.** The panel
	 * fills the page; the message TEXT is capped at `--thrive-chat-measure`. Capping
	 * the container instead would have left the dead margin exactly where it was.
	 *
	 * Other routes did not move. The measure used to live on `AppShell`'s `main` as
	 * a single `max-w-6xl`, which is why widening this one would have widened Home;
	 * it now lives on each page, and `page` is the same 72rem that was there before.
	 *
	 * ## There is no second rail
	 *
	 * The three destinations are in the NAVIGATION rail now, as a disclosure under
	 * Ask THRIVE — they are routes, and routes belong in the navigation. That left
	 * the page's rail holding only the saved conversations, which is not enough to
	 * justify a column, so the history became a horizontal strip and the chat took
	 * the width back. `DestinationTabs` covers the widths where the nav rail is not
	 * on screen.
	 *
	 * ## Why the history is here and not in the page
	 *
	 * It is the same data on all three destinations. In a layout it is loaded once
	 * and SURVIVES navigation between them, so switching subject changes the
	 * highlighted link and nothing else moves. In the page it would remount on
	 * every click.
	 *
	 * ## The destination is read from the URL here too
	 *
	 * The page's `load` validates the segment and is the thing that 404s, but a
	 * layout cannot read its child's data. So it reads the same parameter and falls
	 * back to the default for the one frame `/ask` renders before its redirect
	 * lands. That fallback is never user-visible; it exists so the type is honest
	 * rather than asserted.
	 */
	let { data, children }: { data: LayoutData; children: Snippet } = $props();

	const copy = messages.ask;

	const destination = $derived.by(() => {
		const slug = page.params.destination ?? '';
		return isAskDestination(slug) ? slug : DEFAULT_DESTINATION;
	});
</script>

<svelte:head><title>{pageTitle(copy.documentTitle)}</title></svelte:head>

<!--
	`min-h-0` down the spine is what lets the chat log be the only thing that
	scrolls on a desktop. Without it a flex child refuses to shrink below its
	content and the log's own `overflow-y-auto` never engages — the document grows
	instead, which is precisely the shape `check:layout` exists to catch.
-->
<div class="mx-auto flex w-full max-w-page min-h-0 flex-col gap-4 lg:gap-3">
	<!-- The section's one `h1`. The chat window's title is an `h2` under it: there
	     is one page here and the destination is a region within it. -->
	<header>
		<p class="thrive-eyebrow">{copy.eyebrow}</p>
		<h1 class="mt-1 text-3xl font-bold text-ink">{copy.title}</h1>
		<p class="mt-1.5 max-w-measure text-sm text-body">
			{data.live ? copy.introLive : copy.intro}
		</p>
	</header>

	<!-- Only below `lg`, where the navigation rail is not on screen. -->
	<DestinationTabs />

	<!--
		The history rail and the chat, side by side above `xl`.

		`items-start` rather than stretch: the two are independent scroll containers
		with their own heights, and stretching would make the shorter one grow to the
		taller and defeat both caps.

		Below `xl` this stacks, and `AskHistory` flips to a horizontal strip — see the
		note there for why two rails plus a chat cannot fit a phone.
	-->
	<div class="flex min-h-0 flex-col gap-4 lg:gap-3 xl:flex-row xl:items-start xl:gap-3">
		<AskHistory conversations={data.conversations} {destination} />

		{@render children()}
	</div>
</div>
