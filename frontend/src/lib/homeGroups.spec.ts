import { describe, expect, it } from "vitest";

import { buildHomeGroups, nonEmptyGroups } from "./homeGroups";
import { describeDue } from "./format";
import type { HomeRow } from "./homeGroups";
import type { Task } from "./data";

/**
 * Home's grouping.
 *
 * Fixed instant throughout: Tuesday 15 September 2026, 09:00 local, built from
 * local parts so the suite does not depend on the runner's timezone.
 */
const NOW = new Date(2026, 8, 15, 9, 0, 0);

function task(overrides: Partial<Task> & { id: string; dueDate: string }): Task {
	return {
		title: `Task ${overrides.id}`,
		source: "class",
		priority: "medium",
		done: false,
		subtasks: [],
		...overrides
	};
}

/** A row at `days` from NOW, keeping the clock time so the day is unambiguous. */
function rowAt(id: string, days: number, extra: Partial<Task> = {}): HomeRow {
	const due = new Date(NOW);
	due.setDate(due.getDate() + days);
	due.setHours(17, 0, 0, 0);
	const iso = due.toISOString();
	return { task: task({ id, dueDate: iso, ...extra }), due: describeDue(iso, NOW) };
}

describe("buildHomeGroups", () => {
	it("splits open rows into needs-a-date, overdue, today and this week", () => {
		const rows = [rowAt("a", -2), rowAt("b", 0), rowAt("c", 3)];
		const board = buildHomeGroups(rows, {});

		// `unknown` leads, always, even when empty -- see GROUP_ORDER.
		expect(board.groups.map((g) => g.key)).toEqual([
			"unknown",
			"overdue",
			"today",
			"upcoming"
		]);
		expect(board.groups[0].rows).toEqual([]);
		expect(board.groups[1].rows.map((r) => r.task.id)).toEqual(["a"]);
		expect(board.groups[2].rows.map((r) => r.task.id)).toEqual(["b"]);
		expect(board.groups[3].rows.map((r) => r.task.id)).toEqual(["c"]);
	});

	it("keeps 'this week' to a week", () => {
		// The reason the card was fourteen rows long: an assignment three weeks out
		// is real, but it is not what Home is for.
		const board = buildHomeGroups([rowAt("in-week", 7), rowAt("beyond", 8)], {});

		expect(board.groups[3].rows.map((r) => r.task.id)).toEqual(["in-week"]);
		// Still counted in the total -- it exists, it is just not on this card.
		expect(board.total).toBe(2);
	});

	it("sorts within a group by how soon, not by input order", () => {
		const board = buildHomeGroups([rowAt("later", 5), rowAt("sooner", 2)], {});
		expect(board.groups[3].rows.map((r) => r.task.id)).toEqual(["sooner", "later"]);
	});

	it("pulls done rows out of the groups entirely", () => {
		const rows = [rowAt("open", 1), rowAt("finished", 1, { done: true })];
		const board = buildHomeGroups(rows, {});

		expect(board.done.map((r) => r.task.id)).toEqual(["finished"]);
		expect(board.groups.flatMap((g) => g.rows.map((r) => r.task.id))).toEqual(["open"]);
	});

	it("lets a student's override outrank the fixture, both ways", () => {
		/*
		 * The reason this reads the store at all. `task.done` is the fixture's
		 * answer; the override is the student's, and it is persisted, so it can
		 * already disagree before any ticking exists in the UI.
		 */
		const rows = [rowAt("ships-open", 1), rowAt("ships-done", 1, { done: true })];

		const ticked = buildHomeGroups(rows, { "ships-open": true });
		expect(ticked.done.map((r) => r.task.id)).toEqual(["ships-open", "ships-done"]);

		// And the inverse: unticking something that ships done.
		const unticked = buildHomeGroups(rows, { "ships-done": false });
		expect(unticked.done).toEqual([]);
		expect(unticked.groups[3].rows).toHaveLength(2);
	});

	it("counts every task in the total, including done and out-of-window", () => {
		const rows = [rowAt("a", 1), rowAt("b", 30), rowAt("c", 1, { done: true })];
		const board = buildHomeGroups(rows, {});

		expect(board.total).toBe(3);
		expect(board.doneCount).toBe(1);
		expect(board.percent).toBeCloseTo(100 / 3);
	});

	it("reports 0 percent for an empty list rather than dividing by zero", () => {
		const board = buildHomeGroups([], {});
		expect(board.percent).toBe(0);
		expect(board.total).toBe(0);
	});

	it("puts an unparseable due date in its own group, at the top", () => {
		/*
		 * The Next version filtered by `due.urgency === group.key`, and "unknown"
		 * matches none of the three -- so a task with a broken deadline vanished
		 * from Home with no error. The fixtures contain no such date, which is why
		 * nobody noticed.
		 *
		 * Now it leads the list. Loud is correct, invisible is not: this is the one
		 * group a student can actually fix, and a deadline that silently does not
		 * exist is worse than one shouting for attention.
		 */
		const broken: HomeRow = {
			task: task({ id: "broken", dueDate: "not-a-date" }),
			due: describeDue("not-a-date", NOW)
		};
		const board = buildHomeGroups([broken, rowAt("fine", 1)], {});

		expect(board.groups[0].key).toBe("unknown");
		expect(board.groups[0].rows.map((r) => r.task.id)).toEqual(["broken"]);
		// It is FIRST in the flattened order, which is what makes it survive the
		// collapse to four rows on a capped card.
		expect(board.groups.flatMap((g) => g.rows).map((r) => r.task.id)).toEqual([
			"broken",
			"fine"
		]);
		// Counted, so the progress denominator does not quietly shrink.
		expect(board.total).toBe(2);
	});

	it("keeps unparseable rows in provider order, since there is nothing to sort by", () => {
		const mk = (id: string): HomeRow => ({
			task: task({ id, dueDate: "nope" }),
			due: describeDue("nope", NOW)
		});
		const board = buildHomeGroups([mk("z"), mk("a"), mk("m")], {});

		expect(board.groups[0].rows.map((r) => r.task.id)).toEqual(["z", "a", "m"]);
	});

	it("does not put an unparseable row in done", () => {
		const broken: HomeRow = {
			task: task({ id: "broken", dueDate: "not-a-date" }),
			due: describeDue("not-a-date", NOW)
		};
		expect(buildHomeGroups([broken], {}).done).toEqual([]);
	});
});

