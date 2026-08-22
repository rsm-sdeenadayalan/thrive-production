import { describe, expect, it } from "vitest";

import { expandedEventLimit, planReveal, revealRowId } from "./reveal";
import { COLLAPSED_TASK_ROWS, VISIBLE_EVENTS } from "./cardLayout";
import { buildHomeGroups, nonEmptyGroups } from "./homeGroups";
import { describeDue } from "./format";
import type { HomeRow } from "./homeGroups";
import type { Task } from "./data";

/**
 * The reveal path.
 *
 * Two halves. The first is `planReveal` on its own, at the boundaries -- the
 * interesting cases are exactly-at-the-limit and one-past, same house style as
 * `collapse.spec.ts`, because that edge is where a jump either lands on a row
 * that is not rendered or expands a card for nothing.
 *
 * The second half runs the plan against the list a card actually builds. It is
 * the closest this suite can get to "clicking an overdue item expands the Tasks
 * card" without a DOM: the card's own ordering is `nonEmptyGroups(...).flatMap`,
 * so asserting against that is asserting against the real input rather than a
 * hand-written array that could agree with the test and disagree with the card.
 */

/**
 * The fixture clock, and every fixture instant, built from LOCAL PARTS.
 *
 * Not `new Date("2026-08-21T12:00:00Z")` with `Z` due dates beside it, which is
 * what this file had until the Phase 7a timezone sweep. `tsk-today` was
 * `2026-08-21T23:00:00Z`, and 23:00 UTC is already TOMORROW anywhere east of
 * UTC+2 -- so `describeDue` classified it `upcoming`, the "every overdue and
 * due-today task is reachable" test counted one row instead of two, and the
 * suite failed in Asia/Tokyo, Asia/Kathmandu and Australia/Lord_Howe.
 *
 * The bug was in the fixture, not in `describeDue`: a task due at 23:00 local on
 * the 21st IS due today, and that is what the assertion means. `local()` is the
 * rule TESTING.md already states -- build from local parts, serialise only on the
 * way out -- applied here at last.
 */
const local = (year: number, month: number, day: number, hour: number, minute = 0) =>
	new Date(year, month - 1, day, hour, minute).toISOString();

const NOW = new Date(2026, 7, 21, 12, 0);

function task(id: string, dueDate: string): Task {
	return {
		id,
		title: `Task ${id}`,
		dueDate,
		priority: "medium",
		source: "class",
		done: false,
		subtasks: []
	};
}

function row(id: string, dueDate: string): HomeRow {
	const source = task(id, dueDate);
	return { task: source, due: describeDue(source.dueDate, NOW) };
}

const ids = (n: number) => Array.from({ length: n }, (_, i) => `row-${i}`);

describe("revealRowId", () => {
	it("keeps the two kinds in separate id spaces", () => {
		// A task and an event could in principle carry the same id string. The
		// kind is in the DOM id so a jump cannot land on the wrong one.
		expect(revealRowId({ kind: "task", id: "tsk-001" })).toBe("reveal-task-tsk-001");
		expect(revealRowId({ kind: "event", id: "tsk-001" })).toBe("reveal-event-tsk-001");
	});

	it("passes a raw Event.id through unchanged", () => {
		// `evt-3-1` is the raw id, prefix and all. Stripping it here is the second
		// normaliser that made Home and the calendar disagree about what was
		// ignored -- MIGRATION.md section 9 defect 12.
		expect(revealRowId({ kind: "event", id: "evt-3-1" })).toBe("reveal-event-evt-3-1");
	});
});

describe("planReveal", () => {
	it("reports a row it does not hold as not found", () => {
		// Not the same answer as "found, and visible". The Tasks card gets every
		// event request too, and it must do nothing rather than decide it is
		// already showing it.
		expect(planReveal(ids(6), 4, "row-99")).toEqual({ found: false });
	});

	it("does not expand for a row inside the collapsed slice", () => {
		expect(planReveal(ids(6), 4, "row-0")).toEqual({ found: true, index: 0, expand: false });
	});

	it("does not expand for the last row of the collapsed slice", () => {
		// The boundary from below. Index 3 is the fourth of four visible rows.
		expect(planReveal(ids(6), 4, "row-3")).toEqual({ found: true, index: 3, expand: false });
	});

	it("expands for the first row past the collapsed slice", () => {
		// The boundary from above, and the case the whole module exists for.
		expect(planReveal(ids(6), 4, "row-4")).toEqual({ found: true, index: 4, expand: true });
	});

	it("expands for anything at all when nothing shows collapsed", () => {
		// The done group's arrangement: limit 0, entirely behind its count.
		expect(planReveal(ids(3), 0, "row-0")).toEqual({ found: true, index: 0, expand: true });
	});

	it("treats a negative or fractional limit the way collapseList does", () => {
		// A negative limit clamps to 0, so everything is past the slice.
		expect(planReveal(ids(3), -2, "row-0")).toEqual({ found: true, index: 0, expand: true });
		// 3.7 truncates to 3, so index 3 is past the slice.
		expect(planReveal(ids(6), 3.7, "row-3")).toEqual({ found: true, index: 3, expand: true });
	});
});

