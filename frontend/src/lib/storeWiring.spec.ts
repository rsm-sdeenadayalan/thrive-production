import { afterEach, describe, expect, it, vi } from "vitest";

import { installStorage, uninstallStorage } from "$lib/testing/fakeStorage";
import type { Task } from "$lib/data";

/**
 * End-to-end store wiring: real store functions, a primed (empty) seed so
 * hydration is seed-backed rather than localStorage-backed, and a stubbed
 * `fetch` to catch the ops `overlaySync` fires.
 *
 * Each per-module spec (`userEdits.spec.ts`, `ignoredEvents.spec.ts`, ...)
 * covers its own store's logic against a fake `syncOverlay`-free world, and
 * `overlaySync.spec.ts` covers the dispatcher against raw `syncOverlay` calls.
 * Neither sees the two composed: a real store's `set()` calling the real
 * dispatcher with the real payload shape. That composition is this file's only
 * job, so the assertions here pin wire payloads, not store behaviour.
 *
 * `vi.resetModules()` per case, then a fresh dynamic import of `overlaySync`
 * followed by the store module under test (same resolved path, same module
 * registry generation, so the store's own `import "./overlaySync"` resolves to
 * the instance primed below). Seeding every touched key with an EMPTY record
 * makes `hydrate()` take the seed branch instead of reading `localStorage`.
 */

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

function stubFetch() {
	const impl = vi.fn().mockResolvedValue({ ok: true });
	vi.stubGlobal("fetch", impl);
	return impl;
}

function sentOps(impl: ReturnType<typeof vi.fn>) {
	return impl.mock.calls.map(([, init]) => JSON.parse((init as RequestInit).body as string));
}

/**
 * Reset modules, install an (empty) fake `localStorage`, stub `fetch`, and
 * prime the overlay seed with an empty record for every key this case
 * touches. Returns the fetch stub for assertions.
 */
async function primeSeed(keys: string[]): Promise<ReturnType<typeof vi.fn>> {
	vi.resetModules();
	installStorage();
	const impl = stubFetch();
	const { primeOverlay } = await import("$lib/overlaySync");
	primeOverlay({ stores: Object.fromEntries(keys.map((key) => [key, {}])) });
	return impl;
}

afterEach(() => {
	uninstallStorage();
	vi.useRealTimers();
	vi.unstubAllGlobals();
});

describe("store wiring: userEdits", () => {
	it("setTaskDone sends the override, and forgets on a match with a clear", async () => {
		const impl = await primeSeed(["thrive:task-done"]);
		const edits = await import("$lib/userEdits.svelte");
		const source = task({ done: false });

		edits.setTaskDone(source, true);
		edits.setTaskDone(source, false);

		expect(sentOps(impl)).toEqual([
			{ op: "task-override", taskKey: "t1", facets: { done: true } },
			{ op: "task-override", taskKey: "t1", facets: { done: null } },
		]);
	});

	it("addTask sends task-add with clientKey; removeAddedTask sends task-remove", async () => {
		const impl = await primeSeed([
			"thrive:task-added",
			"thrive:task-due",
			"thrive:task-order",
			"thrive:task-titles",
			"thrive:task-priority",
			"thrive:task-done",
		]);
		const edits = await import("$lib/userEdits.svelte");
		const own = task({ id: "own-1" });

		edits.addTask(own);
		edits.removeAddedTask("own-1");
		await Promise.resolve(); // flush the coalesced order write, if any

		const ops = sentOps(impl);
		const addOp = ops.find((op) => op.op === "task-add");
		expect(addOp?.task.clientKey).toBe("own-1");

		const removeOp = ops.find((op) => op.op === "task-remove");
		expect(removeOp).toEqual({ op: "task-remove", taskKey: "own-1" });
	});

	it("reorderWithin sends exactly one bulk op after the microtask flush", async () => {
		const impl = await primeSeed(["thrive:task-order"]);
		const edits = await import("$lib/userEdits.svelte");

		edits.reorderWithin(["a", "b"]);
		expect(impl).not.toHaveBeenCalled(); // still coalescing

		await Promise.resolve();

		expect(sentOps(impl)).toEqual([
			{ op: "task-order-bulk", orders: { a: 0, b: 1 } },
		]);
	});
});

describe("store wiring: ignoredEvents", () => {
	it("setEventIgnored(true) sends event-ignore on:true", async () => {
		const impl = await primeSeed(["thrive:ignored-events"]);
		const ignoredEvents = await import("$lib/ignoredEvents");

		ignoredEvents.setEventIgnored("evt-1", true);

		expect(sentOps(impl)).toEqual([{ op: "event-ignore", eventId: "evt-1", on: true }]);
	});
});

describe("store wiring: calendarPrefs", () => {
	it("setCalendarPrefs sends one debounced op with the merged prefs", async () => {
		vi.useFakeTimers();
		const impl = await primeSeed(["thrive:calendar-prefs"]);
		const calendarPrefs = await import("$lib/calendarPrefs");

		calendarPrefs.setCalendarPrefs({ view: "week" });
		expect(impl).not.toHaveBeenCalled(); // still debouncing

		await vi.advanceTimersByTimeAsync(400);

		const ops = sentOps(impl);
		expect(ops).toHaveLength(1);
		expect(ops[0].op).toBe("calendar-prefs");
		expect(ops[0].prefs.view).toBe("week");
	});
});

describe("store wiring: calendarItems", () => {
	it("setItemLabel sends item-label", async () => {
		const impl = await primeSeed(["thrive:item-labels"]);
		const calendarItems = await import("$lib/calendarItems");

		calendarItems.setItemLabel("apt-3", "Chat");

		expect(sentOps(impl)).toEqual([{ op: "item-label", itemKey: "apt-3", label: "Chat" }]);
	});
});

describe("store wiring: quickList", () => {
	it("addQuickItem sends quick-put with the item's title", async () => {
		const impl = await primeSeed(["thrive:quicklist"]);
		const quickList = await import("$lib/quickList");

		quickList.addQuickItem("milk");

		const ops = sentOps(impl);
		expect(ops).toHaveLength(1);
		expect(ops[0].op).toBe("quick-put");
		expect(ops[0].item.title).toBe("milk");
	});
});
