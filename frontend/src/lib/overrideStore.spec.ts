import { afterEach, describe, expect, it } from "vitest";

import { createOverrideStore, hydrateStores } from "$lib/overrideStore.svelte";
import { installStorage, uninstallStorage } from "$lib/testing/fakeStorage";

/**
 * The persistence mechanism, and the four properties everything else rests on.
 *
 * Each of these is a rule that, broken, fails silently: the student's edit
 * quietly comes back, or quietly does not, and nothing throws. That is why they
 * are pinned here rather than left to review.
 */

afterEach(() => {
	uninstallStorage();
});

// ---------------------------------------------------------------------------
// Property 1 -- overrides keyed by id, never the whole truth
// ---------------------------------------------------------------------------

describe("property 1: overrides, not the whole truth", () => {
	it("starts empty", () => {
		installStorage();
		expect(createOverrideStore<boolean>("k").values).toEqual({});
	});

	it("records only the ids the student actually touched", () => {
		installStorage();
		const store = createOverrideStore<boolean>("k");

		store.set("a", true);

		expect(store.values).toEqual({ a: true });
		expect("b" in store.values).toBe(false);
	});

	it("deletes the key on undefined rather than storing undefined", () => {
		// `undefined` has to mean "never touched, use the source value". Storing
		// the key with an undefined value would make it indistinguishable from a
		// deliberate choice on reload, once JSON drops it anyway.
		installStorage();
		const store = createOverrideStore<boolean>("k");

		store.set("a", true);
		store.set("a", undefined);

		expect(store.values).toEqual({});
		expect("a" in store.values).toBe(false);
	});

	it("can express unticking something that ships as done", () => {
		/*
		 * THE REASON THIS IS AN OVERRIDE MAP AND NOT A SET OF IDS.
		 *
		 * A bare set of done-ids has no way to say "false" -- it can only add or
		 * omit, and omitting means "use the source", which for a task that ships
		 * done means done. So the untick would silently undo itself on reload.
		 * An explicit `false` is a different thing from an absent key.
		 */
		const storage = installStorage();
		const store = createOverrideStore<boolean>("thrive:task-done");

		store.set("ships-done", false);

		expect(store.values["ships-done"]).toBe(false);
		expect("ships-done" in store.values).toBe(true);

		// And it survives the round trip, which is the half that actually broke.
		const reloaded = createOverrideStore<boolean>("thrive:task-done");
		reloaded.hydrate();
		expect(reloaded.values["ships-done"]).toBe(false);
		expect(storage.dump()["thrive:task-done"]).toBe('{"ships-done":false}');
	});

	it("keeps distinct keys in separate stores", () => {
		// The three key spaces -- task id, calendar item id, raw Event.id -- are
		// separate stores, so the same string in two of them cannot collide.
		installStorage();
		const tasks = createOverrideStore<boolean>("thrive:task-done");
		const items = createOverrideStore<string>("thrive:item-labels");

		tasks.set("shared-id", true);
		items.set("shared-id", "thesis");

		expect(tasks.values["shared-id"]).toBe(true);
		expect(items.values["shared-id"]).toBe("thesis");
	});
});

// ---------------------------------------------------------------------------
// Property 2 -- empty on the server, real after mount
// ---------------------------------------------------------------------------

describe("property 2: empty on the server, real after mount", () => {
	it("is empty with no storage at all, even after hydrate", () => {
		// This is the server. There is no localStorage in a node process, so the
		// un-personalised page is the only thing that can render.
		uninstallStorage();
		const store = createOverrideStore<boolean>("k");

		store.hydrate();

		expect(store.values).toEqual({});
	});

	it("does not read storage until hydrate is called", () => {
		// The first client render must match the server's markup. Reading eagerly
		// at construction, or lazily during the first render, is the mismatch this
		// ordering exists to avoid.
		installStorage({ k: '{"a":true}' });
		const store = createOverrideStore<boolean>("k");

		expect(store.values).toEqual({});

		store.hydrate();

		expect(store.values).toEqual({ a: true });
	});

	it("hydrate is idempotent", () => {
		installStorage({ k: '{"a":true}' });
		const store = createOverrideStore<boolean>("k");

		store.hydrate();
		store.set("b", true);
		store.hydrate(); // must not wipe the edit by re-reading

		expect(store.values).toEqual({ a: true, b: true });
	});

	it("hydrateStores loads every registered store at once", () => {
		installStorage({ one: '{"a":1}', two: '{"b":2}' });
		const first = createOverrideStore<number>("one");
		const second = createOverrideStore<number>("two");

		expect(first.values).toEqual({});
		expect(second.values).toEqual({});

		hydrateStores();

		expect(first.values).toEqual({ a: 1 });
		expect(second.values).toEqual({ b: 2 });
	});

	it("hydrates lazily on a write, so a pre-mount edit cannot clobber storage", () => {
		// If the layout has not called hydrateStores yet and the student edits
		// something, the write must merge into what is already stored rather than
		// replacing the whole key with one entry.
		const storage = installStorage({ k: '{"existing":true}' });
		const store = createOverrideStore<boolean>("k");

		store.set("new", true);

		expect(store.values).toEqual({ existing: true, new: true });
		expect(JSON.parse(storage.dump().k)).toEqual({ existing: true, new: true });
	});
});