describe("revealing a task the Tasks card has collapsed", () => {
	/**
	 * The list the card renders from, built the way the card builds it.
	 *
	 * `TasksCard` flattens `nonEmptyGroups(board.groups)`, so the collapse counts
	 * ROWS across every group rather than per heading. That flattening is what
	 * puts an overdue task past the four-row cap, and it is the reason this test
	 * goes through `buildHomeGroups` instead of asserting on a literal.
	 */
	function flatOpenIds(rows: HomeRow[]): string[] {
		const board = buildHomeGroups(rows, {});
		return nonEmptyGroups(board.groups).flatMap((group) =>
			group.rows.map((entry) => entry.task.id)
		);
	}

	it("expands when undated rows have pushed the overdue task past the cap", () => {
		/*
		 * The realistic path, and the one today's fixture does not exercise.
		 *
		 * `unknown` is FIRST in GROUP_ORDER by decision (CONTEXT.md section 7), so
		 * four undated tasks fill the collapsed slice on their own and the overdue
		 * task -- the one the coral pill is counting -- is not on screen. Clicking
		 * it in the popover has to open the card.
		 */
		const rows = [
			row("tsk-overdue", local(2026, 8, 18, 17)),
			row("nodate-1", "not a date"),
			row("nodate-2", "not a date"),
			row("nodate-3", "not a date"),
			row("nodate-4", "not a date")
		];

		const list = flatOpenIds(rows);
		expect(list.slice(0, COLLAPSED_TASK_ROWS)).not.toContain("tsk-overdue");

		const plan = planReveal(list, COLLAPSED_TASK_ROWS, "tsk-overdue");
		expect(plan).toEqual({ found: true, index: 4, expand: true });
	});

	it("does not expand when the overdue task is already the first row", () => {
		// The companion assertion: the same call must be able to answer "no", or
		// the test above would pass on a function that always expands.
		const list = flatOpenIds([
			row("tsk-overdue", local(2026, 8, 18, 17)),
			row("tsk-later", local(2026, 8, 25, 17))
		]);

		expect(planReveal(list, COLLAPSED_TASK_ROWS, "tsk-overdue")).toEqual({
			found: true,
			index: 0,
			expand: false
		});
	});

	it("holds every overdue and due-today task in the card's own list", () => {
		/*
		 * The property that makes a task target always reachable.
		 *
		 * The pills count OPEN tasks by urgency; the card caps only its `upcoming`
		 * group, at seven days. So no overdue or due-today row can be filtered out
		 * of the card's list -- it can only be collapsed, which `planReveal`
		 * handles. If this ever fails, a pill is counting something the page
		 * cannot show and no amount of expanding will fix it.
		 */
		const rows = [
			row("tsk-overdue", local(2026, 8, 1, 17)),
			row("tsk-today", local(2026, 8, 21, 23)),
			row("tsk-soon", local(2026, 8, 24, 17)),
			// Three weeks out: really is dropped by the card, and really is not
			// counted by either pill.
			row("tsk-far", local(2026, 9, 14, 17))
		];

		const list = flatOpenIds(rows);
		const counted = rows.filter(
			(entry) => entry.due.urgency === "overdue" || entry.due.urgency === "today"
		);

		expect(counted).toHaveLength(2);
		for (const entry of counted) {
			expect(planReveal(list, COLLAPSED_TASK_ROWS, entry.task.id).found).toBe(true);
		}
		expect(list).not.toContain("tsk-far");
	});
});

describe("expandedEventLimit", () => {
	it("opens far enough to reach the whole week on a busy week", () => {
		// The measured case: 21 events inside seven days against a card showing
		// four. Every one of the 21 has to have a row once expanded.
		expect(expandedEventLimit(VISIBLE_EVENTS, 21)).toBe(21);
	});

	it("never shows fewer than the collapsed slice on a quiet week", () => {
		// Two events this week, more beyond. Expanding to the week count would
		// REMOVE two rows the card already shows at rest.
		expect(expandedEventLimit(VISIBLE_EVENTS, 2)).toBe(VISIBLE_EVENTS);
		expect(expandedEventLimit(VISIBLE_EVENTS, 0)).toBe(VISIBLE_EVENTS);
	});

	it("offers nothing to expand when the week is exactly the collapsed slice", () => {
		// Equal counts, so `collapseList` sees no overflow and draws no control.
		expect(expandedEventLimit(VISIBLE_EVENTS, VISIBLE_EVENTS)).toBe(VISIBLE_EVENTS);
	});

	it("reaches every this-week row it is given, as a prefix", () => {
		/*
		 * The prefix argument, asserted rather than trusted.
		 *
		 * `getEvents()` sorts ascending by start and the ignore filter preserves
		 * order, so "this week" is a prefix of the kept list. Slicing to the limit
		 * must therefore contain every this-week id -- which is what makes one
		 * `max()` enough instead of a union.
		 */
		const kept = [
			{ id: "evt-0-0", thisWeek: true },
			{ id: "evt-1-0", thisWeek: true },
			{ id: "evt-2-0", thisWeek: true },
			{ id: "evt-3-0", thisWeek: true },
			{ id: "evt-4-0", thisWeek: true },
			{ id: "evt-9-0", thisWeek: false },
			{ id: "evt-9-1", thisWeek: false }
		];

		const weekIds = kept.filter((entry) => entry.thisWeek).map((entry) => entry.id);
		const shown = kept
			.slice(0, expandedEventLimit(VISIBLE_EVENTS, weekIds.length))
			.map((entry) => entry.id);

		expect(weekIds).toHaveLength(5);
		for (const id of weekIds) expect(shown).toContain(id);
		// Non-vacuous: it stops there rather than showing everything.
		expect(shown).not.toContain("evt-9-0");
	});

	it("guards a nonsense count rather than slicing with it", () => {
		expect(expandedEventLimit(VISIBLE_EVENTS, -3)).toBe(VISIBLE_EVENTS);
		expect(expandedEventLimit(VISIBLE_EVENTS, 6.9)).toBe(6);
	});
});
