import { describe, expect, it } from 'vitest';

import { buildScheduleData, nowMinutesAt, todayKey } from '$lib/buildSchedule';
import { getAssignments, getCourses, getEvents, getMyAppointments } from '$lib/data';
import { eventIdOf } from '$lib/ignoredEvents';
import { dayKeyOf, legendOrder, minutesOf, wallClockLabel } from '$lib/schedule';
import { isTickable } from '$lib/tickItem';

/**
 * The server half of the calendar's data.
 *
 * Every fixture in `mock/` is dated relative to the moment it is read, so
 * nothing here may pin a literal date -- a test asserting "2026-08-21" passes
 * once and then fails every day after. What is pinned instead are the
 * PROPERTIES the rest of the calendar relies on: which id space a row lands in,
 * that its `dayKey` agrees with its own `startISO`, that an all-day row is
 * all-day in all three of its fields at once, and that nothing the server built
 * claims to be tickable.
 *
 * Those properties are what the views actually consume. A dated item whose
 * `dayKey` disagrees with its `startISO` puts a dot on one day and the row on
 * another, which is the failure mode `filterSchedule` was centralised to make
 * impossible -- and no type catches it.
 */

describe('buildScheduleData', () => {
	it('returns both shapes, and neither is empty with the current fixtures', async () => {
		const data = await buildScheduleData();

		// The companion assertion. Almost everything below iterates a collection,
		// and iterating an empty one proves nothing at all.
		expect(data.dated.length).toBeGreaterThan(0);
		expect(data.recurring.length).toBeGreaterThan(0);
	});

	it('keeps classes as weekday rules rather than expanding them', async () => {
		const [data, courses] = await Promise.all([buildScheduleData(), getCourses()]);

		// One rule per meeting, not one row per meeting per week. This is the
		// property that lets the grid page to any month without another round trip.
		const meetings = courses.reduce((sum, course) => sum + course.schedule.length, 0);
		expect(data.recurring).toHaveLength(meetings);

		for (const rule of data.recurring) {
			expect(rule.dayOfWeek).toBeGreaterThanOrEqual(0);
			expect(rule.dayOfWeek).toBeLessThanOrEqual(6);
			// A wall clock, so expanding it carries no timezone with it.
			expect(rule.startTime).toMatch(/^\d{1,2}:\d{2}$/);
			expect(rule.timeLabel).toBe(wallClockLabel(rule.startTime));
		}
	});

	it('gives a twice-weekly course two distinct rule ids', async () => {
		const [data, courses] = await Promise.all([buildScheduleData(), getCourses()]);

		// The meeting index is part of the id for exactly this reason: without it
		// two meetings of one course collide and one row renders where two belong.
		const repeating = courses.filter((course) => course.schedule.length > 1);
		expect(repeating.length).toBeGreaterThan(0);

		expect(new Set(data.recurring.map((rule) => rule.id)).size).toBe(data.recurring.length);
	});

	it('pins every dated row to the day its own start falls on, locally', async () => {
		const data = await buildScheduleData();

		for (const item of data.dated) {
			expect(item.startISO).toBeDefined();
			// `toISOString().slice(0, 10)` would move an evening row onto the next
			// day anywhere behind UTC. `dayKeyOf` builds from local parts.
			expect(item.dayKey).toBe(dayKeyOf(item.startISO!));
		}
	});

	it('gives every row an id in its own stream and a category the legend knows', async () => {
		const data = await buildScheduleData();

		for (const item of data.dated) {
			expect(item.id).toMatch(/^(asg|evt|apt)-/);
			expect(legendOrder).toContain(item.category);
		}

		expect(new Set(data.dated.map((item) => item.id)).size).toBe(data.dated.length);
	});

	it('attaches no source row, so nothing the server built can be ticked', async () => {
		const data = await buildScheduleData();

		/*
		 * The server has nothing writable to attach. Tickability comes from a
		 * `Task` or `QuickItem` being present, which only `mergedSchedule` can
		 * supply -- so a checkbox on any of these rows would be a checkbox with
		 * nowhere to write, which is the exact silent failure `tickItem` was
		 * rewritten to make impossible.
		 */
		for (const item of data.dated) {
			expect(isTickable(item)).toBe(false);
			expect(item.done).toBeUndefined();
		}
	});

	describe('assignments', () => {
		it('carry the course code and are never all-day', async () => {
			const [data, assignments, courses] = await Promise.all([
				buildScheduleData(),
				getAssignments(),
				getCourses()
			]);

			const codes = new Set(courses.map((course) => course.code));
			const rows = data.dated.filter((item) => item.category === 'assignment');
			expect(rows).toHaveLength(assignments.length);

			for (const row of rows) {
				// A deadline has a time. Floating it all-day would sort it above a
				// class it is actually due after.
				expect(row.allDay).toBe(false);
				expect(codes).toContain(row.detail);
			}
		});
	});

	describe('events', () => {
		it('are all-day in all three fields at once, or in none of them', async () => {
			const data = await buildScheduleData();

			const rows = data.dated.filter((item) => item.id.startsWith('evt-'));
			expect(rows.length).toBeGreaterThan(0);

			for (const row of rows) {
				const sameInstant = row.startISO === row.endISO;
				expect(row.allDay).toBe(sameInstant);

				if (row.allDay) {
					// Three fields, one decision. A row that is all-day but sorts by a
					// real time would slot in among the timed rows and read as a bug.
					expect(row.timeLabel).toBe('All day');
					expect(row.sortMinutes).toBe(0);
				}
			}
		});

		it('double-prefix their ids, and eventIdOf recovers the raw one exactly', async () => {
			const [data, events] = await Promise.all([buildScheduleData(), getEvents()]);

			const raw = new Set(events.map((event) => event.id));
			const rows = data.dated.filter((item) => item.id.startsWith('evt-evt-'));

			/*
			 * THE DOUBLE PREFIX IS DELIBERATE AND THIS IS WHERE IT IS PINNED.
			 *
			 * A raw `Event.id` is already `evt-3-1`, so the calendar's stream prefix
			 * makes it `evt-evt-3-1`. That is not a slip: every calendar item id
			 * names its stream, and the label and urgent stores are keyed on that
			 * space. What the collision DID break is the ignore store, and the fix
			 * lives there -- `eventIdOf` is applied to a calendar item id and to
			 * nothing else, which is the only input it can read unambiguously.
			 */
			expect(rows).toHaveLength(events.length);

			for (const row of rows) {
				expect(raw).toContain(eventIdOf(row.id));
			}
		});
	});

	describe('appointments', () => {
		it('name the advisor, since "Appointment" alone says nothing', async () => {
			const [data, appointments] = await Promise.all([
				buildScheduleData(),
				getMyAppointments()
			]);

			const rows = data.dated.filter((item) => item.category === 'appointment');
			expect(rows).toHaveLength(appointments.length);

			for (const row of rows) {
				expect(row.title).not.toBe('Appointment');
				expect(row.title).toContain(' with ');
				expect(row.detail).not.toBe('');
			}
		});
	});
});

describe('todayKey', () => {
	it('agrees with dayKeyOf on the same instant', () => {
		// Not a tautology: it is the assertion that the ONE clock read on the
		// calendar page produces the same string every `===` comparison downstream
		// is made against.
		expect(todayKey()).toBe(dayKeyOf(new Date()));
	});
});

describe('nowMinutesAt', () => {
	it('measures minutes past local midnight', () => {
		expect(nowMinutesAt(new Date(2026, 7, 21, 14, 30))).toBe(minutesOf('14:30'));
		expect(nowMinutesAt(new Date(2026, 7, 21, 0, 0))).toBe(0);
		expect(nowMinutesAt(new Date(2026, 7, 21, 23, 59))).toBe(23 * 60 + 59);
	});

	it('is local, so it does not shift with the offset the way an ISO string would', () => {
		const midnight = new Date(2026, 7, 21, 0, 0);
		// The whole reason this takes a Date rather than an ISO string: the answer
		// must be wall-clock minutes, and a UTC read would be off by the offset.
		expect(nowMinutesAt(midnight)).toBe(midnight.getHours() * 60 + midnight.getMinutes());
	});
});
