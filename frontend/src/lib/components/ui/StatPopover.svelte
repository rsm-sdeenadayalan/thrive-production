<script lang="ts">
	import { tick, type Snippet } from 'svelte';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';

	import { cn } from '$lib/utils';
	import { messages } from '$lib/messages';
	import { clickOutside } from '$lib/actions/clickOutside';
	import { escapeKey } from '$lib/actions/escapeKey';
	import type { RevealItem } from '$lib/reveal';

	/**
	 * The list behind a number.
	 *
	 * A stat pill says "3 overdue" and this is what it opens: the three actual
	 * tasks, each one a jump to its row on the page. Wraps a trigger rather than
	 * being one, so the pill keeps its own look and this keeps the behaviour.
	 *
	 * ## Click, and only click
	 *
	 * This opened on hover as well, gated on `(hover: hover)`, and it was tried and
	 * rejected on 2026-08-21: three pills sit in one row, so a cursor crossing that
	 * row opened and closed panels nobody asked for. The panel that appears where
	 * you are not looking is noise, and the panel that vanishes as you reach for it
	 * is worse.
	 *
	 * Click is unambiguous, works on every device, and was always the primary path.
	 * Pressing the pill again closes it.
	 *
	 * Hover-to-reveal in this app is CSS -- Tailwind's `hover:` utilities, which
	 * compile to `@media (hover: hover)`. Nothing here needs a JavaScript opinion
	 * about what a hovering device is any more, and `hoverIntent` went with the
	 * behaviour rather than being kept in case something wanted it.
	 *
	 * ## Opening moves focus into the list
	 *
	 * Unconditionally, now that the only way in is a deliberate press. A student who
	 * clicks a pill is asking to read the list, and putting focus on its first item
	 * is what makes the next keystroke work.
	 *
	 * ## Dismissal, and the one focus rule
	 *
	 * Escape, a pointer down outside, or focus leaving the widget. All three route
	 * through `dismiss()`, which restores focus to the trigger IF AND ONLY IF focus
	 * is currently inside the panel. That condition is nearly always true now, but
	 * it is the honest form of the rule and it costs nothing: a dismissal must never
	 * MOVE focus, only give it back when it was holding it.
	 *
	 * Choosing an item is the exception, and `dismiss(HAND_OFF)` names it: focus is
	 * about to land on the revealed row, so it must not be pulled back to the pill
	 * on the way. Focus follows the jump, not the dismissal.
	 *
	 * ## Why this is a list and not a menu
	 *
	 * `role="menu"` brings menu keyboard semantics with it -- a single tab stop,
	 * Tab exits, arrow keys are the only way through. That is right for a command
	 * menu and wrong here: these are jump targets, so every one is an ordinary
	 * button in the tab order, and the arrow keys are a convenience on top rather
	 * than the only way through.
	 */
	let {
		items,
		onSelect,
		listLabel,
		triggerClass,
		children
	}: {
		/** Never empty: a caller with nothing to list must not render a popover. */
		items: RevealItem[];
		onSelect: (item: RevealItem) => void;
		/** Names the list for assistive tech, e.g. "3 overdue". */
		listLabel: string;
		/** Applied to the trigger button, so the pill keeps its own look. */
		triggerClass?: string;
		/** The trigger's content. */
		children: Snippet;
	} = $props();

	/** Passed to `dismiss` when focus is about to be placed somewhere else. */
	const HAND_OFF = true;

	const panelId = $props.id();
	const labelId = `${panelId}-label`;

	/*
	 * One boolean, because there is now one way in.
	 *
	 * This was `openedBy: 'pointer' | 'command' | null` while the popover also
	 * opened on hover, and it had to be: with a bare boolean, hover opened the panel
	 * and the click that followed found it open and closed it, so pressing a pill
	 * did nothing at all. Recording WHY it was open is what told a pointer leaving
	 * that it had not been the one to open it.
	 *
	 * Hover is gone, so that distinction has nothing left to distinguish and it is
	 * removed rather than left as a branch that can only ever take one value.
	 */
	let open = $state(false);
	let triggerEl = $state<HTMLButtonElement | null>(null);
	let panelEl = $state<HTMLDivElement | null>(null);

	function itemButtons(): HTMLButtonElement[] {
		return panelEl ? [...panelEl.querySelectorAll<HTMLButtonElement>('button[data-item]')] : [];
	}

	/** `edge` is which end to land on, for ArrowUp opening from the trigger. */
	async function openPanel(edge: 'first' | 'last' = 'first') {
		open = true;

		// The panel does not exist until Svelte has flushed the state above.
		await tick();
		const buttons = itemButtons();
		(edge === 'last' ? buttons.at(-1) : buttons.at(0))?.focus();
	}

	function dismiss(handOff = false) {
		if (!open) return;

		const held = !handOff && panelEl?.contains(document.activeElement);
		open = false;
		if (held) triggerEl?.focus();
	}

	function onTriggerClick() {
		if (open) dismiss();
		else void openPanel();
	}

	function onTriggerKeydown(event: KeyboardEvent) {
		// Enter and Space already fire `click`. These two are the extra affordance
		// a disclosure holding a list is expected to have.
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			void openPanel('first');
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			void openPanel('last');
		}
	}

	/**
	 * Arrow, Home and End across the items.
	 *
	 * On each ITEM rather than on the panel. Focus is always on an item when these
	 * keys should do anything, so the panel was the wrong place twice over: it put
	 * a keydown handler on a `<div>` with no role, and it would have fired for keys
	 * pressed while focus was somewhere else inside the panel entirely.
	 */
	function onItemKeydown(event: KeyboardEvent) {
		const buttons = itemButtons();
		if (buttons.length === 0) return;

		const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
		let next: number | null = null;

		if (event.key === 'ArrowDown') next = at < 0 ? 0 : (at + 1) % buttons.length;
		else if (event.key === 'ArrowUp')
			next = at < 0 ? buttons.length - 1 : (at - 1 + buttons.length) % buttons.length;
		else if (event.key === 'Home') next = 0;
		else if (event.key === 'End') next = buttons.length - 1;

		if (next === null) return;
		event.preventDefault();
		buttons[next].focus();
	}

	/**
	 * Tab out of the widget closes it.
	 *
	 * `relatedTarget` is where focus is GOING. A move between two items inside the
	 * panel keeps it, so the check has to be against the whole widget rather than
	 * against the panel alone. Hand off, because focus has already left and pulling
	 * it back would trap the student in a popover they just tabbed out of.
	 */
	function onWidgetFocusout(event: FocusEvent) {
		const going = event.relatedTarget;
		if (going instanceof Node && event.currentTarget instanceof Node) {
			if (event.currentTarget.contains(going)) return;
		}
		dismiss(HAND_OFF);
	}

	function choose(item: RevealItem) {
		dismiss(HAND_OFF);
		onSelect(item);
	}
