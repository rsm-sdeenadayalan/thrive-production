import { afterEach, describe, expect, it, vi } from "vitest";

import { primeOverlay } from "./overlaySync";

afterEach(() => {
	primeOverlay(null);
	vi.unstubAllGlobals();
	vi.resetModules();
});

describe("seed-backed stores", () => {
	it("hydrates from the seed and syncs writes without touching localStorage", async () => {
		const impl = vi.fn().mockResolvedValue({ ok: true });
		vi.stubGlobal("fetch", impl);
		const setItem = vi.fn();
		vi.stubGlobal("localStorage", { getItem: vi.fn(() => null), setItem });

		const { primeOverlay: primeOverlayDynamic } = await import("./overlaySync");
		primeOverlayDynamic({ stores: { "thrive:seed-test": { a: 1 } } });
		const { createOverrideStore } = await import("./overrideStore.svelte");
		const store = createOverrideStore<number>("thrive:seed-test");
		store.hydrate();
		expect(store.read()).toEqual({ a: 1 });

		store.set("b", 2);
		expect(store.read()).toEqual({ a: 1, b: 2 }); // optimistic local state
		expect(setItem).not.toHaveBeenCalled(); // no localStorage in API mode
		// no handler for thrive:seed-test → no network either
		expect(impl).not.toHaveBeenCalled();
	});

	it("falls back to localStorage when unprimed", async () => {
		vi.stubGlobal("localStorage", {
			getItem: vi.fn(() => JSON.stringify({ x: true })),
			setItem: vi.fn(),
		});
		const { createOverrideStore } = await import("./overrideStore.svelte");
		const store = createOverrideStore<boolean>("thrive:seed-test-2");
		store.hydrate();
		expect(store.read()).toEqual({ x: true });
	});

	it("task notes hydrate from the seed and sync via task-note op", async () => {
		const impl = vi.fn().mockResolvedValue({ ok: true });
		vi.stubGlobal("fetch", impl);
		vi.stubGlobal("localStorage", { getItem: vi.fn(() => null), setItem: vi.fn() });

		const { primeOverlay: primeOverlayDynamic } = await import("./overlaySync");
		primeOverlayDynamic({ stores: { "thrive:task-notes": { "asg:a1": "hi" } } });

		const notes = await import("./taskNotes.svelte");
		notes.hydrateTaskNotes();
		expect(notes.taskNotes()).toEqual({ "asg:a1": "hi" });

		notes.setNote("asg:a2", "  new note ");
		expect(notes.taskNotes()["asg:a2"]).toBe("new note");
		const sent = JSON.parse(impl.mock.calls[0][1].body as string);
		expect(sent).toEqual({ op: "task-note", taskKey: "asg:a2", note: "new note" });
	});
});
