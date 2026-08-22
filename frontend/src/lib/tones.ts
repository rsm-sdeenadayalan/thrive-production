import type { Standing } from '$lib/data';
import type { DueUrgency } from '$lib/format';

/**
 * Where a meaning becomes a colour.
 *
 * Every map in this file is the ONLY place its particular translation happens.
 * They live in a `.ts` rather than inside the components that use them for two
 * reasons: a Svelte component cannot export a type cleanly, and these are the
 * part of the visual system worth testing -- a map is exhaustive or it is not,
 * and `Record<Union, T>` makes that a compile error rather than a missing chip.
 *
 * The class strings name design-system utilities and nothing else. No hex, no
 * raw sizes -- `designSystem.spec.ts` fails the build on either.
 */

export type TagTone =
	| 'neutral'
	| 'quiet'
	| 'primary'
	| 'urgent'
	| 'watch'
	| 'on-track'
	| 'needs-help'
	| 'civic'
	| 'later';

/**
 * Solid fills carrying white text, measured in the contrast gate.
 *
 * `neutral` and `quiet` stay unfilled on purpose: a course code is a fact, not
 * a status, and if everything shouts then nothing does.
 */
export const tagTones: Record<TagTone, string> = {
	neutral: 'border border-line bg-surface text-body',
	quiet: 'text-muted-ink',
	primary: 'bg-primary text-on-primary',
	urgent: 'bg-urgent text-on-primary',
	watch: 'bg-watch text-on-primary',
	'on-track': 'bg-on-track text-on-primary',
	'needs-help': 'bg-needs-help text-on-primary',
	civic: 'bg-civic text-on-primary',
	later: 'bg-later text-on-primary'
};

/**
 * A standing becomes a tone in exactly one place.
 *
 * Note `onTrack` is the teal that replaced the old blue when primary became
 * navy -- the token moved, this map did not.
 */
export const standingTone: Record<Standing, TagTone> = {
	onTrack: 'on-track',
	watch: 'watch',
	needsHelp: 'needs-help'
};

/**
 * A due descriptor becomes a tone.
 *
 * `upcoming` is deliberately `quiet` -- no fill. Most tasks are upcoming, and a
 * filled chip on every row would make the two that matter invisible.
 *
 * `unknown` is the fourth state added in Phase 3a-fix. It gets `neutral`, not a
 * status tone: "how urgent is it" has no answer for a date that does not exist,
 * and tinting it would be inventing one.
 */
export const urgencyTone: Record<DueUrgency | 'unknown', TagTone> = {
	overdue: 'urgent',
	today: 'watch',
	upcoming: 'quiet',
	unknown: 'neutral'
};

/** Stat pill tints. `calm` is the zero state. */
export type StatTone = 'urgent' | 'watch' | 'primary' | 'calm';

/**
 * A count of nothing is not an alarm.
 *
 * `calm` exists so a coral pill does not permanently read "0 overdue", which is
 * manufactured anxiety with no payoff -- a good day has to be able to look
 * different from a bad one.
 */
export const statTones: Record<StatTone, { wrap: string; icon: string }> = {
	urgent: { wrap: 'bg-urgent-soft text-urgent', icon: 'text-urgent' },
	watch: { wrap: 'bg-watch-soft text-watch', icon: 'text-watch' },
	primary: { wrap: 'bg-primary-soft text-primary', icon: 'text-primary' },
	// muted-ink for the icon, not faint: faint on sunken is 3.16:1, and a
	// meaningful graphic owes 3:1 -- too close to spend on decoration.
	calm: { wrap: 'bg-sunken text-muted-ink', icon: 'text-muted-ink' }
};

/** Which token paints a progress fill. `primary` is the neutral default. */
export type ProgressTone = 'primary' | Standing;

export const progressTones: Record<ProgressTone, string> = {
	primary: 'bg-primary',
	onTrack: 'bg-on-track',
	watch: 'bg-watch',
	needsHelp: 'bg-needs-help'
};

/**
 * The nudge callout on a course card, tinted by that course's standing.
 *
 * Only two standings produce a nudge in practice, so this is `Partial` and the
 * caller falls back to the primary tint. Carries a stroke of its own hue: a
 * tinted block with no edge disappeared against the panel it sits in.
 */
export const nudgeTones: Partial<Record<Standing, string>> = {
	watch: 'border-watch bg-watch-soft text-watch',
	needsHelp: 'border-needs-help bg-needs-help-soft text-needs-help'
};

export const nudgeToneFallback = 'border-primary bg-primary-soft text-primary-hover';
