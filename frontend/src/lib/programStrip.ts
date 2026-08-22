import { messages } from '$lib/messages';
import type { PhaseStatus } from '$lib/data';

/**
 * "Summer 2026" -> "Sum 26", for the compact strip on narrow screens.
 *
 * Six full terms need roughly 75px each and a phone gives them about 58, so the
 * choice is between abbreviating and truncating. Truncation produces "Summ…",
 * which names nothing; a known short form still reads as a term.
 *
 * Falls back to the input UNCHANGED when the shape is not "Season YYYY", so an
 * unexpected term is passed through rather than mangled. That matters more than
 * it looks: the term string comes from `buildProgramTimeline`, which builds it
 * from a season and a year for five phases but falls back to
 * `toLocaleDateString` for a phase with no season -- so a non-matching shape is
 * a real possibility, not a defensive hypothetical.
 */
export function abbreviateTerm(term: string): string {
	const match = /^(Summer|Fall|Winter|Spring) (\d{4})$/.exec(term);
	if (!match) return term;

	const short: Record<string, string> = {
		Summer: 'Sum',
		Fall: 'Fall',
		Winter: 'Win',
		Spring: 'Spr'
	};

	return `${short[match[1]]} ${match[2].slice(2)}`;
}

/**
 * A phase status as a word, for the screen-reader-only label under each pip.
 *
 * The pips carry status in fill and stroke, which is colour and shape -- neither
 * reaches a screen reader. This is the same information as prose.
 */
export const phaseStatusWord: Record<PhaseStatus, string> = {
	complete: messages.home.timeline.statusComplete,
	current: messages.home.timeline.statusCurrent,
	upcoming: messages.home.timeline.statusUpcoming
};
