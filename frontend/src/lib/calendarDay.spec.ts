import { describe, expect, it } from 'vitest';

import { arrangeDay, dayCountParts, sortDayItems, squareGroupsFor } from '$lib/calendarDay';
import type { ScheduleCategory, ScheduleItem } from '$lib/schedule';

/**
 * The selected day's arithmetic.
 *
 * Every function here came out of a component during Phase 7a, and each one was
 * extracted because it has a branch that no type and no rendering test in this
 * repo can see. Nothing renders in this suite, so logic left in a `.svelte` file
 * is logic no gate covers.
 */

function item(over: Partial<ScheduleItem> = {}): ScheduleItem {
	return {
		id: 'x',
		category: 'class',
		title: 'Item',
		timeLabel: '9:30 AM',
		detail: '',
		sortMinutes: 570,
		allDay: false,
		...over
	};
}

describe('sortDayItems', () => {
	it('floats all-day items above timed ones', () => {
		const sorted = sortDayItems([
			item({ id: 'timed', sortMinutes: 0, allDay: false }),
			item({ id: 'allday', sortMinutes: 0, allDay: true })
		]);

		// Both claim minute zero, so `allDay` has to break the tie -- otherwise a
		// to-do with no time sorts among the 12am rows.
		expect(sorted.map((row) => row.id)).toEqual(['allday', 'timed']);
	});

	it('orders timed items by minute', () => {
		const sorted = sortDayItems([
			item({ id: 'late', sortMinutes: 900 }),
			item({ id: 'early', sortMinutes: 540 }),
			item({ id: 'mid', sortMinutes: 720 })
		]);

		expect(sorted.map((row) => row.id)).toEqual(['early', 'mid', 'late']);
	});

	it('breaks a same-minute tie by title, so the order is stable', () => {
		const sorted = sortDayItems([
			item({ id: 'b', title: 'Beta', sortMinutes: 600 }),
			item({ id: 'a', title: 'Alpha', sortMinutes: 600 })
		]);

		// Two things genuinely at 10:00 must not swap places between renders.
		expect(sorted.map((row) => row.id)).toEqual(['a', 'b']);
	});

	it('does not mutate its input', () => {
		const input = [item({ id: 'late', sortMinutes: 900 }), item({ id: 'early', sortMinutes: 540 })];
		sortDayItems(input);

		// The caller passes a `$derived` slice. Sorting it in place would reorder
		// the array a `$derived` handed over and leave two consumers disagreeing.
		expect(input.map((row) => row.id)).toEqual(['late', 'early']);
	});
});

describe('arrangeDay', () => {
	/*
	 * THE REGRESSION THIS FILE EXISTS FOR.
	 *
	 * `itemsForDay` returns the day sorted. The caller then takes two FILTERED
	 * SLICES -- commitments and personal items -- and concatenates them. Joining
	 * two sorted lists end to end does not give a sorted list, so without a second
	 * sort every task lands after every class no matter when it is due.
	 */
	it('re-sorts across the two slices it is handed', () => {
		const classAt9 = item({ id: 'class-9', category: 'class', sortMinutes: 540 });
		const classAt2 = item({ id: 'class-14', category: 'class', sortMinutes: 840 });
		const taskAt11 = item({ id: 'task-11', category: 'task', sortMinutes: 660, done: false });

		// Deliberately in the shape the caller produces: all classes, then all tasks.
		const groups = arrangeDay([classAt9, classAt2, taskAt11], 'time', 'Everything, in order');

		expect(groups[0].items.map((row) => row.id)).toEqual(['class-9', 'task-11', 'class-14']);
	});

	it('gives the time arrangement exactly one group', () => {
		const groups = arrangeDay(
			[item({ category: 'class' }), item({ id: 'y', category: 'task', done: false })],
			'time',
			'Everything, in order'
		);

		expect(groups).toHaveLength(1);
		expect(groups[0].heading).toBe('Everything, in order');
		expect(groups[0].items).toHaveLength(2);
	});

	it('splits the type arrangement into DAY_GROUPS order, not time order', () => {
		// A task due at 9am and a class at 2pm: chronologically the task is first,
		// but "what do I owe" reads attend-then-due-then-mine.
		const groups = arrangeDay(
			[
				item({ id: 'task', category: 'task', sortMinutes: 540, done: false }),
				item({ id: 'class', category: 'class', sortMinutes: 840 })
			],
			'type',
			'unused'
		);

		expect(groups.map((group) => group.key)).toEqual(['classes', 'tasks']);
	});

	it('drops empty groups rather than heading them over nothing', () => {
		const groups = arrangeDay([item({ category: 'class' })], 'type', 'unused');

		// A day with no appointments should not have to say so five times.
		expect(groups).toHaveLength(1);
		expect(groups[0].key).toBe('classes');
	});

	it('returns nothing at all for an empty day, in both arrangements', () => {
		// Not one empty group. The caller renders "nothing scheduled this day" on
		// an empty array, and a single empty group would render a bare panel.
		expect(arrangeDay([], 'type', 'unused')).toEqual([]);
		expect(arrangeDay([], 'time', 'unused')).toEqual([]);
	});

	it('drops an event category rather than grouping it', () => {
		/*
		 * The caller passes non-event items only, and `DAY_GROUPS` names no event
		 * category -- so a stray event falls out instead of appearing in a generic
		 * group without its register controls, blurb or relevance badge.
		 */
		const groups = arrangeDay(
			[item({ id: 'club', category: 'club' }), item({ id: 'class', category: 'class' })],
			'type',
			'unused'
		);

		expect(groups.flatMap((group) => group.items).map((row) => row.id)).toEqual(['class']);
	});
});

