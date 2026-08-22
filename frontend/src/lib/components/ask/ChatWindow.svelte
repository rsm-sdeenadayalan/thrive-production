<script lang="ts">
	import { tick } from 'svelte';
	import CornerDownLeft from '@lucide/svelte/icons/corner-down-left';
	import Sparkles from '@lucide/svelte/icons/sparkles';

	import { showsDayLabel, type ChatMessageView, type ConversationDetailView } from '$lib/ask';
	import Button from '$lib/components/ui/Button.svelte';
	import { messages } from '$lib/messages';
	import type { AskDestination } from '$lib/data';
	import { cn } from '$lib/utils';

	/**
	 * The chat window: a log, an empty state, and a composer.
	 *
	 * ## What is real and what is not
	 *
	 * The SAVED half is real data through a real provider -- `conversation` arrives
	 * from the server with every date already formatted, and it is what a retrieval
	 * service will eventually write.
	 *
	 * The SENT half is not. There is nothing to answer with, so a message typed
	 * here gets a fixed reply saying so and lives in `sent` below: component state,
	 * gone the moment the student navigates. That is stated on screen BEFORE
	 * anything is typed, not after, because a student who discovered it by leaving
	 * would reasonably read it as having lost something.
	 *
	 * The reply says plainly that it cannot answer. A placeholder that mimics a
	 * real answer teaches a student to trust something that is not there -- the
	 * same call the floating assistant made, for the same reason.
	 *
	 * Deliberately NOT a `localStorage` store. Conversations are large and grow
	 * without bound, a second laptop would show an empty history indistinguishable
	 * from never having asked anything, and it is persistence that would have to be
	 * torn out when the backend lands. Ephemeral-and-honest beats persistent-and-wrong.
	 *
	 * ## The log's accessibility, ported from the floating assistant
	 *
	 * `role="log"` with `aria-live="polite"`: a reply is announced without stealing
	 * focus from the field the student is still typing in, and `log` tells the
	 * screen reader that only additions matter rather than re-reading the whole
	 * history. Each bubble carries a spoken "You said" / "THRIVE said" prefix, so
	 * who spoke does not rest on which side of the column a bubble sits on.
	 *
	 * The log is a real scroll container with `tabindex="0"`, which is what makes a
	 * long conversation keyboard-navigable: a scrollable region that cannot be
	 * focused cannot be scrolled by a keyboard at all.
	 *
	 * ## Scrolling is not an arrival
	 *
	 * Pushing the log to its newest message is not `arriveAtRow` and must not
	 * become it. CONVENTIONS.md carves out exactly this: an arrival lands a student
	 * ON A ROW THEY ASKED ABOUT and marks what it lands on. Nobody asked about
	 * their own message, and marking every send would turn a wayfinding cue into a
	 * cursor. `arriveAtRow` remains the only arrival treatment in the app because
	 * nothing here is an arrival.
	 */
	let {
		destination,
		conversation
	}: {
		destination: AskDestination;
		/** The saved conversation in view, or null for a fresh one. */
		conversation: ConversationDetailView | null;
	} = $props();

	const copy = messages.ask;

	/** This tab's exchange. Never persisted -- see the note above. */
	let sent = $state<ChatMessageView[]>([]);
	let draft = $state('');
	let logEl = $state<HTMLDivElement | null>(null);

	/**
	 * A counter, not a timestamp, and not `Date.now()`.
	 *
	 * These ids exist only to key an `{#each}` for the lifetime of one tab. Nothing
	 * stores them, nothing reads them back, and nothing outside this component ever
	 * sees them -- so this is not a fourth id key space, and it is not a clock read
	 * either. See CONVENTIONS.md: a nonce is not a date, and this is not even a
	 * nonce.
	 */
	let nextId = 0;

	const entry = $derived(copy.destinations[destination]);

	/** Saved first, then whatever was typed in this tab. */
	const saved = $derived(conversation?.messages ?? []);

	/**
	 * Nothing in the log at all.
	 *
	 * One derived read by both the branch and the log's own classes, so the layout
	 * and the content cannot disagree about whether there is anything to show —
	 * which is how you get a centring grid wrapped around a full conversation.
	 */
	const empty = $derived(saved.length === 0 && sent.length === 0);

	function send(event: SubmitEvent) {
		event.preventDefault();

		const body = draft.trim();
		if (!body) return;

		/*
		 * No time label on these. Every stamp in the saved half was formatted on the
		 * server, and a component has no business asking the browser what time it is
		 * to label a message that will not exist in a minute. The "This session"
		 * heading is what places them instead.
		 */
		sent = [
			...sent,
			{ id: `sent-${nextId++}`, role: 'student', body, timeLabel: '', dayLabel: '' },
			{
				id: `sent-${nextId++}`,
				role: 'thrive',
				body: copy.chat.placeholderReply,
				timeLabel: '',
				dayLabel: ''
			}
		];

		draft = '';
		scrollToNewest();
	}

	/**
	 * Push the log to the bottom, after Svelte has written the new rows.
	 *
	 * `await tick()` rather than the Next version's `queueMicrotask`: a tick IS the
	 * flush, whereas a microtask is a guess that the flush has already happened.
	 * Same substitution `MiniCalendar.focusDay` makes for the same reason.
	 */
	async function scrollToNewest() {
		await tick();
		if (logEl) logEl.scrollTop = logEl.scrollHeight;
	}
