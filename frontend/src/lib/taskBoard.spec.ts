import { describe, expect, it } from "vitest";

import {
	dateForGroup,
	dropIndexWithin,
	fromDateInputValue,
	isDatedGroup,
	mintTaskId,
	newTaskFrom,
	reorderedIds,
	resolveRows,
	shiftFromNow,
	toDateInputValue
} from "./taskBoard";
import { describeDue } from "./format";
import type { TaskRowData } from "./homeView";
import type { Priority, Task } from "./data";

/**
 * The editing half of Home's task list.
 *
 * Fixed instant throughout: Tuesday 15 September 2026, 09:00 local, built from
 * local parts so the suite does not depend on the runner's timezone. Same choice
 * as `homeGroups.spec.ts`, and it is load-bearing here: every function in this
 * module converts between an instant and a LOCAL day, which is the exact place a
 * UTC assumption hides.
 */
const NOW = new Date(2026, 8, 15, 9, 0, 0);
const NOW_ISO = NOW.toISOString();

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

/** An instant `days` from NOW at a stated wall-clock time. */
function at(days: number, hour = 17, minute = 0): string {
	const date = new Date(NOW);
	date.setDate(date.getDate() + days);
	date.setHours(hour, minute, 0, 0);
	return date.toISOString();
}

function row(id: string, days: number, extra: Partial<Task> = {}): TaskRowData {
	const iso = at(days);
	return { task: task({ id, dueDate: iso, ...extra }), due: describeDue(iso, NOW) };
}

describe("isDatedGroup", () => {
	it("excludes 'Needs a date' as a destination", () => {
		// The decision this type enforces: you cannot move a task into having no
		// date. `unknown` is a source rows leave, never a place they land.
		expect(isDatedGroup("unknown")).toBe(false);
		expect(isDatedGroup("overdue")).toBe(true);
		expect(isDatedGroup("today")).toBe(true);
		expect(isDatedGroup("upcoming")).toBe(true);
	});
});

describe("dateForGroup", () => {
	it("keeps the task's own clock time rather than stamping now", () => {
		// A problem set due at 23:59 that moves to today is still due at 23:59.
		// Stamping it with the current time would quietly make it overdue.
		const moved = new Date(dateForGroup("today", at(3, 23, 59), NOW_ISO));

		expect(moved.getHours()).toBe(23);
		expect(moved.getMinutes()).toBe(59);
		expect(moved.getDate()).toBe(NOW.getDate());
	});

	it("lands 'overdue' yesterday and 'today' today", () => {
		expect(describeDue(dateForGroup("overdue", at(5), NOW_ISO), NOW).urgency).toBe("overdue");
		expect(describeDue(dateForGroup("today", at(5), NOW_ISO), NOW).urgency).toBe("today");
	});

	it("lands 'this week' three days out, not tomorrow", () => {
		/*
		 * The reason this is not +1. Dropping something into "This week" means "not
		 * urgent"; landing on tomorrow would classify it `upcoming` but put it right
		 * back at the top of the list the student was moving it out of.
		 */
		const due = describeDue(dateForGroup("upcoming", at(-2), NOW_ISO), NOW);

		expect(due.urgency).toBe("upcoming");
		expect(due.days).toBe(3);
	});
});

describe("toDateInputValue", () => {
	it("reads the LOCAL day, not the UTC one", () => {
		/*
		 * The bug this exists to avoid: `toISOString().slice(0, 10)` shifts an
		 * evening item onto the next day anywhere behind UTC, so a task due at 8pm
		 * would open its editor already showing tomorrow.
		 */
		const evening = new Date(2026, 8, 15, 20, 30, 0);

		expect(toDateInputValue(evening.toISOString())).toBe("2026-09-15");
	});

	it("pads a single-digit month and day", () => {
		expect(toDateInputValue(new Date(2026, 0, 4, 12, 0, 0).toISOString())).toBe("2026-01-04");
	});
});

