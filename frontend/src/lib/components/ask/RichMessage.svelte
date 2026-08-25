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
	 * -- `<p>`, `<ol>`/`<ul>`/`<li>`, `<blockquote>`, `<strong>`, `<code>`,
	 * `<a>`, `<table>` -- never a string handed to the browser to parse as
	 * markup. There is
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
			<!-- Recursive: `inline` renders itself for the bold span's children, so
			     an emphasised link stays a link. -->
			<strong>{@render inline(span.spans)}</strong>
		{:else if span.kind === 'link'}
			<!--
				`rel="noopener noreferrer"` with `target="_blank"`: these hrefs come
				out of a corpus this app did not write, so the opened page must not
				get a `window.opener` handle back into an authenticated THRIVE tab,
				and must not receive this URL as a referrer.

				`parseRichText` has already rejected every scheme except http(s) and
				mailto -- see `SAFE_SCHEME` in `$lib/richtext`. This template is the
				second half of that guarantee, not the first: it renders whatever the
				parser blessed and does no validation of its own.

				Underlined rather than colour-only. The bubble sets the ink for its
				side of the conversation, and a link inside it has to be
				distinguishable without relying on hue.
			-->
			<a
				href={span.href}
				target="_blank"
				rel="noopener noreferrer"
				class="underline underline-offset-2 hover:no-underline"
			>{span.text}</a>
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
	{:else if block.type === 'heading'}
		<!--
			Starts at `h3`, never `h1`.

			The page already owns its heading hierarchy — the panel around this is
			an `h2` — so a reply that injected an `h1` would put a top-level heading
			inside a section, which is exactly the document-outline break screen
			reader users navigate by. Markdown `#` therefore maps to `h3` and each
			further `#` steps down one, capped at `h6`.

			Size is set by level rather than by the tag's default so a `#` and a
			`##` are visibly different without any of them shouting: this is a chat
			bubble, not a document.
		-->
		{@const level = Math.min(block.level + 2, 6)}
		<svelte:element
			this={`h${level}`}
			class={cn(
				'text-left font-medium text-ink',
				block.level === 1 ? 'text-sm' : 'text-xs',
				spacing(index)
			)}
		>
			{@render inline(block.spans)}
		</svelte:element>
	{:else if block.type === 'table'}
		<!--
			The scroll container is not optional. A comparison table of three plans
			of study is wider than a chat bubble on a phone, and a table that
			overflows its bubble pushes the DOCUMENT sideways -- which is the one
			thing `check:layout` fails a page for. `overflow-x-auto` keeps the
			overflow inside the table's own box, so the page never scrolls
			horizontally and the table still scrolls to reveal itself.
		-->
		<div class={cn('max-w-full overflow-x-auto', spacing(index))}>
			<table class="w-full border-collapse text-left text-xs">
				<thead>
					<tr>
						{#each block.head as cell, cellIndex (cellIndex)}
							<th class="border-b border-line-strong px-1.5 py-1 font-medium">
								{@render inline(cell)}
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each block.rows as row, rowIndex (rowIndex)}
						<tr>
							{#each row as cell, cellIndex (cellIndex)}
								<td class="border-b border-hairline px-1.5 py-1 align-top">
									{@render inline(cell)}
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else if block.type === 'blockquote'}
		<!-- The left border is `WeekView`'s day-divider pattern (`border-l
		     border-hairline`), reused for a quote accent rather than a new class. -->
		<blockquote class={cn('border-l border-hairline pl-2 text-left', spacing(index))}>
			{@render lines(block.lines)}
		</blockquote>
	{/if}
{/each}
