import {
	categoryLabel,
	groupDayItems,
	type ScheduleCategory,
	type ScheduleItem
} from '$lib/schedule';
import type { DayGroupMode } from '$lib/schedule';

/**
 * The selected day's arithmetic.
 *
 * Everything `CalendarView` and `CalendarHeader` used to decide inline: how the
 * day's items divide into groups, how they cluster into squares, and how the
 * breakdown line counts them.
 *
 * ## Why these are here and not in the components
 *
 * Vitest runs in Node with no jsdom, so nothing in this repo renders. Logic left
 * inside a `.svelte` file is therefore logic no gate can see -- and each of the
 * three functions below has a branch that has ALREADY been got wrong once in this
 * codebase or its prototype:
 *
 *   - the breakdown pluralised "1 classes"
 *   - the day's two slices were concatenated without re-sorting, so every task
 *     landed after every class no matter when it was due
 *   - a section's fraction counted items that could not be ticked
 *
 * None of those is visible to a type. All three are visible to a test.
 *
 * The one thing deliberately NOT here is copy. `dayCountParts` returns the
 * numbers and the two word-forms; `messages.calendar.header.countPart` decides
 * what to do with them, because "4 classes" is a sentence fragment and word
 * order belongs to a translation rather than to arithmetic.
 */

/* --- The square strip --------------------------------------------------- */

export interface SquareCell {
	id: string;
	/** The item's title, spoken and shown on hover. */
	label: string;
	done: boolean;
}

/** One cluster. The gap between groups is the only thing that separates them. */
export interface SquareGroup {
	key: string;
	cells: SquareCell[];
}

/**
 * A day's items as square clusters: what the student can finish, then what they
 * are simply committed to.
 *
 * Personal leads because those are the cells that can actually change. The
 * commitments are there for SCALE -- "three of my own things, inside a day that
 * already has four classes in it" -- which is why they are always `done: false`
 * rather than being given a state they cannot have. A class is not a thing you
 * complete, and a filled square saying otherwise would be a lie in a glance.
 *
 * An empty group is dropped rather than pushed as an empty cluster, because a
 * cluster with no cells is an unexplained gap in the strip.
 */
export function squareGroupsFor(
	schedule: ScheduleItem[],
	personal: ScheduleItem[]
): SquareGroup[] {
	const groups: SquareGroup[] = [];

	const cellsFor = (items: ScheduleItem[], done: (item: ScheduleItem) => boolean) =>
		items.map((item) => ({ id: item.id, label: item.title, done: done(item) }));

	if (personal.length > 0) {
		groups.push({ key: 'personal', cells: cellsFor(personal, (item) => item.done === true) });
	}

	if (schedule.length > 0) {
		groups.push({ key: 'schedule', cells: cellsFor(schedule, () => false) });
	}

	return groups;
}

/* --- The day's groups --------------------------------------------------- */

export interface DayGroup {
	key: string;
	heading: string;
	items: ScheduleItem[];
}

/**
 * All-day first, then by time, then by title.
 *
 * The sort is not redundant with `itemsForDay`, and that is the bug worth
 * naming. `itemsForDay` sorts the day correctly; the caller then takes two
 * FILTERED SLICES of it -- commitments and personal items -- and concatenates
 * them. Concatenating two sorted lists does not give a sorted list, so without
 * this every task landed after every class regardless of when it was due.
 */
export function sortDayItems(items: ScheduleItem[]): ScheduleItem[] {
	return [...items].sort((a, b) => {
		if (a.allDay !== b.allDay) return a.allDay ? -1 : 1;
		if (a.sortMinutes !== b.sortMinutes) return a.sortMinutes - b.sortMinutes;
		return a.title.localeCompare(b.title);
	});
}

/**
 * Arrange the day's non-event items: split into fixed type groups, or left as
 * one chronological list.
 *
 * Both readings are legitimate and they answer different questions. `type`
 * answers "what do I owe" and runs in `DAY_GROUPS` order -- classes, then what
 * is due, then what the student set themselves, then booked time -- which is the
 * order a day gets planned in rather than the order things happen. `time`
 * answers "what happens next".
 *
 * Events belong to neither. They keep their own section with register controls,
 * a blurb and the "for you" badge; folding them into a generic group would throw
 * all of that away to gain a consistency nobody asked for. The caller passes
 * non-event items only, and `DAY_GROUPS` names no event category so a stray one
 * is dropped rather than silently grouped.
 *
 * An empty day returns an empty array rather than one empty group, so the caller
 * can tell "nothing scheduled" from "one group with nothing in it".
 */
export function arrangeDay(
	items: ScheduleItem[],
	mode: DayGroupMode,
	/** Heading for the single group the `time` arrangement produces. */
	chronologicalHeading: string
): DayGroup[] {
	const sorted = sortDayItems(items);

	if (mode === 'time') {
		return sorted.length === 0
			? []
			: [{ key: 'all', heading: chronologicalHeading, items: sorted }];
	}

	return groupDayItems(sorted);
}

/* --- The breakdown line ------------------------------------------------- */

/**
 * One "4 classes" pair, before it becomes words.
 *
 * `singular` and `plural` rather than a single label plus a rule, because the
 * rule is not general: `class` takes "es" and everything else takes "s". Passing
 * both forms out means the caller's message function never has to know which
 * category it is holding, and a translation gets to disagree about pluralisation
 * entirely.
 */
export interface DayCountPart {
	category: ScheduleCategory;
	count: number;
	singular: string;
	plural: string;
}

/**
 * How many of each kind of thing is on the day, in first-seen order.
 *
 * First-seen rather than `legendOrder`, matching the prototype: the day's items
 * arrive already sorted by time, so the breakdown reads in roughly the order the
 * day happens. Two items of the same category collapse into one entry wherever
 * the first of them fell.
 *
 * Labels are lowercased here because the line is a fragment inside a sentence
 * ("4 classes · 3 tasks"), not a set of chips.
 */
export function dayCountParts(items: ScheduleItem[]): DayCountPart[] {
	const counts = new Map<ScheduleCategory, number>();
	for (const item of items) {
		counts.set(item.category, (counts.get(item.category) ?? 0) + 1);
	}

	return [...counts.entries()].map(([category, count]) => {
		const singular = categoryLabel[category].toLowerCase();
		return {
			category,
			count,
			singular,
			// "1 class" / "4 classes". The one irregular plural in the category list.
			plural: singular === 'class' ? 'classes' : `${singular}s`
		};
	});
}
