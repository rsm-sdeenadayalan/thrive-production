<script lang="ts">
	import { standingLabel } from '$lib/format';
	import { standingTone } from '$lib/tones';
	import type { Standing } from '$lib/data';

	import Tag from './Tag.svelte';

	/**
	 * A standing as dot plus word.
	 *
	 * The dot is not decoration: it is what makes the state survive grayscale and
	 * the common forms of colour blindness. The word is what makes it survive not
	 * knowing the colour code at all.
	 *
	 * `standingTone` is the only place a `Standing` becomes a `TagTone`, and
	 * `standingLabel` the only place it becomes a word.
	 */
	let { standing }: { standing: Standing } = $props();
</script>

<Tag tone={standingTone[standing]} dot>{standingLabel[standing]}</Tag>
