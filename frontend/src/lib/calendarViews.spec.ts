import { describe, expect, it } from 'vitest';

import {
	AGENDA_DAYS,
	agendaRange,
	showsRowDate,
	undatedTodoItem,
	visibleUndatedTodos
} from '$lib/calendarViews';
import type { QuickItem } from '$lib/quickList';
import { groupAgenda, type ScheduleData } from '$lib/schedule';
import { isTickable } from '$lib/tickItem';

/**
 * The view-level arithmetic.
 *
 * Extracted out of the three views in Phase 7b for the same reason
 * `calendarDay.ts` was extracted out of two components in 7a: nothing renders in
 * this suite, so logic inside a `.svelte` file is logic no gate can see.
 *
 * `weekGrid` is already covered in `schedule.spec.ts` (seven days from Sunday, no
 * shift when already Sunday, and crossing a month boundary without drifting), so
 * it is not repeated here.
 */

function quick(over: Partial<QuickItem> = {}): QuickItem {
	return { id: 'q1', title: 'Email the advisor', done: false, createdAt: 1, ...over };
}

describe('agendaRange', () => {
	it('starts on the day it is given and runs forward', () => {
		const range = agendaRange('2026-08-21', 4);
		expect(range).toEqual(['2026-08-21', '2026-08-22', '2026-08-23', '2026-08-24']);
	});

	it('looks thirty days ahead by default', () => {
		const range = agendaRange('2026-08-21');
		expect(range).toHaveLength(AGENDA_DAYS);
		expect(range[0]).toBe('2026-08-21');
		expect(range[AGENDA_DAYS - 1]).toBe('2026-09-19');
	});

	it('never looks backward', () => {
		// Forward only, by decision. A backward-looking agenda is history, which is
		// a different feature and must not arrive by accident.
		const range = agendaRange('2026-08-21');
		for (const key of range) expect(key >= '2026-08-21').toBe(true);
	});

	it('crosses a month boundary without drifting', () => {
		expect(agendaRange('2026-08-30', 3)).toEqual(['2026-08-30', '2026-08-31', '2026-09-01']);
	});

	it('crosses a year boundary without drifting', () => {
		expect(agendaRange('2026-12-30', 4)).toEqual([
			'2026-12-30',
			'2026-12-31',
			'2027-01-01',
			'2027-01-02'
		]);
	});

	it('crosses a leap day without losing one', () => {
		// 2028 is a leap year, so the 29th exists and must be in the range.
		expect(agendaRange('2028-02-27', 4)).toEqual([
			'2028-02-27',
			'2028-02-28',
			'2028-02-29',
			'2028-03-01'
		]);
	});

	it('produces no duplicates over the full default range', () => {
		// The regression net for an off-by-one in the walk. A range with a repeat
		// would render one day's items twice and silently drop the last day.
		const range = agendaRange('2026-08-21');
		expect(new Set(range).size).toBe(range.length);
	});

	it('returns nothing for a non-positive or fractional count', () => {
		expect(agendaRange('2026-08-21', 0)).toEqual([]);
		expect(agendaRange('2026-08-21', -5)).toEqual([]);
		// Truncates rather than producing a fractional-length array.
		expect(agendaRange('2026-08-21', 2.9)).toHaveLength(2);
	});

	it('feeds groupAgenda a range it can group by day', () => {
		// The integration that matters: the range is the second argument to
		// `groupAgenda`, and `groupAgenda`'s day mode keys its groups on exactly
		// these strings. A format mismatch would produce zero groups, silently.
		const data: ScheduleData = {
			dated: [
				{
					id: 'asg-1',
					category: 'assignment',
					title: 'Lab 4',
					dayKey: '2026-08-22',
					timeLabel: '11:59 PM',
					detail: 'MGT 100',
					sortMinutes: 1439,
					allDay: false
				}
			],
			recurring: []
		};

		const groups = groupAgenda(data, agendaRange('2026-08-21', 3), 'day');
		expect(groups).toHaveLength(1);
		expect(groups[0].key).toBe('2026-08-22');
	});
});