describe("fromDateInputValue", () => {
	it("round-trips a date through the input and back", () => {
		const iso = at(2, 23, 59);
		expect(fromDateInputValue(toDateInputValue(iso), iso)).toBe(iso);
	});

	it("keeps the old clock time when the day changes", () => {
		const next = new Date(fromDateInputValue("2026-12-01", at(0, 8, 45)));

		expect(next.getFullYear()).toBe(2026);
		expect(next.getMonth()).toBe(11);
		expect(next.getDate()).toBe(1);
		expect(next.getHours()).toBe(8);
		expect(next.getMinutes()).toBe(45);
	});
});

describe("shiftFromNow", () => {
	it("measures from now, not from the date the task already had", () => {
		/*
		 * "Tomorrow" means tomorrow. Shifting from the task's existing date would
		 * make the shortcut mean "the day after whatever this was already set to",
		 * so pressing Tomorrow on a task due next month would land next month.
		 */
		const due = describeDue(shiftFromNow(1, at(30), NOW_ISO), NOW);

		expect(due.days).toBe(1);
		expect(due.urgency).toBe("upcoming");
	});

	it("keeps the task's clock time", () => {
		const shifted = new Date(shiftFromNow(7, at(0, 23, 59), NOW_ISO));

		expect(shifted.getHours()).toBe(23);
		expect(shifted.getMinutes()).toBe(59);
	});

	it("puts 'next week' at the edge of the week window, still inside it", () => {
		// `homeGroups` keeps `upcoming` to `days <= 7`, so 7 has to be inclusive or
		// the Next week shortcut would remove the row it just dated.
		expect(describeDue(shiftFromNow(7, at(0), NOW_ISO), NOW).days).toBe(7);
	});

	it("shifting by zero is today", () => {
		expect(describeDue(shiftFromNow(0, at(9), NOW_ISO), NOW).urgency).toBe("today");
	});
});

describe("a due date that will not parse", () => {
	/*
	 * The "Needs a date" group's whole purpose is that a student can fix it, so
	 * every route out of it runs an unparseable date through these converters.
	 *
	 * `new Date('nope').getHours()` is NaN, `setHours(NaN, NaN)` gives an Invalid
	 * Date, and `Invalid Date.toISOString()` THROWS a RangeError. Every one of
	 * these cases would have been an exception in front of a student pressing the
	 * one control the group exists to offer.
	 */
	const BROKEN = "not-a-date";

	it("offers a date input no value rather than 'NaN-NaN-NaN'", () => {
		// The literal NaN string is silently rejected by `<input type="date">`,
		// which leaves a field that looks broken on the rows that most need it.
		expect(toDateInputValue(BROKEN)).toBe("");
	});

	it("takes a first real date from the input without throwing", () => {
		const iso = fromDateInputValue("2026-10-02", BROKEN, NOW_ISO);
		const next = new Date(iso);

		expect(Number.isNaN(next.getTime())).toBe(false);
		expect(next.getMonth()).toBe(9);
		expect(next.getDate()).toBe(2);
		// The clock comes from the fallback, since a date that never parsed had no
		// time of day to preserve.
		expect(next.getHours()).toBe(NOW.getHours());
	});

	it("falls back to local midnight when even the fallback is unusable", () => {
		// The two-argument call, where the fallback defaults to the same broken
		// string. Midnight is deterministic; NaN throws.
		const next = new Date(fromDateInputValue("2026-10-02", BROKEN));

		expect(Number.isNaN(next.getTime())).toBe(false);
		expect(next.getHours()).toBe(0);
		expect(next.getMinutes()).toBe(0);
	});

	it("takes a shortcut without throwing", () => {
		expect(describeDue(shiftFromNow(1, BROKEN, NOW_ISO), NOW).urgency).toBe("upcoming");
		expect(describeDue(shiftFromNow(0, BROKEN, NOW_ISO), NOW).urgency).toBe("today");
	});

	it("can be dragged into a dated group without throwing", () => {
		// A row leaving "Needs a date" by drag. Every dated destination has to
		// survive it, not just the one someone happened to test.
		for (const group of ["overdue", "today", "upcoming"] as const) {
			const iso = dateForGroup(group, BROKEN, NOW_ISO);
			expect(Number.isNaN(new Date(iso).getTime())).toBe(false);
			expect(describeDue(iso, NOW).urgency).toBe(group);
		}
	});
});

