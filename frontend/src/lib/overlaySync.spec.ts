import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { overlayEnabled, primeOverlay, seedFor, syncOverlay } from "./overlaySync";

function stubFetch() {
  const impl = vi.fn().mockResolvedValue({ ok: true });
  vi.stubGlobal("fetch", impl);
  return impl;
}

function sentOps(impl: ReturnType<typeof vi.fn>) {
  return impl.mock.calls.map(([, init]) => JSON.parse(init.body as string));
}

beforeEach(() => {
  vi.useFakeTimers();
  primeOverlay({ stores: { "thrive:task-done": { "asg:a1": true } } });
});
afterEach(() => {
  primeOverlay(null);
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("overlaySync", () => {
  it("seed access and enablement", () => {
    expect(overlayEnabled()).toBe(true);
    expect(seedFor("thrive:task-done")).toEqual({ "asg:a1": true });
    expect(seedFor("thrive:task-titles")).toBeNull();
    primeOverlay(null);
    expect(overlayEnabled()).toBe(false);
  });

  it("does nothing when unprimed or for unhandled keys", () => {
    const impl = stubFetch();
    syncOverlay("thrive:quicklist-panel", "panel", { open: true });
    primeOverlay(null);
    syncOverlay("thrive:task-done", "asg:a1", true);
    expect(impl).not.toHaveBeenCalled();
  });

  it("dispatches override facets with null for cleared values", () => {
    const impl = stubFetch();
    syncOverlay("thrive:task-done", "asg:a1", true);
    syncOverlay("thrive:task-titles", "asg:a1", undefined);
    expect(sentOps(impl)).toEqual([
      { op: "task-override", taskKey: "asg:a1", facets: { done: true } },
      { op: "task-override", taskKey: "asg:a1", facets: { title: null } },
    ]);
  });

  it("adds clientKey to added tasks and removes on clear", () => {
    const impl = stubFetch();
    const task = { id: "task-add-1", title: "T", dueDate: "2026-09-01T12:00:00-07:00",
                   source: "admin", priority: "medium", done: false, subtasks: [] };
    syncOverlay("thrive:task-added", "task-add-1", task);
    syncOverlay("thrive:task-added", "task-add-1", undefined);
    const ops = sentOps(impl);
    expect(ops[0].op).toBe("task-add");
    expect(ops[0].task.clientKey).toBe("task-add-1");
    expect(ops[1]).toEqual({ op: "task-remove", taskKey: "task-add-1" });
  });

  it("coalesces order writes in one tick into one bulk op", async () => {
    const impl = stubFetch();
    syncOverlay("thrive:task-order", "asg:a1", 1);
    syncOverlay("thrive:task-order", "asg:a2", 2);
    syncOverlay("thrive:task-order", "asg:a3", undefined);
    expect(impl).not.toHaveBeenCalled();     // waits for the microtask
    await Promise.resolve();
    expect(sentOps(impl)).toEqual([
      { op: "task-order-bulk", orders: { "asg:a1": 1, "asg:a2": 2, "asg:a3": null } },
    ]);
  });

  it("debounces calendar prefs and sends the latest", () => {
    const impl = stubFetch();
    syncOverlay("thrive:calendar-prefs", "value", { view: "week" });
    syncOverlay("thrive:calendar-prefs", "value", { view: "agenda" });
    vi.advanceTimersByTime(399);
    expect(impl).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(sentOps(impl)).toEqual([{ op: "calendar-prefs", prefs: { view: "agenda" } }]);
  });

  it("join/ignore map presence to on", () => {
    const impl = stubFetch();
    syncOverlay("thrive:event-joins", "evt-2", true);
    syncOverlay("thrive:ignored-events", "evt-1", undefined);
    expect(sentOps(impl)).toEqual([
      { op: "event-join", eventId: "evt-2", on: true },
      { op: "event-ignore", eventId: "evt-1", on: false },
    ]);
  });

  it("never throws when fetch rejects", async () => {
    const impl = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", impl);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(() => syncOverlay("thrive:task-done", "asg:a1", true)).not.toThrow();
    await Promise.resolve();
    await Promise.resolve();
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});