</script>

<!-- The positioning context for the panel, and the focus boundary for the whole
     widget. `onfocusout` is a focus event and does bubble, so it belongs here.
     No pointer handlers: this element carried the hover opener, and with that
     gone it is markup with no behaviour of its own. -->
<div class="relative" onfocusout={onWidgetFocusout}>
	<button
		bind:this={triggerEl}
		type="button"
		aria-expanded={open}
		aria-controls={panelId}
		onclick={onTriggerClick}
		onkeydown={onTriggerKeydown}
		class={cn('text-left', triggerClass)}
	>
		{@render children()}
	</button>

	{#if open}
		<!-- Mounted only while open, which is what makes `escapeKey` and
		     `clickOutside` need no open state of their own: their listeners exist
		     exactly as long as the thing they dismiss. `aria-controls` names an id
		     that is absent while closed, which is the accepted cost of that -- the
		     alternative is a permanently mounted panel and two permanently mounted
		     document listeners per pill. -->
		<div
			bind:this={panelEl}
			id={panelId}
			use:escapeKey={() => dismiss()}
			use:clickOutside={{ onOutside: () => dismiss(), alsoInside: [triggerEl] }}
			class="thrive-popover absolute top-full left-0 z-20 mt-1 rounded-lg border border-line bg-surface p-1"
		>
			<p id={labelId} class="thrive-eyebrow px-2 py-1">{listLabel}</p>

			<ul aria-labelledby={labelId} class="max-h-60 overflow-y-auto overscroll-contain">
				{#each items as item (item.target.id)}
					<li>
						<button
							data-item
							type="button"
							onclick={() => choose(item)}
							onkeydown={onItemKeydown}
							class="thrive-row group flex w-full min-h-11 items-start gap-2 px-2 py-1.5 text-left lg:min-h-9"
						>
							<span class="min-w-0 flex-1">
								<span class="block text-xs font-medium break-words text-ink">{item.title}</span>
								<span
									class="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-3xs text-muted-ink"
								>
									<span>{item.detail}</span>
									{#if item.value}
										<span aria-hidden="true">·</span>
										<span class="thrive-numeric">{item.value}</span>
									{/if}
								</span>
							</span>

							<!-- Says the row goes somewhere. The words are for screen
							     readers, since the arrow alone is not a name. -->
							<ArrowRight
								aria-hidden="true"
								class="mt-0.5 size-3 shrink-0 text-muted-ink transition-transform duration-(--motion-fast) ease-standard group-hover:translate-x-0.5"
							/>
							<span class="sr-only">{messages.home.stats.jumpTo(item.title)}</span>
						</button>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
</div>