describe("newTaskFrom", () => {
	const base = { title: "Read the case", dueDay: "", label: "", priority: "medium" as Priority };

	it("refuses an empty or whitespace title", () => {
		// Title is the only required field, so it is the only one that can refuse.
		expect(newTaskFrom({ ...base, title: "" }, NOW_ISO, "id")).toBeNull();
		expect(newTaskFrom({ ...base, title: "   " }, NOW_ISO, "id")).toBeNull();
	});

	it("trims the title and defaults to due now", () => {
		const made = newTaskFrom({ ...base, title: "  Read the case  " }, NOW_ISO, "own-1");

		expect(made).toMatchObject({
			id: "own-1",
			title: "Read the case",
			dueDate: NOW_ISO,
			source: "admin",
			priority: "medium",
			done: false,
			subtasks: []
		});
	});

	it("has no course code when the label is blank", () => {
		// `undefined` and not "", so `taskLabels` falls through to the source word
		// rather than rendering an empty chip.
		expect(newTaskFrom({ ...base, label: "   " }, NOW_ISO, "id")?.courseCode).toBeUndefined();
	});

	it("carries a label through as the course code", () => {
		expect(newTaskFrom({ ...base, label: " MGT 253 " }, NOW_ISO, "id")?.courseCode).toBe("MGT 253");
	});

	it("uses the chosen day at the current clock time", () => {
		const made = newTaskFrom({ ...base, dueDay: "2026-10-02" }, NOW_ISO, "id");
		const due = new Date(made!.dueDate);

		expect(due.getMonth()).toBe(9);
		expect(due.getDate()).toBe(2);
		expect(due.getHours()).toBe(NOW.getHours());
	});
});

describe("mintTaskId", () => {
	it("never collides, even inside one millisecond", () => {
		// The reason the counter exists: two adds faster than the clock ticks is
		// ordinary when the form stays open after a submit.
		const ids = new Set(Array.from({ length: 50 }, () => mintTaskId()));
		expect(ids.size).toBe(50);
	});

	it("is prefixed so it cannot collide with a fixture id", () => {
		expect(mintTaskId().startsWith("own-")).toBe(true);
	});
});

