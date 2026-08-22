<script lang="ts">
	import EyeOff from '@lucide/svelte/icons/eye-off';

	import { cn } from '$lib/utils';
	import { messages } from '$lib/messages';

	/**
	 * Ignore. Low emphasis on purpose.
	 *
	 * "Count me in" is the action the row exists for and "Add to calendar" is the
	 * useful second; dismissing is a third thing that must not read as equal to
	 * either.
	 *
	 * The visual rules, all deliberate:
	 *  - NO BORDER. Not a control boundary, so the 1.5px stroke does not apply,
	 *    and a decorative hairline would only make it look like a button.
	 *  - `text-muted-ink`, not body and not ink.
	 *  - `font-medium` set here, since weight is not in the type scale and leaving
	 *    it off would render 400 and make this disappear.
	 *  - `min-h-11` even though the type is 13px, because a touch target is about
	 *    the finger, not the glyph.
	 *
	 * Separation from the other two actions is the caller's job: on both surfaces
	 * it sits after a spacer rather than flush in the same button group.
	 */
	let {
		title,
		onIgnore,
		class: className
	}: {
		/** The event title, so the accessible name says which one. */
		title: string;
		onIgnore: () => void;
		class?: string;
	} = $props();
</script>

<button
	type="button"
	onclick={onIgnore}
	class={cn(
		'inline-flex min-h-11 items-center gap-1.5 rounded-md px-2 text-2xs font-medium text-muted-ink',
		'transition-colors duration-(--motion-fast) ease-standard hover:bg-sunken hover:text-body',
		className
	)}
>
	<EyeOff aria-hidden="true" class="size-3.5" />
	{messages.common.ignore}
	<!-- The visible label is one word on every row, so the accessible name has to
	     carry the subject or a screen reader hears "Ignore" four times. -->
	<span class="sr-only">{messages.common.ignoreSubject(title)}</span>
</button>
