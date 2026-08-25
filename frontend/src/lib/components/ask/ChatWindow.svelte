<script lang="ts">
	import { tick } from 'svelte';
	import CornerDownLeft from '@lucide/svelte/icons/corner-down-left';
	import Sparkles from '@lucide/svelte/icons/sparkles';

	import { goto } from '$app/navigation';
	import { showsDayLabel, type ChatMessageView, type ConversationDetailView } from '$lib/ask';
	import type { ConversationStarter, RatingForm } from '$lib/data';
	import RichMessage from '$lib/components/ask/RichMessage.svelte';
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
	 * The SENT half depends on `live`. With the backend off there is nothing to
	 * answer with, so a message typed here gets a fixed reply saying so and lives
	 * in `sent` below: component state, gone the moment the student navigates. That
	 * is stated on screen BEFORE anything is typed, not after, because a student
	 * who discovered it by leaving would reasonably read it as having lost
	 * something.
	 *
	 * The mock reply says plainly that it cannot answer. A placeholder that mimics
	 * a real answer teaches a student to trust something that is not there -- the
	 * same call the floating assistant made, for the same reason.
	 *
	 * Deliberately NOT a `localStorage` store for the mock half. Conversations are
	 * large and grow without bound, a second laptop would show an empty history
	 * indistinguishable from never having asked anything, and it is persistence
	 * that would have to be torn out when the backend lands. Ephemeral-and-honest
	 * beats persistent-and-wrong.
	 *
	 * ## The live half
	 *
	 * When `live` is true, `sent` is used differently: as the OPTIMISTIC half of a
	 * real round trip rather than a permanent fiction. A submit pushes the
	 * student's own bubble immediately, posts to `/ask-sync`, and on success
	 * `goto`s to the URL carrying the persisted conversation id with
	 * `invalidateAll` -- the server reload is what actually renders the saved
	 * turns, and `sent` is cleared once that lands (explicitly, for the
	 * same-conversation case where the id does not change and the `{#key}` below
	 * does not remount). On failure the student's bubble stays exactly where it
	 * is and a THRIVE-side bubble explains what happened; nothing is lost because
	 * it was never a draft to begin with, it is already rendered.
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
		conversation,
		live,
		starter = null
	}: {
		destination: AskDestination;
		/** The saved conversation in view, or null for a fresh one. */
		conversation: ConversationDetailView | null;
		/** Whether `/ask-sync` is reachable. See the doc comment above. */
		live: boolean;
		/**
		 * The destination's opening question, when it has one and nothing has been
		 * said yet. Only the course recommender does. Null offline, and null once a
		 * conversation is open -- there is then nothing to open ON.
		 */
		starter?: ConversationStarter | null;
	} = $props();

	const copy = messages.ask;

	/**
	 * This tab's exchange. Never persisted when `!live` -- see the note above.
	 * When `live`, this is cleared once the server round trip lands; it never
	 * accumulates a full history of its own.
	 */
	let sent = $state<ChatMessageView[]>([]);
	let draft = $state('');
	let logEl = $state<HTMLDivElement | null>(null);

	/** True while a live send is in flight. Disables the composer. */
	let pending = $state(false);

	/**
	 * The rating form's current values, keyed by row.
	 *
	 * Seeded lazily from the form's own `default` rather than initialised up
	 * front: the form arrives with a message, so there is nothing to seed until
	 * one is on screen, and `$state` in a component that remounts per
	 * conversation cannot outlive the question it belongs to.
	 */
	let ratings = $state<Record<string, number>>({});

	function ratingOf(form: RatingForm, key: string) {
		return ratings[key] ?? form.default;
	}

	/** Submit the form as one ordinary message, phrased as a person would. */
	function submitRatings(form: RatingForm) {
		if (pending) return;
		const said = form.rows
			.map((row) => `${row.label} ${ratingOf(form, row.key)}`)
			.join(', ');
		ratings = {};
		choose(said);
	}

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

	/**
	 * Whether the thing on screen is a QUESTION waiting on an answer.
	 *
	 * True whenever choices are showing — the opening question's, or those under
	 * the newest reply. It is the same condition the buttons render on, derived
	 * once so the composer and the buttons cannot disagree about whether a
	 * question is open.
	 *
	 * The composer's own wording turns on this. "Type your question…" under a bot
	 * that has just asked "Which track are you on?" tells a student to do the
	 * opposite of what the screen is asking, and the course recommender asks four
	 * of those in a row.
	 */
	const awaitingAnswer = $derived.by(() => {
		if (empty) return Boolean(starter && (starter.quickReplies.length > 0 || starter.form));
		return saved.length > 0 && showsChoices(saved.length - 1);
	});

	/**
	 * Send a specific text, from a button rather than the field.
	 *
	 * Goes through exactly the same path as a typed message, and posts the words
	 * the button stands for rather than an id. The transcript then reads as though
	 * the student typed it, the backend's extractor sees ordinary language, and
	 * pressing a button is never a different kind of turn from typing one.
	 */
	function choose(text: string) {
		if (pending) return;
		draft = '';
		if (live) {
			sendLive(text);
			return;
		}
		pushMock(text);
	}

	/**
	 * Whether the choices under a saved message should show.
	 *
	 * The last saved message only, and only while this tab has not moved past it:
	 * once the student has said anything else, the question those buttons answer
	 * is behind them.
	 */
	function showsChoices(index: number) {
		const message = saved[index];
		return (
			index === saved.length - 1 &&
			message.role === 'thrive' &&
			(message.quickReplies.length > 0 || message.form !== null) &&
			sent.length === 0
		);
	}

	function send(event: SubmitEvent) {
		event.preventDefault();

		const body = draft.trim();
		if (!body) return;

		draft = '';

		if (live) {
			sendLive(body);
			return;
		}

		/*
		 * No time label on these. Every stamp in the saved half was formatted on the
		 * server, and a component has no business asking the browser what time it is
		 * to label a message that will not exist in a minute. The "This session"
		 * heading is what places them instead.
		 */
		pushMock(body);
	}

	/** The offline half: the student's line and a reply that says it cannot answer. */
	function pushMock(body: string) {
		sent = [
			...sent,
			{ id: `sent-${nextId++}`, role: 'student', body, timeLabel: '', dayLabel: '',
			  quickReplies: [], form: null },
			{
				id: `sent-${nextId++}`,
				role: 'thrive',
				body: copy.chat.placeholderReply,
				timeLabel: '',
				dayLabel: '',
				quickReplies: [],
				form: null
			}
		];

		scrollToNewest();
	}

	/**
	 * The live half of `send`. See the component doc comment for the full
	 * round trip; this is steps 1-4 of it.
	 */
	async function sendLive(body: string) {
		sent = [
			...sent,
			{ id: `sent-${nextId++}`, role: 'student', body, timeLabel: '', dayLabel: '',
			  quickReplies: [], form: null }
		];
		pending = true;
		scrollToNewest();

		try {
			const response = await fetch('/ask-sync', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify(
					conversation
						? { action: 'message', conversationId: conversation.id, body }
						: { action: 'create', destination, body }
				)
			});

			if (!response.ok) throw new Error('ask-sync request failed');

			const payload = (await response.json()) as { conversation: { id: string } };

			await goto(`/ask/${destination}?c=${payload.conversation.id}`, { invalidateAll: true });

			// The `{#key}` above only remounts for a NEW conversation id; the
			// same-conversation case (a second message in an already-open thread)
			// keeps this component alive, so the optimistic state is cleared here
			// explicitly rather than relying on the remount.
			sent = [];
			pending = false;
		} catch {
			pending = false;
			sent = [
				...sent,
				{ id: `sent-${nextId++}`, role: 'thrive', body: copy.chat.errorReply,
				  timeLabel: '', dayLabel: '', quickReplies: [], form: null }
			];
			scrollToNewest();
		}
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
	{@const bubbleClass = cn(
		'inline-block rounded-md border px-2.5 py-2 text-left text-sm break-words',
		mine ? 'border-line-strong bg-primary text-on-primary' : 'border-line bg-surface text-body'
	)}

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
			<!--
				Student side stays a `<p>` holding a plain text node, exactly as
				before -- it never carries Markdown.

				THRIVE's side is a `<div>`, not a `<p>`, even though it renders
				identically (both are `inline-block`, and Tailwind's preflight zeroes
				default margins on both). A reply can contain a `<ol>` or
				`<blockquote>`, and the HTML parser closes an open `<p>` the instant a
				block-level child like that appears inside it -- which would silently
				pop the list OUT of the bubble as a sibling rather than nest it, taking
				the border and background with the now-empty `<p>` and leaving the
				actual reply unstyled beside it. A `<div>` has no such rule.
			-->
			{#if mine}
				<p class={bubbleClass}>
					<!-- Who spoke, in words. On screen it is carried by the side of the
					     column and the fill; neither of those reaches a screen reader. -->
					<span class="sr-only">{copy.chat.youSaid}</span>
					{message.body}
				</p>
			{:else}
				<div class={bubbleClass}>
					<span class="sr-only">{copy.chat.thriveSaid}</span>
					<RichMessage body={message.body} />
				</div>
			{/if}

			{#if stamped}
				<span class="thrive-numeric mt-0.5 block text-3xs text-muted-ink">
					{message.timeLabel}
				</span>
			{/if}
		</div>
	</div>
{/snippet}

{#snippet ratingForm(form: RatingForm)}
	<!--
		One control per area rather than a flat row of twenty-five buttons.

		`aria-pressed` rather than a radio group: these are buttons that set a
		value, and the pattern already used by the appointments day chips, so it
		reads the same way to a screen reader as the rest of the app. Each row is
		its own labelled group so "Python programming, 1 to 5" is announced before
		the numbers, which are otherwise five anonymous digits.

		`min-h-11` is the 44px touch floor. The number buttons are square-ish and
		wrap, so five of them fit a phone without a sideways scroll.
	-->
	<div class="flex justify-start">
		<div class="min-w-0 max-w-[min(85%,var(--thrive-chat-measure))]">
			<p class="thrive-eyebrow mt-1.5">{copy.chat.ratingLabel}</p>
			<div class="mt-1 space-y-1.5 rounded-md border border-line bg-sunken p-2">
				{#each form.rows as row (row.key)}
					<div>
						<p id={`rate-${row.key}`} class="text-xs text-body">{row.label}</p>
						<div
							role="group"
							aria-labelledby={`rate-${row.key}`}
							class="mt-0.5 flex flex-wrap gap-1"
						>
							{#each form.scale as point (point.value)}
								<button
									type="button"
									disabled={pending}
									aria-pressed={ratingOf(form, row.key) === point.value}
									title={point.help}
									onclick={() => (ratings = { ...ratings, [row.key]: point.value })}
									class={cn(
										'min-h-11 min-w-11 rounded-md border-[1.5px] text-sm',
										ratingOf(form, row.key) === point.value
											? 'border-line-strong bg-primary text-on-primary'
											: 'border-line bg-surface text-ink'
									)}
								>
									{point.label}
								</button>
							{/each}
						</div>
					</div>
				{/each}

				<Button
					type="button"
					variant="primary"
					disabled={pending}
					class="min-h-11 w-full"
					onclick={() => submitRatings(form)}
				>
					{form.submitLabel}
				</Button>
			</div>
			<p class="mt-1 text-3xs text-muted-ink">{copy.chat.ratingHint}</p>
		</div>
	</div>
{/snippet}

{#snippet quickReplyRow(replies: ConversationStarter['quickReplies'])}
	<!--
		Only ever rendered under the NEWEST reply — see `showsQuickReplies`. The
		buttons answer the question that was just asked, so leaving them on older
		turns would offer a student a shortcut to re-answer something already
		settled, and pressing one would read as editing history rather than adding
		to it.

		`min-h-11` is 44px, the touch-target floor `check:interaction` asserts. The
		row wraps rather than scrolling sideways: six role names do not fit a phone
		on one line, and a horizontally scrolling strip hides choices behind an
		edge with nothing to suggest they are there.
	-->
	<div class="flex justify-start">
		<div class="min-w-0 max-w-[min(85%,var(--thrive-chat-measure))]">
			<p id="quick-replies-label" class="thrive-eyebrow mt-1.5">
				{copy.chat.quickRepliesLabel}
			</p>
			<div
				role="group"
				aria-labelledby="quick-replies-label"
				class="mt-1 flex flex-wrap gap-1.5"
			>
				{#each replies as reply (reply.send)}
					<!--
						The description sits ON the button rather than in a bullet list
						above it. The interview used to print both — a list of options
						with their explanations, then a row of buttons repeating the
						labels — which made one question five stacked blocks and split
						each choice from what it means.

						`items-start` and `text-left`: with two lines a centred button
						reads as a heading with a caption, and these are controls.
					-->
					<button
						type="button"
						disabled={pending}
						onclick={() => choose(reply.send)}
						class={cn(
							'flex min-h-11 flex-col justify-center rounded-md border-[1.5px] border-line-strong bg-surface px-2.5 text-left text-sm text-ink',
							reply.description && 'py-1'
						)}
					>
						<span>{reply.label}</span>
						{#if reply.description}
							<span class="text-3xs font-normal text-muted-ink">{reply.description}</span>
						{/if}
					</button>
				{/each}
			</div>
			<p class="mt-1 text-3xs text-muted-ink">{copy.chat.quickRepliesHint}</p>
		</div>
	</div>
{/snippet}

<!--
	`h-full` above `xl` is what makes the LOG the scroller rather than the
	document: the height it fills comes from the section (`--thrive-ask-height` in
	`app.css`), which is why this is `h-full` rather than a number of its own — the
	panel used to carry a flat 34rem and stopped two-thirds of the way down a tall
	screen. A phone deliberately gets no height at all; see the token's note.

	`flex-1` starts at `lg`, and what it governs changes with the axis.

	Between `lg` and `xl` this is a child of a `flex-col` whose height is now
	definite (the section owns it), so `flex-1` governs HEIGHT and is exactly what
	makes the chat fill the room the header and the history strip do not take.
	Above `xl` the parent turns into a `flex-row`, `flex-1` governs WIDTH instead,
	and `h-full` supplies the height.

	This was gated on `xl` for a while, back when the panel carried its own fixed
	height: a column child with an ungated `flex-1` has `flex-basis: 0%` plus grow,
	which silently beats an `h-` beside it, so the panel took its content's height,
	the log never overflowed, and the document scrolled in its place. That is only
	a hazard when the two rules DISAGREE — with the height coming from the parent
	instead, growing to fill it is the whole point.

	That mistake shipped once, and `check:interaction` caught it by SKIPPING its own
	keyboard-scroll assertion — "could not make the log overflow" — which is the
	quietest possible failure and still louder than the layout, which looked fine.
	Worth knowing that a skip is the signal here, not a failure.
-->
<section
	aria-labelledby="ask-destination-heading"
	class="thrive-panel flex min-h-0 min-w-0 flex-col p-0 lg:min-h-0 lg:flex-1 xl:h-full"
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
			empty && !starter ? 'grid place-items-center' : 'space-y-2.5'
		)}
	>
		{#if empty && starter}
			<!--
				Opening ON the first question, rather than on a box that has to be
				typed into before the question appears.

				Rendered as a THRIVE bubble because that is what it is -- the same text
				the bot sends, arriving before the student has had to ask for it. The
				buttons underneath go through the same `choose` a real reply's buttons
				use, and because `conversation` is null that first press CREATES the
				conversation, so nothing here is a special case downstream.
			-->
			{@render bubble(
				{ id: 'starter', role: 'thrive', body: starter.body, timeLabel: '',
				  dayLabel: '', quickReplies: starter.quickReplies, form: starter.form ?? null },
				false
			)}
			{#if starter.form}
				{@render ratingForm(starter.form)}
			{/if}
			{#if starter.quickReplies.length > 0}
				{@render quickReplyRow(starter.quickReplies)}
			{/if}
		{:else if empty}
			<!--
				No script for this destination, so say what it CAN help with. A blank
				box would make the three surfaces indistinguishable, which is the whole
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

			{#if showsChoices(index)}
				{#if message.form}
					{@render ratingForm(message.form)}
				{/if}
				{#if message.quickReplies.length > 0}
					{@render quickReplyRow(message.quickReplies)}
				{/if}
			{/if}
		{/each}

		{#if sent.length > 0}
			<p class="thrive-eyebrow pt-1 text-center">{copy.chat.draftHeading}</p>

			{#each sent as message (message.id)}
				{@render bubble(message, false)}
			{/each}

			{#if pending}
				<!--
					Not part of `sent`: it is a status, not a message, and it must not
					survive into the "keep the student bubble" failure branch alongside a
					second, separately-pushed error bubble. `role="log"` /
					`aria-live="polite"` on the container above already announces this the
					same way a real reply would be announced.
				-->
				{@render bubble(
					{ id: 'pending', role: 'thrive', body: copy.chat.pendingReply,
					  timeLabel: '', dayLabel: '', quickReplies: [], form: null },
					false
				)}
			{/if}
		{/if}
	</div>

	<form onsubmit={send} class="flex items-end gap-2 border-t border-line bg-sunken p-2.5">
		<label for="ask-composer" class="sr-only">
			{awaitingAnswer ? copy.chat.answerLabel : copy.chat.composerLabel}
		</label>

		<input
			id="ask-composer"
			name="question"
			bind:value={draft}
			autocomplete="off"
			disabled={pending}
			placeholder={awaitingAnswer ? copy.chat.answerPlaceholder : copy.chat.placeholder}
			class="min-h-11 min-w-0 flex-1 rounded-md border-[1.5px] border-line-strong bg-surface px-2.5 text-sm text-ink placeholder:text-muted-ink"
		/>

		<Button
			type="submit"
			variant="primary"
			disabled={pending || draft.trim().length === 0}
			class="min-h-11"
		>
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