describe("resolveRows", () => {
	it("returns an untouched row by reference", () => {
		/*
		 * Load-bearing, not an optimisation. `{#each}` keyed on the task id compares
		 * objects; rebuilding every row on every store write would tear down a row
		 * whose only crime was being a sibling of an edited one -- losing an open
		 * note panel's draft on someone else's tick.
		 */
		const rows = [row("a", 1), row("b", 2)];
		const resolved = resolveRows(rows, {}, {}, {}, {}, NOW_ISO);

		expect(resolved[0]).toBe(rows[0]);
		expect(resolved[1]).toBe(rows[1]);
	});

	it("applies a title override", () => {
		const resolved = resolveRows([row("a", 1)], {}, { a: "Renamed" }, {}, {}, NOW_ISO);
		expect(resolved[0].task.title).toBe("Renamed");
	});

	it("applies a priority override", () => {
		const resolved = resolveRows([row("a", 1)], {}, {}, { a: "high" }, {}, NOW_ISO);
		expect(resolved[0].task.priority).toBe("high");
	});

	it("keeps the server's descriptor when only the title moved", () => {
		// The server is the authority on a date nobody changed. Re-deriving it would
		// be a second answer to a settled question.
		const rows = [row("a", 3)];
		const resolved = resolveRows(rows, {}, { a: "Renamed" }, {}, {}, NOW_ISO);

		expect(resolved[0].due).toBe(rows[0].due);
	});

	it("reclassifies a row whose due date moved", () => {
		const resolved = resolveRows([row("a", 3)], {}, {}, {}, { a: at(-1) }, NOW_ISO);

		expect(resolved[0].task.dueDate).toBe(at(-1));
		expect(resolved[0].due.urgency).toBe("overdue");
		expect(resolved[0].due.days).toBe(-1);
	});

	it("describes a student-created task against the same instant", () => {
		const own = task({ id: "own-1", dueDate: at(0, 12) });
		const resolved = resolveRows([], { "own-1": own }, {}, {}, {}, NOW_ISO);

		expect(resolved).toHaveLength(1);
		expect(resolved[0].due.urgency).toBe("today");
	});

	it("merges created tasks after the server's rows", () => {
		const own = task({ id: "own-1", dueDate: at(1) });
		const resolved = resolveRows([row("a", 1)], { "own-1": own }, {}, {}, {}, NOW_ISO);

		expect(resolved.map((r) => r.task.id)).toEqual(["a", "own-1"]);
	});

	it("applies edits to a created task too", () => {
		/*
		 * `setTaskDue` writes a due-date edit for a created task onto the task in
		 * `addedStore` rather than into the due map -- but a title or priority edit
		 * still goes to the override map, so both paths have to resolve.
		 */
		const own = task({ id: "own-1", dueDate: at(1) });
		const resolved = resolveRows([], { "own-1": own }, { "own-1": "Renamed" }, {}, {}, NOW_ISO);

		expect(resolved[0].task.title).toBe("Renamed");
	});

	it("does not mutate the rows it was given", () => {
		const rows = [row("a", 1)];
		const before = rows[0].task.title;
		resolveRows(rows, {}, { a: "Renamed" }, {}, {}, NOW_ISO);

		expect(rows[0].task.title).toBe(before);
	});

	it("survives an override pointing at an id that is not there", () => {
		// Property 3: corrupt or stale stored input cannot take the page down. An
		// override for a task that has since left the fixture is exactly that.
		const resolved = resolveRows([row("a", 1)], {}, { ghost: "nothing" }, {}, {}, NOW_ISO);

		expect(resolved).toHaveLength(1);
		expect(resolved[0].task.title).toBe("Task a");
	});
});

describe("dropIndexWithin", () => {
	it("accounts for the row's own absence when dropping below", () => {
		/*
		 * Removing the row first shifts everything after it up by one. Without this
		 * a row dropped two places down lands one place down, which reads as "drag
		 * is janky" rather than as an off-by-one.
		 */
		expect(dropIndexWithin(0, 3)).toBe(2);
	});

	it("leaves a drop above the row alone", () => {
		expect(dropIndexWithin(3, 1)).toBe(1);
	});

	it("is a no-op on the row's own slot", () => {
		expect(dropIndexWithin(2, 2)).toBe(2);
	});
});

describe("reorderedIds", () => {
	const ids = ["a", "b", "c", "d"];

	it("moves a row down", () => {
		expect(reorderedIds(ids, 0, 2)).toEqual(["b", "c", "a", "d"]);
	});

	it("moves a row up", () => {
		expect(reorderedIds(ids, 3, 1)).toEqual(["a", "d", "b", "c"]);
	});

	it("returns a copy, never the array it was given", () => {
		const result = reorderedIds(ids, 0, 1);
		expect(result).not.toBe(ids);
		expect(ids).toEqual(["a", "b", "c", "d"]);
	});

	it("is a no-op when nothing moves", () => {
		expect(reorderedIds(ids, 2, 2)).toEqual(ids);
	});

	it("clamps a target past the end rather than leaving a hole", () => {
		// `splice` past the end appends, which is what we want -- but the clamp says
		// so rather than relying on it, since a hole here would write `undefined`
		// into the order store as a sort key.
		expect(reorderedIds(ids, 0, 99)).toEqual(["b", "c", "d", "a"]);
	});

	it("ignores an out-of-range source", () => {
		expect(reorderedIds(ids, 9, 0)).toEqual(ids);
		expect(reorderedIds(ids, -1, 0)).toEqual(ids);
	});
});
