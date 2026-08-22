import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * The confirmation line.
 *
 * A single slot rather than a queue, and not persisted -- a confirmation that
 * survives a reload has stopped being a confirmation. So there is no storage
 * here and nothing to hydrate; the only behaviour worth pinning is the slot and
 * the clock.
 */

type Toast = typeof import("$lib/toast.svelte");

async function fresh(): Promise<Toast> {
	vi.resetModules();
	return await import("$lib/toast.svelte");
}

afterEach(() => {
	vi.useRealTimers();
});

describe("toast", () => {
	it("starts with nothing showing", async () => {
		const toast = await fresh();

		expect(toast.toast()).toBeNull();
	});

	it("shows a message", async () => {
		const toast = await fresh();

		toast.showToast("Copied to your list");

		expect(toast.toast()).toBe("Copied to your list");
	});

	it("clears itself after three seconds", async () => {
		vi.useFakeTimers();
		const toast = await fresh();

		toast.showToast("Copied to your list");

		vi.advanceTimersByTime(2999);
		expect(toast.toast()).toBe("Copied to your list");

		vi.advanceTimersByTime(1);
		expect(toast.toast()).toBeNull();
	});

	it("is one slot: a second message replaces the first", async () => {
		vi.useFakeTimers();
		const toast = await fresh();

		toast.showToast("first");
		toast.showToast("second");

		expect(toast.toast()).toBe("second");
	});

	it("restarts the clock on the replacing message", async () => {
		// Two in quick succession should not leave the second one cut short by the
		// first one's timer.
		vi.useFakeTimers();
		const toast = await fresh();

		toast.showToast("first");
		vi.advanceTimersByTime(2500);
		toast.showToast("second");

		vi.advanceTimersByTime(1000);
		expect(toast.toast()).toBe("second");

		vi.advanceTimersByTime(2000);
		expect(toast.toast()).toBeNull();
	});

	it("does not persist anything", async () => {
		// No storage is touched at all, so there is nothing to survive a reload.
		const toast = await fresh();
		toast.showToast("gone on reload");

		const reloaded = await fresh();
		expect(reloaded.toast()).toBeNull();
	});
});
