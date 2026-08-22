import { afterEach, describe, expect, it, vi } from "vitest";

import { installStorage, uninstallStorage, type FakeStorage } from "$lib/testing/fakeStorage";
import type { Task } from "$lib/data";

/**
 * The student's own edits.
 *
 * Property 4 -- "a write matching the source value forgets the override" --
 * lives in this module rather than in `overrideStore`, because only the caller
 * knows what the source value is. It is the whole subject of the first block
 * below, one function at a time, because each one compares against a different
 * field and each could drift independently.
 *
 * These are module singletons, so every test re-imports the module to get fresh
 * stores. Storage is installed before the import, but that is only for tidiness
 * -- the stores read it lazily, not at construction.
 */

type UserEdits = typeof import("$lib/userEdits.svelte");

let storage: FakeStorage;

async function fresh(seed: Record<string, string> = {}): Promise<UserEdits> {
	vi.resetModules();
	storage = installStorage(seed);
	return await import("$lib/userEdits.svelte");
}

/** What is actually sitting in one localStorage key, parsed. */
function stored(key: string): unknown {
	const raw = storage.dump()[key];
	return raw === undefined ? undefined : JSON.parse(raw);
}

function task(over: Partial<Task> = {}): Task {
	return {
		id: "t1",
		title: "Submit peer review",
		dueDate: new Date(2026, 7, 17, 14, 30).toISOString(),
		source: "class",
		priority: "high",
		done: false,
		subtasks: [],
		...over,
	};
}

