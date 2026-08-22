<script lang="ts">
	import { urgencyTone } from '$lib/tones';
	import type { DueDescriptor } from '$lib/format';

	import Tag from './Tag.svelte';

	/**
	 * A `DueDescriptor` as a chip.
	 *
	 * Renders the descriptor's own `label` -- already classified and formatted on
	 * the server -- so nothing here touches a timestamp.
	 *
	 * `upcoming` is deliberately unfilled: most things are upcoming, and a filled
	 * chip on every row makes the two that matter invisible. The fourth state,
	 * `unknown`, gets a neutral chip reading "No date" rather than a status tone,
	 * because a date that does not exist has no urgency to report.
	 */
	let { due }: { due: DueDescriptor } = $props();
</script>

<Tag tone={urgencyTone[due.urgency]}>{due.label}</Tag>
