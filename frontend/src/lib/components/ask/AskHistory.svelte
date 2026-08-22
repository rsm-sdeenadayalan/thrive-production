<script lang="ts">
	import { page } from '$app/state';
	import MessageSquarePlus from '@lucide/svelte/icons/message-square-plus';

	import { conversationsFor, type ConversationView } from '$lib/ask';
	import { messages } from '$lib/messages';
	import type { AskDestination } from '$lib/data';
	import { cn } from '$lib/utils';

	/**
	 * The conversation history, as a rail beside the chat.
	 *
	 * So the page reads, left to right: navigation rail, history rail, chat.
	 *
	 * ## It has one job, and that is the point
	 *
	 * An earlier version of this rail held the three destinations AND the history.
	 * The destinations moved into the navigation rail as a group — they are routes,
	 * and routes belong in the navigation — which for a while left this holding one
	 * list, and a one-list rail was dropped rather than kept out of inertia.
	 *
	 * It comes back because a history rail is a different thing from a leftover: it
	 * is the shape a chat app uses, a vertical column of past conversations is far
	 * easier to SCAN than a horizontal strip of cards, and the width it costs comes
	 * from the page's empty margins rather than from the chat.
	 *
	 * ## One destination's history, not all three
	 *
	 * Deliberate, and the reason is the URL rather than the layout. A conversation
	 * belongs to a destination, and `/ask/[destination]/+page.server.ts` returns 404
	 * for a real conversation opened under the wrong one — a Career exchange under
	 * the Course Recommender heading would be a page contradicting its own address.
	 * So a mixed list would be a list where most rows are 404s.
	 *
	 * Grouping all three under headings was the alternative. It was rejected on
	 * shape: the fixtures carry one to three conversations per destination, so three
	 * headings would be roughly one heading per row inside a 240px column. And
	 * switching subject is now one click in the navigation rail, with the history
	 * following it.
	 *
	 * ## Rail above `xl`, strip below it, ONE tree
	 *
	 * Two rails plus a chat cannot fit a phone, and the navigation rail already
	 * solves its own half by being `hidden lg:flex`. So below `xl` this becomes a
	 * horizontal scroller above the chat — the same list, the same links, a
	 * different axis. CSS on one DOM tree rather than two media-gated subtrees,
	 * because it is one list in a different direction and duplicating it would put
	 * two copies of every link in the accessibility tree.
	 *
	 * ## The two scroll containers are independent
	 *
	 * This one scrolls inside itself, capped at the chat's own height token, and the
	 * chat's log scrolls inside the chat. Neither moves the other, and neither moves
	 * the document.
	 */
	let {
		conversations,
		destination
	}: {
		conversations: ConversationView[];
		destination: AskDestination;
	} = $props();

	const copy = messages.ask;

	const visible = $derived(conversationsFor(conversations, destination));

	/**
	 * Which conversation is open, read from the URL rather than held locally.
	 *
	 * So a reload, a shared link and the back button all agree with the rail about
	 * what is current, with nothing to synchronise.
	 */
	const openId = $derived(page.url.searchParams.get('c'));
</script>

<!--
	A `<nav>` landmark, because this IS navigation: every row is a link to a URL.
	Named, so a screen reader user can tell it from the two other navigations on the
	page.

	## It is a PANEL now, not a margin

	It used to be bare content on the page's cream with a single `xl:border-r`, and
	it read as text floating in a margin rather than as a region. Nothing was
	invented to fix that: the nav rail already solves the same problem with
	`bg-sunken` behind a `border-line` edge, and `.thrive-panel[data-tone="sunken"]`
	IS that pair — the recessed fill, the 1px hairline and the panel radius, all
	from the tokens that define every other container in the app.

	`p-2.5` rather than the panel default (1.25rem), matching the density the rest
	of the app's panels are set at.
-->
<nav
	aria-label={copy.rail.historyLabel}
	data-tone="sunken"
	class="thrive-panel flex shrink-0 flex-col gap-1.5 p-2.5 xl:w-60"
