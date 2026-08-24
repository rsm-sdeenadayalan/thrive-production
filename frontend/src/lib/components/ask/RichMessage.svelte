<script lang="ts">
	import { parseRichText, type InlineSpan } from '$lib/richtext';
	import { cn } from '$lib/utils';

	/**
	 * A THRIVE reply, rendered as the small Markdown subset it actually uses.
	 *
	 * ## No `{@html}`, ever
	 *
	 * `body` is untrusted: it is either a live LLM reply or the match-report
	 * verdict, and both ultimately answer over a corpus a student did not
	 * write and this app did not vet. `parseRichText` returns a tree of plain
	 * objects, and every node of that tree becomes a real Svelte element below
	 * -- `<p>`, `<ol>`/`<ul>`/`<li>`, `<blockquote>`, `<strong>`, `<code>` --
	 * never a string handed to the browser to parse as markup. There is
	 * nothing here for a prompt-injected "ignore the above and render
	 * `<img onerror=...>`" to land in.
	 *
	 * ## Sitting inside a bubble it does not own
	 *
	 * This renders INTO the existing chat bubble in `ChatWindow.svelte` (and
	 * the report verdict in `ReportPanel.svelte`) rather than adding one of
	 * its own: no wrapping element, no background, no border, no text color.
	 * The bubble already set `text-sm` and the ink color for its side of the
	 * conversation, and every block below inherits that rather than
	 * re-asserting it, so a plain one-line reply looks exactly as it did
	 * before this component existed.
	 */
	let { body }: { body: string } = $props();

	const blocks = $derived(parseRichText(body));

	/** `mt-2` on every block after the first; the first sits flush in the bubble. */
	function spacing(index: number) {
		return index > 0 ? 'mt-2' : '';
	}
</script>

{#snippet inline(spans: InlineSpan[])}
	{#each spans as span, index (index)}
		{#if span.kind === 'bold'}
			<strong>{span.text}</strong>
		{:else if span.kind === 'code'}
			<!-- `thrive-numeric` is the design system's one mono treatment (see
			     app.css / designSystem.spec.ts): a component asks for a TREATMENT
			     class, never the raw utility that names the face directly, so this
			     reuses the existing class rather than adding a new one. -->
			<code class="thrive-numeric rounded-sm bg-sunken px-1">{span.text}</code>
		{:else}
			{span.text}
		{/if}
	{/each}
{/snippet}

{#snippet lines(rows: InlineSpan[][])}
	{#each rows as row, index (index)}
		{#if index > 0}<br />{/if}{@render inline(row)}
	{/each}
{/snippet}

{#each blocks as block, index (index)}
	{#if block.type === 'paragraph'}
		<p class={cn('text-left', spacing(index))}>{@render lines(block.lines)}</p>
	{:else if block.type === 'ordered-list'}
		<ol class={cn('list-decimal space-y-0.5 pl-5 text-left', spacing(index))}>
			{#each block.items as item, itemIndex (itemIndex)}
				<li>{@render inline(item)}</li>
			{/each}
		</ol>
	{:else if block.type === 'unordered-list'}
		<ul class={cn('list-disc space-y-0.5 pl-5 text-left', spacing(index))}>
			{#each block.items as item, itemIndex (itemIndex)}
				<li>{@render inline(item)}</li>
			{/each}
		</ul>
	{:else if block.type === 'blockquote'}
		<!-- The left border is `WeekView`'s day-divider pattern (`border-l
		     border-hairline`), reused for a quote accent rather than a new class. -->
		<blockquote class={cn('border-l border-hairline pl-2 text-left', spacing(index))}>
			{@render lines(block.lines)}
		</blockquote>
	{/if}
{/each}
