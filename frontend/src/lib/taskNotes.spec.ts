import { afterEach, describe, expect, it, vi } from "vitest";

import { installStorage, uninstallStorage, type FakeStorage } from "$lib/testing/fakeStorage";

/**
 * Self notes.
 *
 * Its own store rather than one built on `createOverrideStore`, so every
 * property has to be re-established here rather than inherited. That is the
 * point of testing it separately: the Next version's hand-rolled copy had
 * drifted, and accepted a stored array where its sibling did not.
 */

type TaskNotes = typeof import("$lib/taskNotes.svelte");

let storage: FakeStorage;

async function fresh(seed: Record<string, string> = {}): Promise<TaskNotes> {
	vi.resetModules();
	storage = installStorage(seed);
	return await import("$lib/taskNotes.svelte");
}

afterEach(() => {
	uninstallStorage();
});

describe("taskNotes: hydration", () => {
	it("is empty until hydrated", async () => {
		const notes = await fresh({ "thrive:task-notes": '{"t1":"call Amber"}' });

		expect(notes.taskNotes()).toEqual({});
	});

	it("loads on hydrate", async () => {
		const notes = await fresh({ "thrive:task-notes": '{"t1":"call Amber"}' });

		notes.hydrateTaskNotes();

		expect(notes.taskNotes()).toEqual({ t1: "call Amber" });
	});

	it("is empty with no storage, even after hydrate", async () => {
		vi.resetModules();
		uninstallStorage();
		const notes = await import("$lib/taskNotes.svelte");

		notes.hydrateTaskNotes();

		expect(notes.taskNotes()).toEqual({});
	});
});

describe("taskNotes: corrupt input", () => {
	it("rejects a stored array", async () => {
		/*
		 * HARDENED RELATIVE TO THE NEXT SOURCE, which cast the parse result
		 * straight to a note map with no shape check. An array would have come
		 * through and `notes[taskId]` would then read an index.
		 */
		const notes = await fresh({ "thrive:task-notes": '["a","b"]' });

		notes.hydrateTaskNotes();

		expect(notes.taskNotes()).toEqual({});
	});

	it("rejects non-object JSON", async () => {
		for (const raw of ["null", "42", '"text"', "true"]) {
			const notes = await fresh({ "thrive:task-notes": raw });
			notes.hydrateTaskNotes();
			expect(notes.taskNotes()).toEqual({});
			uninstallStorage();
		}
	});

	it("survives JSON that does not parse", async () => {
		const notes = await fresh({ "thrive:task-notes": "{broken" });

		expect(() => notes.hydrateTaskNotes()).not.toThrow();
		expect(notes.taskNotes()).toEqual({});
	});

	it("keeps the note in memory when the write fails", async () => {
		const notes = await fresh();
		notes.hydrateTaskNotes();
		storage.failWrites();

		expect(() => notes.setNote("t1", "kept")).not.toThrow();
		expect(notes.taskNotes()).toEqual({ t1: "kept" });
	});
});

describe("taskNotes: writing", () => {
	it("trims and stores a note", async () => {
		const notes = await fresh();

		notes.setNote("t1", "  ask about the capstone  ");

		expect(notes.taskNotes()).toEqual({ t1: "ask about the capstone" });
		expect(JSON.parse(storage.dump()["thrive:task-notes"])).toEqual({
			t1: "ask about the capstone",
		});
	});

	it("deletes on an emptied note rather than storing a blank", async () => {
		const notes = await fresh();

		notes.setNote("t1", "something");
		notes.setNote("t1", "   ");

		expect(notes.taskNotes()).toEqual({});
		expect(JSON.parse(storage.dump()["thrive:task-notes"])).toEqual({});
	});

	it("merges into what is already stored rather than replacing it", async () => {
		// The lazy-hydrate-on-write guard: without it this would persist only t2.
		const notes = await fresh({ "thrive:task-notes": '{"t1":"first"}' });

		notes.setNote("t2", "second");

		expect(notes.taskNotes()).toEqual({ t1: "first", t2: "second" });
	});

	it("leaves other notes alone", async () => {
		const notes = await fresh();

		notes.setNote("t1", "one");
		notes.setNote("t2", "two");
		notes.setNote("t1", "");

		expect(notes.taskNotes()).toEqual({ t2: "two" });
	});
});

describe("taskNote, the single-row view", () => {
	it("reads an empty string for a task with no note", async () => {
		const notes = await fresh();

		expect(notes.taskNote("t1").value).toBe("");
	});

	it("reads and writes one task's note", async () => {
		const notes = await fresh();
		const note = notes.taskNote("t1");

		note.save("remember the reading");

		expect(note.value).toBe("remember the reading");
		expect(notes.taskNote("t2").value).toBe("");
	});
});
