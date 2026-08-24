<script lang="ts">
	/**
	 * A score, drawn as a ring rather than only a number.
	 *
	 * Pure SVG -- two stacked circles and nothing else drawing the arc, so the
	 * one ring in the app costs no charting dependency. `value` is assumed
	 * already clamped 0-100 -- callers pass `ringPercent(score)` from `$lib/jobs`
	 * rather than this component re-deriving that rule.
	 *
	 * ## Two tones, not a colour scale
	 *
	 * `tone="primary"` is a report-backed score, the strongest signal a card can
	 * show; `tone="muted"` is the hybrid search estimate every posting starts
	 * with. A literal colour scale (green through red) would smuggle in a
	 * verdict this component was never asked to render -- `JobCompetency`
	 * already carries that judgement, as a `Tag`, on the card around this ring.
	 *
	 * ## Rotating the whole `<svg>`, not one circle
	 *
	 * A plain circle's dash pattern starts at 3 o'clock. Rotating the SVG -90°
	 * moves that start to 12 o'clock for BOTH circles at once -- the track is a
	 * full circle, so its own rotation is invisible, which is what makes
	 * rotating the pair simpler than rotating the arc alone around an off-center
	 * transform origin.
	 */
	const RADIUS = 18;
	const CIRCUMFERENCE = 113.097; // 2 * PI * RADIUS, spelled out per the spec.

	let {
		value,
		label,
		tone = 'primary'
	}: {
		/** 0-100. Already clamped by the caller. */
		value: number;
		/** The ring's accessible name -- the arc is decorative without it. */
		label: string;
		tone?: 'primary' | 'muted';
	} = $props();

	const dash = $derived((value / 100) * CIRCUMFERENCE);
</script>

<div class="relative inline-grid size-12 shrink-0 place-items-center" role="img" aria-label={label}>
	<svg viewBox="0 0 40 40" class="size-12 -rotate-90" aria-hidden="true">
		<circle cx="20" cy="20" r={RADIUS} fill="none" stroke="currentColor" stroke-width="4" class="text-line" />
		<circle
			cx="20"
			cy="20"
			r={RADIUS}
			fill="none"
			stroke="currentColor"
			stroke-width="4"
			stroke-linecap="round"
			stroke-dasharray={`${dash} ${CIRCUMFERENCE}`}
			class={tone === 'primary' ? 'text-primary' : 'text-muted-ink'}
		/>
	</svg>
	<span class="thrive-numeric absolute text-sm font-semibold text-ink">{value}</span>
</div>