afterEach(() => {
	uninstallStorage();
	vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Property 4, caller by caller
// ---------------------------------------------------------------------------

describe("property 4: setTaskDone forgets a write that matches the source", () => {
	it("stores nothing when marking an undone task undone", async () => {
		const edits = await fresh();

		edits.setTaskDone(task({ done: false }), false);

		expect(edits.taskDoneOverrides()).toEqual({});
		expect(stored("thrive:task-done")).toEqual({});
	});

	it("stores true when ticking an undone task", async () => {
		const edits = await fresh();

		edits.setTaskDone(task({ done: false }), true);

		expect(edits.taskDoneOverrides()).toEqual({ t1: true });
		expect(stored("thrive:task-done")).toEqual({ t1: true });
	});

	it("stores false when unticking a task that ships as done", async () => {
		// The case a bare set of ids cannot express at all.
		const edits = await fresh();

		edits.setTaskDone(task({ done: true }), false);

		expect(edits.taskDoneOverrides()).toEqual({ t1: false });
		expect(stored("thrive:task-done")).toEqual({ t1: false });
	});

	it("forgets when re-ticking a task that ships as done", async () => {
		const edits = await fresh();
		const source = task({ done: true });

		edits.setTaskDone(source, false);
		edits.setTaskDone(source, true);

		expect(edits.taskDoneOverrides()).toEqual({});
		expect(stored("thrive:task-done")).toEqual({});
	});
});

describe("property 4: the other setters", () => {
	it("setTaskTitle forgets an unchanged title", async () => {
		const edits = await fresh();

		edits.setTaskTitle(task(), "Submit peer review");

		expect(edits.taskTitles()).toEqual({});
	});

	it("setTaskTitle forgets an emptied title rather than storing a blank", async () => {
		const edits = await fresh();

		edits.setTaskTitle(task(), "New title");
		expect(edits.taskTitles()).toEqual({ t1: "New title" });

		edits.setTaskTitle(task(), "   ");
		expect(edits.taskTitles()).toEqual({});
	});

	it("setTaskTitle trims before comparing", async () => {
		const edits = await fresh();

		edits.setTaskTitle(task(), "  Submit peer review  ");

		expect(edits.taskTitles()).toEqual({});
	});

	it("setTaskPriority forgets an unchanged priority", async () => {
		const edits = await fresh();

		edits.setTaskPriority(task({ priority: "high" }), "high");
		expect(edits.taskPriorities()).toEqual({});

		edits.setTaskPriority(task({ priority: "high" }), "low");
		expect(edits.taskPriorities()).toEqual({ t1: "low" });
	});

	it("setTaskDue forgets an unchanged due date", async () => {
		const edits = await fresh();
		const source = task();

		edits.setTaskDue(source, source.dueDate);
		expect(edits.taskDues()).toEqual({});

		const moved = new Date(2026, 7, 20, 9, 0).toISOString();
		edits.setTaskDue(source, moved);
		expect(edits.taskDues()).toEqual({ t1: moved });
	});

	it("setEventJoined stores the absence rather than false", async () => {
		const edits = await fresh();

		// A RAW `Event.id`, which is the key space this store settled on in 7c.
		edits.setEventJoined("evt-3-1", true);
		expect(edits.eventJoins()).toEqual({ "evt-3-1": true });

		edits.setEventJoined("evt-3-1", false);
		expect(edits.eventJoins()).toEqual({});
	});

	it("keys on exactly the id it is handed, and normalises nothing", async () => {
		/*
		 * The store's own half of the key-space rule, stated the same way the ignore
		 * store states it. Both live in the raw-`Event.id` space and BOTH must
		 * refuse to touch what they are given -- a normaliser here could not tell a
		 * raw id from a calendar item id, because a raw event id starts with `evt-`
		 * too, which is exactly how the ignore store ended up as two stores wearing
		 * one name.
		 *
		 * The conversion belongs at the calendar's boundary. That half is pinned in
		 * `calendarEvents.spec.ts`.
		 */
		const edits = await fresh();

		edits.setEventJoined("evt-evt-3-1", true);

		expect(stored("thrive:event-joins")).toEqual({ "evt-evt-3-1": true });
	});
});

// ---------------------------------------------------------------------------
// Reading through the overrides
// ---------------------------------------------------------------------------

describe("isTaskDone", () => {
	it("uses the source value when untouched", async () => {
		const edits = await fresh();

		expect(edits.isTaskDone(task({ done: true }), {})).toBe(true);
		expect(edits.isTaskDone(task({ done: false }), {})).toBe(false);
	});

	it("lets an explicit false beat a source that ships done", async () => {
		const edits = await fresh();

		expect(edits.isTaskDone(task({ done: true }), { t1: false })).toBe(false);
	});
});

describe("applyTaskEdits", () => {
	it("returns the same object when there is nothing to apply", async () => {
		const edits = await fresh();
		const source = task();

		expect(edits.applyTaskEdits(source, {}, {})).toBe(source);
	});

	it("applies a title and a priority together", async () => {
		const edits = await fresh();

		const result = edits.applyTaskEdits(task(), { t1: "Renamed" }, { t1: "low" });

		expect(result.title).toBe("Renamed");
		expect(result.priority).toBe("low");
		// Everything else carries through untouched.
		expect(result.source).toBe("class");
	});
});

// ---------------------------------------------------------------------------
// Tasks the student created -- not overrides, they have no source row
// ---------------------------------------------------------------------------

describe("added tasks", () => {
	it("stores the whole task, not a diff", async () => {
		const edits = await fresh();
		const own = task({ id: "own-1" });

		edits.addTask(own);

		expect(edits.addedTasks()).toEqual({ "own-1": own });
	});

	it("puts a due-date edit on the task itself, not in the override map", async () => {
		// A student-created task has no source row to diverge from, so there is
		// nothing for an override to be an override OF.
		const edits = await fresh();
		const own = task({ id: "own-1" });
		const moved = new Date(2026, 7, 25, 9, 0).toISOString();

		edits.addTask(own);
		edits.setTaskDue(own, moved);

		expect(edits.addedTasks()["own-1"].dueDate).toBe(moved);
		expect(edits.taskDues()).toEqual({});
	});

	it("removeAddedTask leaves no orphaned overrides behind", async () => {
		const edits = await fresh();
		const own = task({ id: "own-1", done: false, priority: "high" });

		edits.addTask(own);
		edits.setTaskDone(own, true);
		edits.setTaskTitle(own, "Renamed");
		edits.setTaskPriority(own, "low");
		edits.setTaskDue(own, new Date(2026, 7, 25, 9, 0).toISOString());
		edits.setTaskOrder("own-1", 3);

		edits.removeAddedTask("own-1");

		expect(edits.addedTasks()).toEqual({});
		expect(edits.taskDoneOverrides()).toEqual({});
		expect(edits.taskTitles()).toEqual({});
		expect(edits.taskPriorities()).toEqual({});
		expect(edits.taskDues()).toEqual({});
		expect(edits.taskOrder()).toEqual({});
	});
});

describe("reorderWithin", () => {
	it("writes a key for every row in the group, not just the moved one", async () => {
		// A single key cannot express "between these two" once several rows share
		// the provider's implicit order.
		const edits = await fresh();

		edits.reorderWithin(["c", "a", "b"]);

		expect(edits.taskOrder()).toEqual({ c: 0, a: 1, b: 2 });
	});
});

// ---------------------------------------------------------------------------
// The undo slot
// ---------------------------------------------------------------------------

describe("taskToggle", () => {
	it("ticks a task and offers the way back", async () => {
		const edits = await fresh();
		const source = task({ done: false });

		edits.taskToggle.toggle(source);

		expect(edits.taskToggle.isDone(source)).toBe(true);
		expect(edits.taskToggle.undo).toEqual({ task: source, markedDone: true });
	});

	it("applyUndo reverts the tick and clears the offer", async () => {
		const edits = await fresh();
		const source = task({ done: false });

		edits.taskToggle.toggle(source);
		edits.taskToggle.applyUndo();

		expect(edits.taskToggle.isDone(source)).toBe(false);
		expect(edits.taskToggle.undo).toBeNull();
		// Back to source truth, so the override is forgotten rather than false.
		expect(edits.taskDoneOverrides()).toEqual({});
	});

	it("is one slot: a second toggle replaces the first offer", async () => {
		const edits = await fresh();
		const first = task({ id: "t1" });
		const second = task({ id: "t2" });

		edits.taskToggle.toggle(first);
		edits.taskToggle.toggle(second);

		expect(edits.taskToggle.undo?.task.id).toBe("t2");
		// The first task stays ticked; only its undo became unreachable.
		expect(edits.taskToggle.isDone(first)).toBe(true);
	});

	it("withdraws the offer after six seconds", async () => {
		vi.useFakeTimers();
		const edits = await fresh();

		edits.taskToggle.toggle(task());
		expect(edits.taskToggle.undo).not.toBeNull();

		vi.advanceTimersByTime(5999);
		expect(edits.taskToggle.undo).not.toBeNull();

		vi.advanceTimersByTime(1);
		expect(edits.taskToggle.undo).toBeNull();
	});

	it("restarts the clock on the replacing toggle", async () => {
		vi.useFakeTimers();
		const edits = await fresh();

		edits.taskToggle.toggle(task({ id: "t1" }));
		vi.advanceTimersByTime(5000);
		edits.taskToggle.toggle(task({ id: "t2" }));

		// The first timer must have been cleared, or this would already be null.
		vi.advanceTimersByTime(1000);
		expect(edits.taskToggle.undo?.task.id).toBe("t2");

		vi.advanceTimersByTime(5000);
		expect(edits.taskToggle.undo).toBeNull();
	});

	it("resolve applies the student's edits to the row", async () => {
		const edits = await fresh();
		const source = task();

		edits.setTaskTitle(source, "Renamed");

		expect(edits.taskToggle.resolve(source).title).toBe("Renamed");
	});
});

// ---------------------------------------------------------------------------
// Hydration, through a real store
// ---------------------------------------------------------------------------

describe("hydration", () => {
	it("shows no edits until the stores are hydrated", async () => {
		const edits = await fresh({ "thrive:task-done": '{"t1":true}' });

		expect(edits.taskDoneOverrides()).toEqual({});
	});

	it("shows the student's edits once hydrated", async () => {
		const edits = await fresh({ "thrive:task-done": '{"t1":true}' });
		const { hydrateStores } = await import("$lib/overrideStore.svelte");

		hydrateStores();

		expect(edits.taskDoneOverrides()).toEqual({ t1: true });
		expect(edits.isTaskDone(task({ done: false }), edits.taskDoneOverrides())).toBe(true);
	});

	it("survives a corrupt value for one key without losing the others", async () => {
		const edits = await fresh({
			"thrive:task-done": "[1,2,3]",
			"thrive:task-titles": '{"t1":"Renamed"}',
		});
		const { hydrateStores } = await import("$lib/overrideStore.svelte");

		hydrateStores();

		expect(edits.taskDoneOverrides()).toEqual({});
		expect(edits.taskTitles()).toEqual({ t1: "Renamed" });
	});
});