describe("buildHomeGroups, ordered by the student", () => {
	it("sorts by the student's own keys when they exist", () => {
		const board = buildHomeGroups([rowAt("a", 2), rowAt("b", 3), rowAt("c", 4)], {}, {
			a: 2,
			b: 0,
			c: 1
		});

		expect(board.groups[3].rows.map((r) => r.task.id)).toEqual(["b", "c", "a"]);
	});

	it("puts a moved row ahead of every row that has never been moved", () => {
		/*
		 * The rule, and it is not arbitrary: an explicit placement outranks an
		 * implicit one. Interleaving a reordered row back into the date-sorted list
		 * would drop it near where it started, which reads as the drag having
		 * failed.
		 */
		const board = buildHomeGroups([rowAt("soonest", 1), rowAt("moved", 6)], {}, { moved: 0 });

		expect(board.groups[3].rows.map((r) => r.task.id)).toEqual(["moved", "soonest"]);
	});

	it("falls back to how soon for rows with no key", () => {
		const board = buildHomeGroups([rowAt("later", 5), rowAt("sooner", 2)], {}, { other: 0 });
		expect(board.groups[3].rows.map((r) => r.task.id)).toEqual(["sooner", "later"]);
	});

	it("lets a student reorder rows that have no date to sort by", () => {
		/*
		 * "Needs a date" accepts no drops -- there is nothing to write, since
		 * `Task.dueDate` is required -- but a student can still arrange the rows
		 * already in it. The fallback is 0 and `sort` is stable, so unmoved rows
		 * keep the provider order they arrived in.
		 */
		const mk = (id: string): HomeRow => ({
			task: task({ id, dueDate: "nope" }),
			due: describeDue("nope", NOW)
		});
		const board = buildHomeGroups([mk("z"), mk("a"), mk("m")], {}, { m: 0 });

		expect(board.groups[0].rows.map((r) => r.task.id)).toEqual(["m", "z", "a"]);
	});

	it("ignores an order key for a row in another group", () => {
		// Keys are global but groups are sorted separately, so a key belonging to an
		// overdue row must not reorder the upcoming ones.
		const board = buildHomeGroups([rowAt("od", -1), rowAt("x", 2), rowAt("y", 3)], {}, { od: 0 });

		expect(board.groups[3].rows.map((r) => r.task.id)).toEqual(["x", "y"]);
	});

	it("defaults to no overrides, so a caller that cannot reorder is unaffected", () => {
		const rows = [rowAt("later", 5), rowAt("sooner", 2)];
		expect(buildHomeGroups(rows, {}).groups[3].rows.map((r) => r.task.id)).toEqual([
			"sooner",
			"later"
		]);
	});

	it("survives an order key pointing at a row that is not there", () => {
		// Property 3 again: a stale key in localStorage after a fixture changed.
		const board = buildHomeGroups([rowAt("a", 1)], {}, { ghost: 0 });
		expect(board.groups[3].rows.map((r) => r.task.id)).toEqual(["a"]);
	});
});

describe("nonEmptyGroups", () => {
	it("drops groups with no rows, so no heading appears over nothing", () => {
		// Including `unknown`: it leads the order but must not render a heading on
		// the overwhelmingly common day when every task has a date.
		const board = buildHomeGroups([rowAt("only", 3)], {});
		const shown = nonEmptyGroups(board.groups);

		expect(shown).toHaveLength(1);
		expect(shown[0].key).toBe("upcoming");
	});

	it("keeps the canonical order of the groups it keeps", () => {
		const board = buildHomeGroups([rowAt("a", 3), rowAt("b", -1)], {});
		expect(nonEmptyGroups(board.groups).map((g) => g.key)).toEqual(["overdue", "upcoming"]);
	});
});