// ---------------------------------------------------------------------------
// Property 3 -- corrupt input cannot take the page down
// ---------------------------------------------------------------------------

describe("property 3: corrupt input cannot take the page down", () => {
	it("rejects an array, which passes typeof object", () => {
		installStorage({ k: "[1,2,3]" });
		const store = createOverrideStore<boolean>("k");

		store.hydrate();

		expect(store.values).toEqual({});
	});

	it("rejects every non-object JSON value", () => {
		for (const raw of ["null", "42", '"a string"', "true"]) {
			installStorage({ k: raw });
			const store = createOverrideStore<boolean>("k");

			store.hydrate();

			expect(store.values).toEqual({});
			uninstallStorage();
		}
	});

	it("survives JSON that does not parse", () => {
		installStorage({ k: "{not json" });
		const store = createOverrideStore<boolean>("k");

		expect(() => store.hydrate()).not.toThrow();
		expect(store.values).toEqual({});
	});

	it("survives an empty string", () => {
		installStorage({ k: "" });
		const store = createOverrideStore<boolean>("k");

		store.hydrate();

		expect(store.values).toEqual({});
	});

	it("keeps the edit in memory when the write fails", () => {
		// Out of quota, or private mode. Losing the write is acceptable; losing
		// the edit the student just made, in front of them, is not.
		const storage = installStorage();
		const store = createOverrideStore<boolean>("k");
		store.hydrate();
		storage.failWrites();

		expect(() => store.set("a", true)).not.toThrow();
		expect(store.values).toEqual({ a: true });
		expect(storage.dump().k).toBeUndefined();
	});

	it("survives storage that throws on access", () => {
		// Some sandboxed contexts throw on merely touching localStorage.
		Object.defineProperty(globalThis, "localStorage", {
			get() {
				throw new Error("blocked");
			},
			configurable: true,
		});

		const store = createOverrideStore<boolean>("k");

		expect(() => store.hydrate()).not.toThrow();
		expect(() => store.set("a", true)).not.toThrow();
		expect(store.values).toEqual({ a: true });
	});
});

// ---------------------------------------------------------------------------
// Property 4 -- a write matching the source forgets the override
//
// The comparison itself lives in each caller (`setTaskDone` and friends), since
// only the caller knows the source value. What this layer owes is that passing
// `undefined` genuinely removes the entry, in memory AND in storage.
// ---------------------------------------------------------------------------

describe("property 4: forgetting leaves nothing behind", () => {
	it("removes the entry from persisted JSON, not just from memory", () => {
		const storage = installStorage();
		const store = createOverrideStore<boolean>("k");

		store.set("a", true);
		store.set("b", true);
		expect(JSON.parse(storage.dump().k)).toEqual({ a: true, b: true });

		store.set("a", undefined);

		expect(JSON.parse(storage.dump().k)).toEqual({ b: true });
	});

	it("leaves the store genuinely empty, so nothing is pinned to a stale answer", () => {
		const storage = installStorage();
		const store = createOverrideStore<boolean>("k");

		store.set("a", true);
		store.set("a", undefined);

		expect(store.values).toEqual({});
		expect(JSON.parse(storage.dump().k)).toEqual({});
	});

	it("forgetting an id that was never set is a no-op", () => {
		installStorage();
		const store = createOverrideStore<boolean>("k");

		expect(() => store.set("never", undefined)).not.toThrow();
		expect(store.values).toEqual({});
	});
});

// ---------------------------------------------------------------------------
// The rest of the contract
// ---------------------------------------------------------------------------

describe("read", () => {
	it("returns the current values without triggering a load", () => {
		// Deliberately does not hydrate: a component calling this during render
		// would otherwise assign state mid-render, which Svelte rejects.
		installStorage({ k: '{"a":true}' });
		const store = createOverrideStore<boolean>("k");

		expect(store.read()).toEqual({});

		store.hydrate();

		expect(store.read()).toEqual({ a: true });
	});
});

describe("persistence round trip", () => {
	it("writes JSON a fresh store can read back", () => {
		const storage = installStorage();
		const first = createOverrideStore<{ n: number }>("k");

		first.set("a", { n: 1 });

		const second = createOverrideStore<{ n: number }>("k");
		second.hydrate();

		expect(second.values).toEqual({ a: { n: 1 } });
		expect(storage.dump().k).toBe('{"a":{"n":1}}');
	});
});