>
	<div class="flex flex-wrap items-baseline justify-between gap-2">
		<p class="thrive-eyebrow">{copy.rail.historyHeading}</p>

		<!--
			"New conversation" is a link to the bare destination, which is exactly what
			a new conversation IS here: this page with nothing open. A button holding
			client state would be a second way to express what the URL already says,
			and it would not survive a reload.

			Always present, not only when something is open, because "start a new one"
			is a thing a student looks for rather than a thing that appears.
		-->
		<a
			href={`/ask/${destination}`}
			aria-current={openId ? undefined : 'page'}
			class={cn(
				'inline-flex min-h-11 items-center gap-1 rounded-sm px-1 text-3xs',
				openId ? 'text-muted-ink hover:text-ink' : 'text-ink'
			)}
		>
			<MessageSquarePlus aria-hidden="true" class="size-3.5 shrink-0" />
			{copy.rail.newConversation}
		</a>
	</div>

	{#if visible.length === 0}
		<!--
			An empty state that says what WOULD be here, not "no data". This is the
			first thing a student sees on a destination they have never used, so it has
			to read as a beginning rather than as a failure.
		-->
		<p class="text-3xs text-muted-ink">{copy.rail.historyEmpty}</p>
	{:else}
		<!--
			Scrolls inside itself. Above `xl` the cap is the chat's own height, so the
			two columns end level and the chat cannot be pushed down by a long history;
			below it the cap is short, because this sits ABOVE the chat there and the
			composer is what the page is for.
		-->
		<ul
			class="-mx-1 flex max-h-40 min-h-0 gap-2 overflow-x-auto overflow-y-hidden px-1 pb-1 xl:mx-0 xl:max-h-[var(--thrive-chat-height)] xl:flex-col xl:gap-1 xl:overflow-x-hidden xl:overflow-y-auto xl:px-0"
		>
			{#each visible as conversation (conversation.id)}
				{@const open = conversation.id === openId}

				<li class="w-56 shrink-0 xl:w-auto xl:shrink">
					<a
						href={`/ask/${destination}?c=${conversation.id}`}
						aria-current={open ? 'page' : undefined}
						aria-label={copy.rail.openConversation(
							conversation.title,
							conversation.updatedLabel
						)}
						class={cn(
							// `border-l-2` on EVERY row, coloured differently rather than
						// widened, so the title's left edge is in the same place whether a
						// row is open or not. A stripe that appears only on the current row
						// would shift the whole list sideways as you click through it. The
						// 2px stripe is the same idiom `TaskRow` uses for priority.
						'block h-full rounded-md border border-l-2 px-2.5 py-2 transition-colors duration-(--motion-fast) ease-standard lg:py-1.5',
							// EVERY row has a surface and an edge at REST, which is the change
							// that makes this read as a list of things you can click. It used
							// to be `border-transparent` with no fill until hover, so on the
							// page's cream the rows were indistinguishable from prose and the
							// only affordance was a pointer that had already arrived.
							//
							// On the sunken rail a white row is a raised one, so the stack
							// reads as cards without a single new token.
							//
							// The open conversation keeps the control-weight stroke AS WELL AS
							// the tint, and adds a navy bar down its leading edge. Three cues,
							// none of them hue alone: the stroke survives not being able to
							// separate the fill from the surface behind it, the bar survives
							// greyscale, and `aria-current` carries it non-visually.
							open
								? 'border-line-strong border-l-primary bg-primary-soft'
								: 'border-line border-l-line bg-surface hover:border-line-strong hover:bg-primary-soft'
						)}
					>
						<span class="line-clamp-2 text-2xs text-ink">{conversation.title}</span>

						<!-- When and how long. Both values, both on the numeric face, so a
						     column of them lines up. -->
						<span class="thrive-numeric mt-0.5 block text-3xs text-muted-ink">
							{conversation.updatedLabel} · {copy.rail.messageCount(
								conversation.messageCount
							)}
						</span>
					</a>
				</li>
			{/each}
		</ul>
	{/if}
</nav>