describe('showsRowDate', () => {
	it('does not repeat the date when the group heading is the date', () => {
		expect(showsRowDate('day')).toBe(false);
	});

	it('names the date when the grouping is not by day', () => {
		/*
		 * The gap this closes. The Next agenda rendered `ItemRow` identically in all
		 * three groupings, and `ItemRow` shows a time and no date -- so grouped by
		 * type, thirty days of rows each read "9:30 AM" with nothing anywhere saying
		 * which 9:30 AM.
		 */
		expect(showsRowDate('category')).toBe(true);
		expect(showsRowDate('course')).toBe(true);
	});
});

describe('undatedTodoItem', () => {
	it('attaches the source row, which is the whole reason it can be ticked', () => {
		const source = quick();
		const item = undatedTodoItem(source);

		// The mechanism, asserted as the mechanism. `isTickable` reads the attached
		// object; a row built without it renders a checkbox that appears to tick and
		// reverts on the next render, with no error anywhere.
		expect(item.quickItem).toBe(source);
		expect(isTickable(item)).toBe(true);
	});

	it('carries whatever done state the to-do had', () => {
		expect(undatedTodoItem(quick({ done: true })).done).toBe(true);
		expect(undatedTodoItem(quick({ done: false })).done).toBe(false);
	});

	it('lands in the todo category and id space', () => {
		const item = undatedTodoItem(quick({ id: 'abc' }));
		expect(item.category).toBe('todo');
		expect(item.id).toBe('todo-abc');
	});

	it('is not all-day, because it is not on a day at all', () => {
		/*
		 * A departure from the Next source, which set `allDay: true` -- so `ItemRow`
		 * rendered "all day" on every undated to-do. "All day" is a claim about a
		 * DAY, and having no day is precisely what puts these rows in their own
		 * section. An empty time column says "no time here", which is true.
		 */
		const item = undatedTodoItem(quick());
		expect(item.allDay).toBe(false);
		expect(item.timeLabel).toBe('');
	});

	it('has no day key, so nothing can place it on the grid', () => {
		// `DatedScheduleItem` is the shape the month grid and the week columns
		// consume. This is deliberately only a `ScheduleItem`.
		expect('dayKey' in undatedTodoItem(quick())).toBe(false);
	});
});

describe('visibleUndatedTodos', () => {
	const open = quick({ id: 'open', done: false });
	const finished = quick({ id: 'finished', done: true });

	it('shows both when done items are shown', () => {
		const visible = visibleUndatedTodos([open, finished], { showDone: true });
		expect(visible.map((todo) => todo.id)).toEqual(['open', 'finished']);
	});

	it('drops finished ones when done items are hidden', () => {
		const visible = visibleUndatedTodos([open, finished], { showDone: false });
		expect(visible.map((todo) => todo.id)).toEqual(['open']);
	});

	it('hides ALL of them under urgent-only, because none can be urgent', () => {
		/*
		 * The rule the Next version was missing, and the reason it matters.
		 *
		 * Urgent is keyed by calendar item id and applied by `mergedSchedule`'s
		 * `annotate`, which runs over `data.dated` only. These rows never pass
		 * through it, so `urgent` is always undefined on them. Leaving them in meant
		 * that switching urgent-only on emptied the whole page EXCEPT this section --
		 * a filter that visibly does not apply to one section reads as broken.
		 *
		 * This is `filterSchedule`'s own recurring-classes rule finished, not a new
		 * one: it drops recurring classes under `urgentOnly` for exactly the same
		 * reason. Nothing in `filterSchedule` changed.
		 */
		expect(visibleUndatedTodos([open, finished], { showDone: true, urgentOnly: true })).toEqual([]);
		expect(visibleUndatedTodos([open], { showDone: false, urgentOnly: true })).toEqual([]);
	});

	it('does not mutate its input', () => {
		const input = [open, finished];
		visibleUndatedTodos(input, { showDone: false });
		expect(input).toHaveLength(2);
	});
});