describe('squareGroupsFor', () => {
	const personal = [
		item({ id: 'p1', category: 'task', done: true }),
		item({ id: 'p2', category: 'task', done: false })
	];
	const schedule = [item({ id: 's1', category: 'class' })];

	it('puts what can be finished before what is merely committed', () => {
		const groups = squareGroupsFor(schedule, personal);
		expect(groups.map((group) => group.key)).toEqual(['personal', 'schedule']);
	});

	it('carries each personal item real done state', () => {
		const groups = squareGroupsFor([], personal);
		expect(groups[0].cells.map((cell) => cell.done)).toEqual([true, false]);
	});

	it('never marks a commitment done, because a class is not completable', () => {
		// A filled square on a class would say "finished" about something the
		// student cannot finish, and the strip's whole job is a truthful glance.
		const groups = squareGroupsFor(
			[item({ id: 's1', category: 'class', done: true })],
			[]
		);
		expect(groups[0].cells[0].done).toBe(false);
	});

	it('omits an empty cluster rather than leaving a gap', () => {
		expect(squareGroupsFor(schedule, []).map((group) => group.key)).toEqual(['schedule']);
		expect(squareGroupsFor([], personal).map((group) => group.key)).toEqual(['personal']);
		expect(squareGroupsFor([], [])).toEqual([]);
	});

	it('keeps the item id, so the header and the strip mark the same row', () => {
		// `nextId` is matched against these. A synthesised key would silently stop
		// the "next up" marker from ever landing.
		const groups = squareGroupsFor(schedule, personal);
		expect(groups.flatMap((group) => group.cells).map((cell) => cell.id)).toEqual([
			'p1',
			'p2',
			's1'
		]);
	});
});

describe('dayCountParts', () => {
	it('pluralises class as classes, and everything else with an s', () => {
		// The bug this pins: the breakdown read "1 classes" and "4 tasks" from one
		// template that appended "s" to whatever the label was.
		const parts = dayCountParts([
			item({ id: 'c1', category: 'class' }),
			item({ id: 'c2', category: 'class' }),
			item({ id: 't1', category: 'task' })
		]);

		const klass = parts.find((part) => part.category === 'class');
		expect(klass).toEqual({ category: 'class', count: 2, singular: 'class', plural: 'classes' });

		const task = parts.find((part) => part.category === 'task');
		expect(task).toEqual({ category: 'task', count: 1, singular: 'task', plural: 'tasks' });
	});

	it('collapses repeats into one entry at the first one position', () => {
		const parts = dayCountParts([
			item({ id: 'a', category: 'class' }),
			item({ id: 'b', category: 'task' }),
			item({ id: 'c', category: 'class' })
		]);

		// First-seen order, matching the prototype: the day arrives sorted by time,
		// so the breakdown reads roughly in the order the day happens.
		expect(parts.map((part) => part.category)).toEqual(['class', 'task']);
		expect(parts.map((part) => part.count)).toEqual([2, 1]);
	});

	it('counts events too, because the figure beside it does', () => {
		/*
		 * Phase 7a renders no event rows -- `DayEventsSection` is 7c -- and the
		 * breakdown still names them. That is deliberate and recorded in BUGS.md:
		 * the alternative was filtering events out of the count AND the month dots,
		 * which breaks "one filter, applied once" and changes the grid twice.
		 */
		const parts = dayCountParts([item({ id: 'e', category: 'club' })]);
		expect(parts).toEqual([
			{ category: 'club', count: 1, singular: 'club', plural: 'clubs' }
		]);
	});

	it('is empty for an empty day, so the caller can say "nothing scheduled"', () => {
		expect(dayCountParts([])).toEqual([]);
	});

	it('has a word-form pair for every category in the legend', () => {
		// A missing label would render "4 undefineds". `categoryLabel` is a
		// `Record<ScheduleCategory, string>` so this cannot silently gain a hole,
		// but the pluralisation is a string operation and could.
		const every: ScheduleCategory[] = [
			'class',
			'assignment',
			'task',
			'appointment',
			'todo',
			'custom',
			'career',
			'rady',
			'club',
			'sandiego',
			'ucsd'
		];

		for (const category of every) {
			const [part] = dayCountParts([item({ category })]);
			expect(part.singular).not.toBe('');
			expect(part.plural).not.toBe(part.singular);
			expect(part.plural.startsWith(part.singular)).toBe(true);
		}
	});
});