</script>

{#snippet bubble(message: ChatMessageView, stamped: boolean)}
	{@const mine = message.role === 'student'}

	<div class={cn('flex', mine ? 'justify-end' : 'justify-start')}>
		<!--
			`min(85%, --thrive-chat-measure)` — the bubble is capped by CHARACTERS, not
			by the panel. The panel fills a 90rem page; a bubble allowed to fill it too
			would run about 140 characters a line, roughly twice what a reader can track
			without losing the start of the next one. The percentage still wins on a
			phone, where 65ch is wider than the screen, and it is what keeps the inset
			from the opposite edge that makes a conversation read as two voices.
		-->
		<div
			class={cn('min-w-0 max-w-[min(85%,var(--thrive-chat-measure))]', mine && 'text-right')}
		>
			<p
				class={cn(
					'inline-block rounded-md border px-2.5 py-2 text-left text-sm break-words',
					mine
						? 'border-line-strong bg-primary text-on-primary'
						: 'border-line bg-surface text-body'
				)}
			>
				<!-- Who spoke, in words. On screen it is carried by the side of the
				     column and the fill; neither of those reaches a screen reader. -->
				<span class="sr-only">{mine ? copy.chat.youSaid : copy.chat.thriveSaid}</span>
				{message.body}
			</p>

			{#if stamped}
				<span class="thrive-numeric mt-0.5 block text-3xs text-muted-ink">
					{message.timeLabel}
				</span>
			{/if}
		</div>
	</div>
{/snippet}

<!--
	The height above `xl` is what makes the LOG the scroller rather than the
	document. See `--thrive-chat-height` in `app.css` for why it is a fixed panel
	and not a viewport calculation, and why a phone deliberately does not get one.

	`flex-1` IS GATED ON `xl`, and that is load-bearing rather than fussy.

	Above `xl` this sits in a `flex-row` beside the history rail, where `flex-1`
	governs WIDTH and is exactly what makes the chat take the room the rail does
	not. Below `xl` it is a child of a `flex-col`, where `flex-1` would govern
	HEIGHT instead: `flex-basis: 0%` plus grow silently beats the `h-` beside it, so
	the panel would take its content's height, the log would never overflow, and the
	document would scroll in its place.

	That exact mistake shipped for one commit when the rail was removed and this
	became a column child with an ungated `flex-1`. `check:interaction` caught it by
	SKIPPING its own keyboard-scroll assertion — "could not make the log overflow" —
	which is the quietest possible failure and still louder than the layout, which
	looked fine.
-->
<section
	aria-labelledby="ask-destination-heading"
	class="thrive-panel flex min-h-0 min-w-0 flex-col p-0 xl:h-[var(--thrive-chat-height)] xl:flex-1"
>
	<div class="border-b border-line px-3 py-2.5">
		<h2 id="ask-destination-heading" class="text-base font-medium text-ink">
			{conversation ? conversation.title : entry.label}
		</h2>

		{#if conversation}
			<p class="thrive-numeric mt-0.5 text-3xs text-muted-ink">
				{conversation.updatedLabel} · {copy.rail.messageCount(conversation.messageCount)}
			</p>
		{:else}
			<p class="mt-0.5 text-3xs text-muted-ink">{entry.blurb}</p>
		{/if}
	</div>

	<!--
		`tabindex="0"` is load-bearing: a scroll container that cannot take focus
		cannot be scrolled with a keyboard, which would make a long conversation
		reachable by mouse only. `aria-labelledby` names it, because "log" on its
		own tells a screen reader nothing about which log.
	-->
	<!--
		svelte-ignore a11y_no_noninteractive_tabindex

		Two authorities disagree here and the accessibility one wins.

		Svelte's rule says a noninteractive role must not take a non-negative
		tabindex. axe's `scrollable-region-focusable` says the opposite about this
		exact element: a region that scrolls MUST be focusable, or its content is
		unreachable to anyone navigating by keyboard. A long conversation is the case
		that rule exists for, and the brief requires it be navigable.

		So the tabindex stays and the warning is suppressed at this one site with the
		reason written down, rather than the behaviour being dropped to keep a linter
		quiet. `npm run check` stays at 0 errors and 0 warnings.
	-->
	<div
		bind:this={logEl}
		role="log"
		aria-live="polite"
		aria-label={copy.chat.logLabel(entry.label)}
		tabindex="0"
		class={cn(
			'min-h-0 flex-1 overflow-y-auto p-3',
			// Empty: CENTRE the prompt card in the space. Pinned to the top it left a
			// tall void underneath it, which read as a panel that had failed to load
			// rather than as an invitation. With messages in it, back to a normal
			// top-anchored stack.
			empty ? 'grid place-items-center' : 'space-y-2.5'
		)}
	>
		{#if empty}
			<!--
				The empty state says what THIS destination can help with. A blank box
				would make the three surfaces indistinguishable, which is the whole
				thing they are not.
			-->
			<div class="max-w-measure rounded-lg border border-line bg-sunken p-3">
				<p class="thrive-eyebrow flex items-center gap-1.5">
					<Sparkles aria-hidden="true" class="size-3.5" />
					{entry.emptyHeading}
				</p>
				<p class="mt-1.5 max-w-measure text-sm text-body">{entry.emptyBody}</p>

				<ul class="mt-2.5 space-y-1">
					{#each entry.examples as example (example)}
						<li class="text-xs text-muted-ink">{example}</li>
					{/each}
				</ul>
			</div>
		{/if}

		{#each saved as message, index (message.id)}
			{#if showsDayLabel(saved, index)}
				<!-- One heading per day, not one per message. `showsDayLabel` lives in
				     `$lib/ask` because an off-by-one here would be invisible. -->
				<p class="thrive-eyebrow pt-1 text-center">{message.dayLabel}</p>
			{/if}

			{@render bubble(message, true)}
		{/each}

		{#if sent.length > 0}
			<p class="thrive-eyebrow pt-1 text-center">{copy.chat.draftHeading}</p>

			{#each sent as message (message.id)}
				{@render bubble(message, false)}
			{/each}
		{/if}
	</div>

	<form onsubmit={send} class="flex items-end gap-2 border-t border-line bg-sunken p-2.5">
		<label for="ask-composer" class="sr-only">{copy.chat.composerLabel}</label>

		<input
			id="ask-composer"
			name="question"
			bind:value={draft}
			autocomplete="off"
			placeholder={copy.chat.placeholder}
			class="min-h-11 min-w-0 flex-1 rounded-md border-[1.5px] border-line-strong bg-surface px-2.5 text-sm text-ink placeholder:text-muted-ink"
		/>

		<Button type="submit" variant="primary" disabled={draft.trim().length === 0} class="min-h-11">
			<CornerDownLeft aria-hidden="true" class="size-3.5" />
			{copy.chat.send}
		</Button>
	</form>

	<!-- Outside the form and below it, so it reads as a property of the page rather
	     than as an error about what was just typed. Said before anything is typed. -->
	<!-- The cap goes on the paragraph, not on a span inside it. A full-width `<p>`
	     wrapping a capped span LOOKS identical and is not the same thing: the
	     element that owns the text is the element whose line length matters, and a
	     gate measuring paragraph widths reads the wrapper. -->
	<p class="max-w-measure border-t border-line px-2.5 py-1.5 text-3xs text-muted-ink">
		{copy.chat.notSaved}
	</p>
</section>
